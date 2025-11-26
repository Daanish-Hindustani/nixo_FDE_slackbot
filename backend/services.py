import os
import json
import logging
from threading import Lock
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timezone
from math import exp, log

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

from openai import OpenAI
from sqlmodel import Session, select

from models import Message, Issue

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
DEFAULT_SEARCH_THRESHOLD = float(os.getenv("SEARCH_THRESHOLD", "0.35"))
DEFAULT_TEMPORAL_WEIGHT = float(os.getenv("TEMPORAL_WEIGHT", "0.35"))
DEFAULT_TIME_DECAY_HOURS = float(os.getenv("TIME_DECAY_HOURS", "24.0"))
DEFAULT_TOP_K = int(os.getenv("SEARCH_TOP_K", "3"))
MAX_CACHE_SIZE = int(os.getenv("TS_CACHE_MAX", "10000"))
FIRST_N_MESSAGES_FOR_CENTROID = int(os.getenv("CENTROID_FIRST_N", "5"))
MIN_WORDS_FOR_MEANINGFUL_MSG = int(os.getenv("MIN_WORDS_MEANINGFUL", "5"))
SHORT_MSG_WORD_THRESHOLD = int(os.getenv("SHORT_MSG_WORD_THRESHOLD", "6"))
ANN_FETCH_K = int(os.getenv("ANN_FETCH_K", "25"))
DEBUG_SIMILARITY = bool(int(os.getenv("DEBUG_SIMILARITY", "0")))

SYSTEM_PROMPT = """
You are an expert FDE assistant. Classify the following Slack message.
Output JSON:
{
  "label": "bug_report" | "support_question" | "feature_request" | "product_question" | "irrelevant",
  "is_relevant": boolean,
  "confidence": float (0.0-1.0),
  "summary": "short summary of the issue"
}

Relevant messages: Support questions, Bug reports, Feature requests, Product questions.
Irrelevant: Greetings, Social, Acknowledgments (ok, thanks), Logistics.
"""

SELECTION_PROMPT = """
You are an expert FDE assistant. Determine if the new message belongs to any of the existing issues.

New Message: {message}
Message Timestamp: {message_timestamp}

Existing Issues:
{issues_text}

IMPORTANT: When evaluating which issue the message belongs to, consider:
1. **Topic Match** - Is the message about the SAME specific problem/feature/question as the issue?
   - Don't group messages just because they share common words (e.g., "button", "login", "export")
   - "Login button doesn't work" is DIFFERENT from "Missing CSV export button"
2. **Temporal Proximity** - Is the message timestamp close to the issue's last update?
   - **CRITICAL**: Messages sent within seconds or 1-2 minutes are VERY LIKELY conversational follow-ups
   - Short messages like "I don't see a button for it" sent immediately after another message are almost certainly related to that conversation
   - Messages hours/days apart need stronger topic match
3. **Context Continuity** - Does it make sense as a direct follow-up or clarification?
   - "I don't see a button for it" should group with the immediately preceding conversation about a missing button
   - Pronouns like "it" usually refer to the most recent topic

Be STRICT about topic matching, but LENIENT about recency - if a message was sent within 1-2 minutes and could plausibly be a follow-up, it probably is.

Output JSON:
{{
  "selected_issue_id": int | null,
  "reason": "short explanation including topic and time consideration"
}}
"""

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

def _normalize(vec: np.ndarray) -> np.ndarray:
    vec = np.array(vec, dtype="float32")
    norm = np.linalg.norm(vec)
    if norm == 0 or np.isnan(norm):
        return vec
    return vec / norm


def get_semantic_embedding(text: str) -> np.ndarray:
    vec = embedding_model.encode(text)
    return _normalize(vec)


def get_metadata_embedding(text: str, user: str, channel: str, ts: str) -> np.ndarray:
    formatted = f"Channel: {channel} User: {user} Time: {ts} Text: {text}"
    vec = embedding_model.encode(formatted)
    return _normalize(vec)


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    if a is None or b is None:
        return 0.0
    a = _normalize(a)
    b = _normalize(b)
    return float(np.dot(a, b))


def temporal_decay_score(query_ts: datetime, issue_ts: datetime, half_life_hours: float) -> float:
    if query_ts.tzinfo is None:
        query_ts = query_ts.replace(tzinfo=timezone.utc)
    if issue_ts.tzinfo is None:
        issue_ts = issue_ts.replace(tzinfo=timezone.utc)
    time_diff_hours = abs((query_ts - issue_ts).total_seconds()) / 3600.0
    return float(exp(-log(2) * time_diff_hours / half_life_hours))


def classification_boost(msg_label: str, issue_label: Optional[str]) -> float:
    if not issue_label:
        return 0.0
    return 0.15 if msg_label == issue_label else -0.05

def classify_message_with_llm(text: str) -> Dict:
    client = get_openai_client()
    if not client:
        logger.warning("No OpenAI API Key found. Returning default classification.")
        return {"label": "irrelevant", "is_relevant": False, "confidence": 0.0, "summary": ""}

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception:
        logger.exception("LLM classification failed")
        return {"label": "irrelevant", "is_relevant": False, "confidence": 0.0, "summary": ""}


def select_issue_with_llm(message: str, candidates: List[Issue], message_timestamp: Optional[datetime] = None) -> Optional[int]:
    client = get_openai_client()
    if not client:
        return candidates[0].id if candidates else None

    try:
        msg_ts_str = message_timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if message_timestamp else "Unknown"
        
        issues_text = "\n\n".join([
            f"ID: {issue.id}\nTitle: {getattr(issue, 'title', '')}\nSummary: {getattr(issue, 'summary', '')}\nLast Updated: {getattr(issue, 'updated_at', datetime.now(timezone.utc)).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            for issue in candidates
        ])
        prompt = SELECTION_PROMPT.format(message=message, message_timestamp=msg_ts_str, issues_text=issues_text)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        return result.get("selected_issue_id")
    except Exception:
        logger.exception("LLM selection failed")
        return candidates[0].id if candidates else None


def check_if_followup_to_previous(new_message: str, new_msg_timestamp: datetime, previous_message: Message) -> bool:
    """
    Use LLM to determine if new_message is a conversational follow-up to previous_message.
    Returns True if it's a follow-up, False otherwise.
    """
    client = get_openai_client()
    if not client:
        return False

    try:
        # Ensure timestamp is timezone-aware
        prev_ts = previous_message.timestamp
        if prev_ts.tzinfo is None:
            prev_ts = prev_ts.replace(tzinfo=timezone.utc)
        
        time_diff_seconds = abs((new_msg_timestamp - prev_ts).total_seconds())
        
        prompt = f"""
You are an expert at understanding conversational context in Slack messages.

Previous Message: "{previous_message.text}"
Previous Message Timestamp: {prev_ts.strftime('%Y-%m-%d %H:%M:%S UTC')}

New Message: "{new_message}"
New Message Timestamp: {new_msg_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

Time between messages: {time_diff_seconds:.0f} seconds

Determine if the new message is a direct conversational follow-up to the previous message.
Consider:
- Does the new message reference or continue the topic from the previous message?
- Are pronouns like "it", "that", "this" referring to something in the previous message?
- Is it providing additional context or clarification?
- Does the timing suggest it's part of the same conversation?

Output JSON:
{{
  "is_followup": boolean,
  "confidence": float (0.0-1.0),
  "reason": "brief explanation"
}}
"""
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        
        is_followup = result.get("is_followup", False)
        confidence = result.get("confidence", 0.0)
        reason = result.get("reason", "")
        
        logger.info(f"LLM follow-up check: is_followup={is_followup}, confidence={confidence:.2f}, reason={reason}")
        
        return is_followup and confidence >= 0.6
    except Exception:
        logger.exception("LLM follow-up check failed")
        return False

class VectorStore:
    def __init__(self, session: Session):
        self.dim = EMBEDDING_DIM
        self.index = faiss.IndexFlatIP(self.dim)
        self.index = faiss.IndexIDMap(self.index)
        self.issue_timestamps: Dict[int, datetime] = {}
        self.issue_metadata_embeddings: Dict[int, np.ndarray] = {}
        self._load_from_db(session)

    def _load_from_db(self, session: Session):
        try:
            issues = session.exec(select(Issue).where(Issue.embedding != None)).all()
            logger.info(f"Loading {len(issues)} issues into vector store")
            if not issues:
                return

            vectors = []
            ids = []
            for issue in issues:
                try:
                    vec = np.array(json.loads(issue.embedding), dtype="float32")
                    vec = _normalize(vec)
                    if vec.size != self.dim:
                        logger.warning(f"Issue {issue.id}: embedding dimension mismatch ({vec.size} != {self.dim})")
                        continue
                    vectors.append(vec)
                    ids.append(int(issue.id))
                    ts_val = issue.updated_at or datetime.now(timezone.utc)
                    if ts_val.tzinfo is None:
                        ts_val = ts_val.replace(tzinfo=timezone.utc)
                    self.issue_timestamps[int(issue.id)] = ts_val

                    md_text = f"{getattr(issue, 'title', '')} {getattr(issue, 'summary', '')}"
                    try:
                        md_vec = embedding_model.encode(md_text)
                        self.issue_metadata_embeddings[int(issue.id)] = _normalize(md_vec)
                    except Exception:
                        self.issue_metadata_embeddings[int(issue.id)] = None

                except Exception:
                    logger.exception(f"Error loading embedding for issue {issue.id}")
                    continue

            if vectors:
                xb = np.stack(vectors)
                ids_np = np.array(ids, dtype="int64")
                self.index.add_with_ids(xb, ids_np)
        except Exception:
            logger.exception("Failed to initialize vector store from DB")

    def search(self, embedding: np.ndarray,
               threshold: float = DEFAULT_SEARCH_THRESHOLD,
               query_timestamp: Optional[datetime] = None,
               temporal_weight: float = DEFAULT_TEMPORAL_WEIGHT,
               time_decay_hours: float = DEFAULT_TIME_DECAY_HOURS,
               top_k: int = DEFAULT_TOP_K,
               fetch_k: int = 10) -> List[Tuple[int, float]]:
        if self.index.ntotal == 0:
            return []

        embedding = _normalize(embedding)
        fetch_k = min(fetch_k, int(self.index.ntotal))
        distances, ids = self.index.search(embedding.reshape(1, -1), fetch_k)
        distances = distances[0]
        ids = ids[0]

        candidates = []
        for dist, iid in zip(distances, ids):
            if iid == -1:
                continue
            issue_id = int(iid)
            semantic_score = float(dist)
            combined_score = semantic_score

            md_vec = self.issue_metadata_embeddings.get(issue_id)
            if md_vec is not None:
                md_sim = float(np.dot(embedding, md_vec))
                combined_score = combined_score * 0.9 + md_sim * 0.1

            if query_timestamp and issue_id in self.issue_timestamps:
                issue_time = self.issue_timestamps[issue_id]
                ts_score = temporal_decay_score(query_timestamp, issue_time, time_decay_hours)
                combined_score = (1 - temporal_weight) * combined_score + temporal_weight * ts_score

            if DEBUG_SIMILARITY:
                logger.info(f"[ANN] issue={issue_id} semantic={semantic_score:.3f} combined={combined_score:.3f}")

            # keep candidates even if below threshold; higher layer decides
            candidates.append((issue_id, combined_score))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]

    def add_issue(self, issue_id: int, embedding: np.ndarray, timestamp: Optional[datetime] = None):
        try:
            vec = _normalize(embedding)
            if vec.size != self.dim:
                logger.warning(f"Attempted to add embedding with wrong dim: {vec.size}")
                return
            xb = vec.reshape(1, -1)
            ids = np.array([int(issue_id)], dtype="int64")
            try:
                self.index.remove_ids(np.array([issue_id], dtype="int64"))
            except Exception:
                pass
            self.index.add_with_ids(xb, ids)
            ts_val = timestamp or datetime.now(timezone.utc)
            if ts_val.tzinfo is None:
                ts_val = ts_val.replace(tzinfo=timezone.utc)
            self.issue_timestamps[int(issue_id)] = ts_val
            self.issue_metadata_embeddings[int(issue_id)] = None
        except Exception:
            logger.exception("Failed to add issue to vector store")

_vector_store: Optional[VectorStore] = None
_vector_store_lock = Lock()

def get_vector_store(session: Session) -> VectorStore:
    global _vector_store
    with _vector_store_lock:
        if _vector_store is None:
            _vector_store = VectorStore(session)
        return _vector_store

def update_issue_centroid(session: Session, issue_id: int) -> Optional[np.ndarray]:
    msgs = session.exec(
        select(Message)
        .where(Message.issue_id == issue_id)
        .order_by(Message.timestamp.asc())
        .limit(FIRST_N_MESSAGES_FOR_CENTROID)
    ).all()

    vectors = []
    for msg in msgs:
        if not msg.embedding:
            continue
        if len((msg.text or "").split()) < MIN_WORDS_FOR_MEANINGFUL_MSG:
            continue
        try:
            vec = np.array(json.loads(msg.embedding), dtype="float32")
            vectors.append(vec)
        except Exception:
            logger.exception(f"Bad embedding for message {getattr(msg,'id',None)}")
            continue

    if not vectors:
        return None

    weights = np.linspace(1.0, 0.3, num=len(vectors))
    centroid = np.average(np.stack(vectors), axis=0, weights=weights)
    return _normalize(centroid)

_ts_cache = {}
_ts_cache_lock = Lock()

def compute_hybrid_scores_for_candidates(
    semantic_vec: np.ndarray,
    metadata_vec: np.ndarray,
    candidates: List[Issue],
    vector_store: VectorStore,
    msg_timestamp: datetime,
    msg_label: str
) -> List[Tuple[Issue, float]]:
    results = []
    for issue in candidates:
        issue_centroid = None
        try:
            if issue.embedding:
                issue_centroid = _normalize(np.array(json.loads(issue.embedding), dtype="float32"))
        except Exception:
            issue_centroid = None

        semantic_score = 0.0
        if issue_centroid is not None:
            semantic_score = cosine_sim(semantic_vec, issue_centroid)
        else:
            md_vec = vector_store.issue_metadata_embeddings.get(issue.id)
            semantic_score = cosine_sim(semantic_vec, md_vec) if md_vec is not None else 0.0

        md_vec = vector_store.issue_metadata_embeddings.get(issue.id)
        md_score = cosine_sim(metadata_vec, md_vec) if md_vec is not None else 0.0

        issue_time = vector_store.issue_timestamps.get(issue.id, datetime.now(timezone.utc))
        temp_score = temporal_decay_score(msg_timestamp, issue_time, DEFAULT_TIME_DECAY_HOURS)

        cboost = classification_boost(msg_label, getattr(issue, "classification", None))

        combined = 0.3 * semantic_score + 0.3 * md_score + 0.2 * temp_score + cboost

        if DEBUG_SIMILARITY:
            logger.info(f"[RERANK] issue={issue.id} sem={semantic_score:.3f} md={md_score:.3f} "
                        f"temp={temp_score:.3f} cboost={cboost:.3f} combined={combined:.3f}")

        results.append((issue, combined))

    results.sort(key=lambda x: x[1], reverse=True)
    return results

def process_message(session: Session, slack_event: dict):
    text = (slack_event.get("text") or "").strip()
    user = slack_event.get("user")
    ts = slack_event.get("ts")
    channel = slack_event.get("channel")
    thread_ts = slack_event.get("thread_ts")

    if not ts:
        logger.warning("Message without ts received; ignoring.")
        return None

    with _ts_cache_lock:
        if ts in _ts_cache:
            _ts_cache[ts] = _ts_cache.pop(ts)
            if DEBUG_SIMILARITY:
                logger.debug(f"Duplicate TS {ts} in cache; skipping")
            return None

    existing = session.exec(select(Message).where(Message.slack_ts == ts)).first()
    if existing:
        with _ts_cache_lock:
            if len(_ts_cache) >= MAX_CACHE_SIZE:
                _ts_cache.pop(next(iter(_ts_cache)))
            _ts_cache[ts] = True
        if DEBUG_SIMILARITY:
            logger.debug(f"Message {ts} already in DB; skipping")
        return None

    classification = classify_message_with_llm(text)
    if not classification.get("is_relevant", False):
        if DEBUG_SIMILARITY:
            logger.info("Message classified as irrelevant by LLM; skipping")
        return None

    semantic_vec = get_semantic_embedding(text)
    metadata_vec = get_metadata_embedding(text, user or "", channel or "", ts)

    issue = None
    if thread_ts:
        parent_msg = session.exec(select(Message).where(Message.slack_ts == thread_ts)).first()
        if parent_msg and parent_msg.issue_id:
            issue = session.get(Issue, parent_msg.issue_id)
            logger.info(f"Thread message detected - grouping with parent issue id={getattr(issue,'id',None)}")

    vector_store = get_vector_store(session)

    if not issue:
        try:
            msg_timestamp = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        except Exception:
            msg_timestamp = datetime.now(timezone.utc)

        
        most_recent_msg = session.exec(
            select(Message)
            .where(Message.channel_id == channel)
            .where(Message.slack_ts != ts) 
            .order_by(Message.timestamp.desc())
            .limit(1)
        ).first()
        
        if most_recent_msg and most_recent_msg.issue_id:
            logger.info("Checking if new message is a follow-up to the most recent message...")
            is_followup = check_if_followup_to_previous(text, msg_timestamp, most_recent_msg)
            
            if is_followup:
                logger.info(f"✓ LLM confirmed: This is a follow-up to previous message - using issue {most_recent_msg.issue_id}")
                issue = session.get(Issue, most_recent_msg.issue_id)
                if issue:
                    logger.info(f"Grouped with previous message's issue {issue.id} based on LLM follow-up detection")
            else:
                logger.info("✗ LLM determined: Not a follow-up to previous message - proceeding with vector search")
        
        
        if not issue:
            ann_candidates = vector_store.search(
                embedding=semantic_vec,
                threshold=max(0.01, DEFAULT_SEARCH_THRESHOLD * 0.75),
                query_timestamp=msg_timestamp,
                temporal_weight=DEFAULT_TEMPORAL_WEIGHT,
                time_decay_hours=DEFAULT_TIME_DECAY_HOURS,
                top_k=ANN_FETCH_K if ANN_FETCH_K > DEFAULT_TOP_K else DEFAULT_TOP_K,
                fetch_k=ANN_FETCH_K
            )

            if not ann_candidates:
                if DEBUG_SIMILARITY:
                    logger.info("No ANN candidates returned at all")
                ann_candidate_ids = []
            else:
                ann_candidate_ids = [c[0] for c in ann_candidates]

            candidate_issues = [session.get(Issue, cid) for cid in ann_candidate_ids]
            candidate_issues = [i for i in candidate_issues if i is not None]

            if candidate_issues:
                filtered = []
                for i in candidate_issues:
                    if getattr(i, "classification", None) == classification.get("label"):
                        filtered.append(i)
                if not filtered:
                    filtered = candidate_issues[:max(3, len(candidate_issues))]
                candidate_issues = filtered

                word_count = len(text.split())
                if word_count < SHORT_MSG_WORD_THRESHOLD:
                    logger.info("Short message detected — performing LLM-only grouping fallback for candidates")
                    selected_id = select_issue_with_llm(text, candidate_issues, msg_timestamp)
                    if selected_id:
                        issue = session.get(Issue, selected_id)
                        logger.info(f"LLM-short-text selected issue {getattr(issue,'id',None)}")
                    else:
                        if DEBUG_SIMILARITY:
                            logger.info("LLM-short-text did not select an issue")

                if not issue:
                    reranked = compute_hybrid_scores_for_candidates(
                        semantic_vec, metadata_vec, candidate_issues, vector_store, msg_timestamp, classification.get("label")
                    )
                    if reranked:
                        best_issue, best_score = reranked[0]
                        if DEBUG_SIMILARITY:
                            logger.info(f"Top reranked candidate: id={best_issue.id} score={best_score:.3f}")
                        
                        if best_score >= DEFAULT_SEARCH_THRESHOLD:
                            if best_score >= 0.6:
                                issue = best_issue
                                logger.info(f"Assigned to issue {issue.id} by rerank (high confidence score {best_score:.3f})")
                            else:
                                logger.info(f"Score {best_score:.3f} requires LLM validation to prevent false positives")
                                selected_id = select_issue_with_llm(text, [best_issue], msg_timestamp)
                                if selected_id:
                                    issue = session.get(Issue, selected_id)
                                    logger.info(f"LLM confirmed grouping into issue {issue.id}")
                                else:
                                    logger.info("LLM rejected grouping - will create new issue")
                        else:
                            if best_score >= DEFAULT_SEARCH_THRESHOLD * 0.5:
                                logger.info(f"Best score {best_score:.3f} below threshold; asking LLM to confirm")
                                selected_id = select_issue_with_llm(text, [best_issue], msg_timestamp)
                                if selected_id:
                                    issue = session.get(Issue, selected_id)
                                    logger.info(f"LLM confirmed grouping into issue {issue.id}")
                            else:
                                if DEBUG_SIMILARITY:
                                    logger.info("No reranked candidate passed soft thresholds")
            else:
                if DEBUG_SIMILARITY:
                    logger.info("No candidate issues to attempt grouping")

        if not issue:
            logger.info("Creating new issue from message")
            nonlocal_title = classification.get("summary") or (text[:80] + ("..." if len(text) > 80 else ""))
            issue = Issue(
                title=nonlocal_title,
                summary=classification.get("summary") or "",
                classification=classification.get("label"),
                updated_at=datetime.now(timezone.utc)
            )
            session.add(issue)
            session.commit()
            session.refresh(issue)
            logger.info(f"Created issue id={issue.id}")
    else:
        if getattr(issue, "status", None) == "closed":
            issue.status = "open"
        issue.updated_at = datetime.now(timezone.utc)
        session.add(issue)
        session.commit()

    try:
        msg = Message(
            slack_ts=ts,
            thread_ts=thread_ts,
            channel_id=channel,
            user_id=user,
            text=text,
            timestamp=datetime.fromtimestamp(float(ts), tz=timezone.utc),
            classification=classification.get("label"),
            confidence=classification.get("confidence", 0.0),
            is_relevant=True,
            issue_id=issue.id,
            embedding=json.dumps(semantic_vec.tolist())
        )
        session.add(msg)
        session.commit()
        session.refresh(msg)
        logger.info(f"Saved message id={getattr(msg,'id',None)} to issue id={issue.id}")
    except Exception:
        logger.exception("Failed to save message to DB")
        return None

    new_centroid = update_issue_centroid(session, issue.id)
    if new_centroid is not None:
        try:
            issue.embedding = json.dumps(new_centroid.tolist())
            issue.updated_at = datetime.now(timezone.utc)
            session.add(issue)
            session.commit()
            vector_store.add_issue(issue.id, new_centroid, issue.updated_at)
            logger.info(f"Updated centroid for issue id={issue.id} and pushed to FAISS")
        except Exception:
            logger.exception("Failed updating issue centroid/FAISS entry")

    with _ts_cache_lock:
        if len(_ts_cache) >= MAX_CACHE_SIZE:
            _ts_cache.pop(next(iter(_ts_cache)))
        _ts_cache[ts] = True

    return msg
