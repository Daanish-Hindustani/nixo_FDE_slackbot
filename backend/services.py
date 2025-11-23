import os
from threading import Lock
from openai import OpenAI
from models import Message, Issue
from sqlmodel import Session, select
from datetime import datetime
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
from typing import Optional, List, Dict, Tuple

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

EMBEDDING_DIM = 384

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

import logging

logger = logging.getLogger(__name__)

def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

def classify_message(text: str):
    client = get_openai_client()
    
    if not client:
        logger.warning("No OpenAI API Key found. Skipping classification.")
        return {"label": "irrelevant", "is_relevant": False, "confidence": 0.0}

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"Error classifying message: {e}")
        return {"label": "irrelevant", "is_relevant": False, "confidence": 0.0}

def get_embedding(text: str):
    return embedding_model.encode(text)

def format_embedding_text(text: str, user: str, channel: str, timestamp: str = "") -> str:
    """Format text for embedding with metadata including channel, user, timestamp, and message text."""
    time_str = f" Time: {timestamp}" if timestamp else ""
    return f"Channel: {channel} User: {user}{time_str} Text: {text}"

class VectorStore:
    def __init__(self, session: Session):
        self.index = faiss.IndexFlatIP(EMBEDDING_DIM)
        self.issue_map: Dict[int, int] = {}  # Maps vector index to issue_id
        self.issue_timestamps: Dict[int, datetime] = {}  # Maps issue_id to updated_at timestamp
        self.current_id = 0
        self._load_from_db(session)

    def _load_from_db(self, session: Session):
        issues = session.exec(select(Issue).where(Issue.embedding != None)).all()
        logger.info(f"Loading {len(issues)} issues into vector store")
        
        vectors = []
        ids = []
        for issue in issues:
            try:
                vec = np.array(json.loads(issue.embedding)).astype("float32")
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec /= norm
                    vectors.append(vec)
                    ids.append(issue.id)
                    self.issue_timestamps[issue.id] = issue.updated_at
            except Exception as e:
                logger.error(f"Error loading embedding for issue {issue.id}: {e}")
                continue
        
        if vectors:
            self.index.add(np.stack(vectors))
            for i, issue_id in enumerate(ids):
                self.issue_map[self.current_id + i] = issue_id
            self.current_id += len(vectors)

    def search(self, embedding: np.ndarray, threshold: float = 0.70, 
               query_timestamp: Optional[datetime] = None, 
               temporal_weight: float = 0.3,
               time_decay_hours: float = 24.0) -> Tuple[Optional[int], float]:
        """
        Search for similar issues with temporal weighting.
        
        Args:
            embedding: Query embedding vector
            threshold: Minimum combined score threshold
            query_timestamp: Timestamp of the query message
            temporal_weight: Weight for temporal similarity (0-1), remaining weight goes to semantic similarity
            time_decay_hours: Half-life for temporal decay in hours
        
        Returns:
            Tuple of (issue_id, combined_score) or (None, 0.0)
        """
        if self.index.ntotal == 0:
            return None, 0.0
        
        query = embedding.astype("float32")
        q_norm = np.linalg.norm(query)
        if q_norm == 0:
            return None, 0.0
        query /= q_norm
        
        # Get top K candidates for temporal reranking
        k = min(5, self.index.ntotal)
        distances, indices = self.index.search(query[None, :], k)
        
        best_issue_id = None
        best_combined_score = 0.0
        
        for i in range(k):
            idx = int(indices[0][i])
            semantic_score = float(distances[0][i])
            
            if idx == -1 or idx not in self.issue_map:
                continue
            
            issue_id = self.issue_map[idx]
            
            # Calculate temporal score if timestamp is provided
            if query_timestamp and issue_id in self.issue_timestamps:
                issue_time = self.issue_timestamps[issue_id]
                time_diff_hours = abs((query_timestamp - issue_time).total_seconds()) / 3600.0
                
                # Exponential decay: score = exp(-ln(2) * time_diff / half_life)
                temporal_score = np.exp(-0.693147 * time_diff_hours / time_decay_hours)
                
                # Combine semantic and temporal scores
                combined_score = (1 - temporal_weight) * semantic_score + temporal_weight * temporal_score
            else:
                # No temporal weighting, use semantic score only
                combined_score = semantic_score
            
            if combined_score > best_combined_score:
                best_combined_score = combined_score
                best_issue_id = issue_id
        
        if best_issue_id and best_combined_score > threshold:
            return best_issue_id, best_combined_score
        return None, 0.0

    def add_issue(self, issue_id: int, embedding: np.ndarray, timestamp: Optional[datetime] = None):
        """Add a new issue to the vector store with optional timestamp."""
        vec = embedding.astype("float32")
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
            self.index.add(vec[None, :])
            self.issue_map[self.current_id] = issue_id
            if timestamp:
                self.issue_timestamps[issue_id] = timestamp
            self.current_id += 1

_vector_store: Optional[VectorStore] = None

def get_vector_store(session: Session) -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(session)
    return _vector_store

def update_issue_centroid(session: Session, issue_id: int):
    msgs = session.exec(select(Message).where(Message.issue_id == issue_id)).all()
    if not msgs:
        return None
    
    vectors = []
    for msg in msgs:
        if msg.embedding:
            try:
                v = np.array(json.loads(msg.embedding))
                vectors.append(v)
            except:
                pass
    
    if not vectors:
        return None
    
    centroid = np.mean(vectors, axis=0)
    return centroid


_ts_cache = {}
MAX_CACHE_SIZE = 10000
_ts_cache_lock = Lock()

def process_message(session: Session, slack_event: dict):
    text = slack_event.get("text", "")
    user = slack_event.get("user")
    ts = slack_event.get("ts")
    channel = slack_event.get("channel")
    thread_ts = slack_event.get("thread_ts")
    
    with _ts_cache_lock:
        if ts in _ts_cache:
            _ts_cache[ts] = _ts_cache.pop(ts)
            return None

    existing = session.exec(select(Message).where(Message.slack_ts == ts)).first()
    if existing:
        with _ts_cache_lock:
            if len(_ts_cache) >= MAX_CACHE_SIZE:
                _ts_cache.pop(next(iter(_ts_cache)))
            _ts_cache[ts] = True
        return None

    classification = classify_message(text)
    
    if not classification["is_relevant"]:
        return None

    embedding_text = format_embedding_text(text, user, str(channel), ts)
    embedding_vec = get_embedding(embedding_text)
    embedding_json = json.dumps(embedding_vec.tolist())

    issue = None
    
    # If this message is in a thread, try to find the parent message and use its issue
    if thread_ts:
        parent_msg = session.exec(select(Message).where(Message.slack_ts == thread_ts)).first()
        if parent_msg and parent_msg.issue_id:
            issue = session.get(Issue, parent_msg.issue_id)
            logger.info(f"Thread message detected - grouping with parent issue '{issue.title}'")
    
    # If not in a thread or parent not found, use similarity search
    if not issue:
        vector_store = get_vector_store(session)
        msg_timestamp = datetime.fromtimestamp(float(ts))
        issue_id, score = vector_store.search(
            embedding_vec, 
            threshold=0.70,
            query_timestamp=msg_timestamp,
            temporal_weight=0.3,  # 30% weight on time, 70% on semantic similarity
            time_decay_hours=24.0  # Messages within 24 hours get higher temporal scores
        )
        
        if issue_id:
            issue = session.get(Issue, issue_id)

        if issue:
            logger.info(f"Grouping with existing issue '{issue.title}' (Score: {score:.2f})")
            if getattr(issue, "status", None) == "closed":
                issue.status = "open"
            if not issue.classification or (classification["confidence"] > 0.8):
                 issue.classification = classification["label"]
            issue.updated_at = datetime.utcnow()
            session.add(issue)
            session.commit()
        else:
            logger.info("Creating new issue")
            issue = Issue(
                title=classification.get("summary", text[:50]),
                summary=classification.get("summary"),
                classification=classification["label"],
                updated_at=datetime.utcnow()
            )
            session.add(issue)
            session.commit()
            session.refresh(issue)
    else:
        # Update existing issue from thread
        if getattr(issue, "status", None) == "closed":
            issue.status = "open"
        issue.updated_at = datetime.utcnow()
        session.add(issue)
        session.commit()
    
    msg = Message(
        slack_ts=ts,
        thread_ts=thread_ts,
        channel_id=channel,
        user_id=user,
        text=text,
        timestamp=datetime.fromtimestamp(float(ts)),
        classification=classification["label"],
        confidence=classification["confidence"],
        is_relevant=True,
        issue_id=issue.id,
        embedding=embedding_json
    )
    session.add(msg)
    session.commit()
    session.refresh(msg)

    new_centroid = update_issue_centroid(session, issue.id)
    if new_centroid is not None:
        issue.embedding = json.dumps(new_centroid.tolist())
        session.add(issue)
        session.commit()
        vector_store.add_issue(issue.id, new_centroid, issue.updated_at)
        session.refresh(msg)
    
    with _ts_cache_lock:
        if len(_ts_cache) >= MAX_CACHE_SIZE:
            _ts_cache.pop(next(iter(_ts_cache)))
        _ts_cache[ts] = True
    
    return msg
