from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
import uvicorn
import os
from dotenv import load_dotenv
import logging
import asyncio
import json
from sqlmodel import Session, select
from database import create_db_and_tables, get_session, engine
from services import process_message
from models import Issue, Message

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="FDE Slackbot Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store connected clients (queues)
clients = []

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/")
async def root():
    return {"message": "FDE Slackbot Backend is running"}

@app.get("/issues")
async def get_issues(session: Session = Depends(get_session)):
    issues = session.exec(select(Issue)).all()
    return issues

@app.get("/issues/{issue_id}/messages")
async def get_issue_messages(issue_id: int, session: Session = Depends(get_session)):
    messages = session.exec(select(Message).where(Message.issue_id == issue_id)).all()
    return messages

@app.put("/issues/{issue_id}/resolve")
async def resolve_issue(issue_id: int, session: Session = Depends(get_session)):
    issue = session.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    issue.status = "resolved"
    session.add(issue)
    session.commit()
    session.refresh(issue)
    
    # Broadcast update
    payload = {"type": "issue_resolved", "issue_id": issue.id}
    for queue in clients:
        await queue.put(payload)
        
    return issue

@app.get("/events")
async def events():
    async def event_generator():
        queue = asyncio.Queue()
        clients.append(queue)
        try:
            while True:
                data = await queue.get()
                yield f"data: {json.dumps(data)}\n\n"
        except asyncio.CancelledError:
            clients.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Handle URL Verification
    if data.get("type") == "url_verification":
        logger.info("Received url_verification challenge")
        return {"challenge": data.get("challenge")}

    # Handle Event Callback
    if data.get("type") == "event_callback":
        event = data.get("event")
        logger.info(f"Received event: {event}")
        
        if event.get("type") == "message" and not event.get("bot_id"):
             background_tasks.add_task(process_message_task, event)
        
        return {"status": "ok"}

    return {"status": "ignored"}

async def process_message_task(event):
    # Run sync DB operation in threadpool
    def db_op():
        with Session(engine) as session:
            return process_message(session, event)
    
    msg = await run_in_threadpool(db_op)
    
    if msg:
        # Broadcast to all connected clients
        logger.info(f"Broadcasting message: {msg.id}")
        payload = {"type": "new_message", "issue_id": msg.issue_id, "message_id": msg.id}
        for queue in clients:
            await queue.put(payload)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
