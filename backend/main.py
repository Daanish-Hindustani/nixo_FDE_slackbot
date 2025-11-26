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

clients = []

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/")
async def root():
    return {"message": "FDE Slackbot Backend is running"}

@app.get("/issues")
async def get_issues(session: Session = Depends(get_session)):
    return session.exec(select(Issue)).all()

@app.get("/issues/{issue_id}/messages")
async def get_issue_messages(issue_id: int, session: Session = Depends(get_session)):
    return session.exec(select(Message).where(Message.issue_id == issue_id)).all()

@app.put("/issues/{issue_id}/resolve")
async def resolve_issue(issue_id: int, session: Session = Depends(get_session)):
    issue = session.get(Issue, issue_id)

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    issue.status = "resolved"
    session.add(issue)
    session.commit()
    session.refresh(issue)

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
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if data.get("type") == "url_verification":
        logger.info("Received Slack challenge event")
        return {"challenge": data.get("challenge")}

    if data.get("type") == "event_callback":
        event = data.get("event")
        logger.info(f"Received Slack event: {event}")

        # Ignore bot messages to prevent loops
        if event.get("type") == "message" and not event.get("bot_id"):
            background_tasks.add_task(process_message_task, event)

        return {"status": "ok"}

    return {"status": "ignored"}

async def process_message_task(event):
    def db_op():
        with Session(engine) as session:
            msg = process_message(session, event)
            if msg:
                # Extract data while still in session to avoid DetachedInstanceError
                return {
                    "id": msg.id,
                    "issue_id": msg.issue_id
                }
            return None

    msg_data = await run_in_threadpool(db_op)

    if msg_data:
        logger.info(f"Broadcasting new message: {msg_data['id']}")
        payload = {
            "type": "new_message",
            "issue_id": msg_data["issue_id"],
            "message_id": msg_data["id"],
        }
        for queue in clients:
            await queue.put(payload)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
