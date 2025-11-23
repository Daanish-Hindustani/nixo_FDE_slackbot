import os
from openai import OpenAI
from models import Message, Issue
from sqlmodel import Session, select
from datetime import datetime
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

# Load model once (global)
# Warning: This downloads ~80MB on first run
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# ANN configuration
EMBEDDING_DIM = 384  # dimension of the MiniLM embeddings

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

def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

def classify_message(text: str):
    client = get_openai_client()
    
    if not client:
        print("⚠️ No OpenAI API Key found. Using mock classification.")
        # Mock logic for testing
        lower_text = text.lower()
        if "bug" in lower_text or "crash" in lower_text or "error" in lower_text:
            return {"label": "bug_report", "is_relevant": True, "confidence": 0.9, "summary": f"Bug: {text[:30]}..."}
        elif "help" in lower_text or "how" in lower_text:
            return {"label": "support_question", "is_relevant": True, "confidence": 0.8, "summary": f"Support: {text[:30]}..."}
        elif "feature" in lower_text or "add" in lower_text:
             return {"label": "feature_request", "is_relevant": True, "confidence": 0.8, "summary": f"Feature: {text[:30]}..."}
        else:
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
        print(f"Error classifying message: {e}")
        return {"label": "irrelevant", "is_relevant": False, "confidence": 0.0}

def get_embedding(text: str):
    return embedding_model.encode(text)


def find_similar_issue(session: Session, embedding: np.ndarray, threshold: float = 0.7):
    """Find the most similar Issue (open *or* closed) using FAISS ANN.

    The function builds a temporary FAISS index from the latest embedding of each
    issue, regardless of its status, and performs a single nearest‑neighbor search.
    It returns the best matching Issue and its cosine similarity score (or
    ``None, 0.0`` if no match exceeds the threshold).
    """
    # Gather the latest embedding for each issue (open or closed)
    all_issues = session.exec(select(Issue)).all()
    vectors = []
    issue_ids = []
    for issue in all_issues:
        # Get the most recent message with an embedding for this issue
        msg = session.exec(
            select(Message.embedding)
            .where(Message.issue_id == issue.id)
            .order_by(Message.timestamp.desc())
        ).first()
        if not msg:
            continue
        # Load and normalize the embedding
        try:
            vec = np.array(json.loads(msg)).astype("float32")
        except (json.JSONDecodeError, TypeError):
             continue
             
        norm = np.linalg.norm(vec)
        if norm == 0:
            continue
        vec /= norm
        vectors.append(vec)
        issue_ids.append(issue.id)

    if not vectors:
        return None, 0.0

    # Build FAISS inner‑product index (cosine similarity when vectors are normalized)
    index = faiss.IndexFlatIP(EMBEDDING_DIM)
    index.add(np.stack(vectors))

    # Prepare query embedding
    query = embedding.astype("float32")
    q_norm = np.linalg.norm(query)
    if q_norm == 0:
        return None, 0.0
    query /= q_norm

    # Search for the nearest neighbour (k=1)
    distances, indices = index.search(query[None, :], 1)
    best_idx = int(indices[0][0])
    best_score = float(distances[0][0])

    if best_score > threshold:
        best_issue_id = issue_ids[best_idx]
        best_issue = session.get(Issue, best_issue_id)
        return best_issue, best_score
    return None, 0.0

def process_message(session: Session, slack_event: dict):
    text = slack_event.get("text", "")
    user = slack_event.get("user")
    ts = slack_event.get("ts")
    channel = slack_event.get("channel")
    
    # De-duplication
    existing = session.exec(select(Message).where(Message.slack_ts == ts)).first()
    if existing:
        return None

    classification = classify_message(text)
    
    if not classification["is_relevant"]:
        return None

    # Generate embedding
    embedding_vec = get_embedding(text)
    embedding_json = json.dumps(embedding_vec.tolist())

    # Clustering Logic
    issue, score = find_similar_issue(session, embedding_vec)
    
    if issue:
        print(f"🔗 Grouping with existing issue '{issue.title}' (Score: {score:.2f})")
        # Auto‑reopen if the issue is closed
        if getattr(issue, "status", None) == "closed":
            issue.status = "open"
        issue.updated_at = datetime.utcnow()
        session.add(issue)
        session.commit()
    else:
        print("🆕 Creating new issue")
        issue = Issue(
            title=classification.get("summary", text[:50]),
            summary=classification.get("summary"),
            updated_at=datetime.utcnow()
        )
        session.add(issue)
        session.commit()
        session.refresh(issue)
    
    msg = Message(
        slack_ts=ts,
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
    
    return msg
