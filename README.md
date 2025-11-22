# FDE Slackbot

A real-time dashboard for Forward-Deployed Engineers to track relevant customer messages from Slack.

## Setup

### Backend

1.  Navigate to `backend`:
    ```bash
    cd backend
    ```
2.  Create a virtual environment and install dependencies:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
3.  Copy `.env.example` to `.env` and fill in your keys:
    ```bash
    cp .env.example .env
    ```
4.  Run the server:
    ```bash
    uvicorn main:app --reload
    ```

### Frontend

1.  Navigate to `frontend`:
    ```bash
    cd frontend
    ```
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Run the dev server:
    ```bash
    npm run dev
    ```

### Slack Setup

1.  Create a Slack App.
2.  Enable Event Subscriptions and point to your ngrok URL + `/slack/events`.
3.  Install the app to your workspace.
