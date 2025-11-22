import os
from openai import OpenAI
from models import Message, Issue
from sqlmodel import Session, select
from datetime import datetime
import json
import numpy as np
from sentence_transformers import SentenceTransformer

# Load model once (global)
# Warning: This downloads ~80MB on first run
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

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
    # Get all open issues
    open_issues = session.exec(select(Issue).where(Issue.status == "open")).all()
    
    best_issue = None
    best_score = -1.0
    
    for issue in open_issues:
        # Get recent messages in this issue to compare against
        # For simplicity, let's compare against the *last* message in the issue
        # Better: Compare against centroid, but that requires more state.
        messages = session.exec(select(Message).where(Message.issue_id == issue.id)).all()
        if not messages:
            continue
            
        # Check similarity with messages in this issue
        for msg in messages:
            if not msg.embedding:
                continue
            
            msg_emb = np.array(json.loads(msg.embedding))
            # Cosine similarity
            score = np.dot(embedding, msg_emb) / (np.linalg.norm(embedding) * np.linalg.norm(msg_emb))
            
            if score > best_score:
                best_score = score
                best_issue = issue

    if best_score > threshold:
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
