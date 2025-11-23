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

1.  **Create App from Manifest:**
    - Go to [Your Apps](https://api.slack.com/apps).
    - Click "Create New App".
    - Select "From an app manifest".
    - Select your workspace.
    - Copy the contents of `slack_manifest.json` (update ngrok url) and paste them into the YAML/JSON editor.
    - Click "Create".

2.  **Install App:**
    - Navigate to "Install App" in the sidebar.
    - Click "Install to Workspace".
    - Authorize the app.

3.  **Environment Variables:**
    - Copy the "Bot User OAuth Token" (starts with `xoxb-`) and set it as `SLACK_BOT_TOKEN` in `backend/.env`.
    - Go to "Basic Information" -> "App-Level Tokens".
    - Generate a token with `connections:write` scope (if using Socket Mode) or just use the "Signing Secret" if using HTTP.
    - *Note:* This app is configured for HTTP (Event Subscriptions).
    - Ensure `OPENAI_API_KEY` is set in `backend/.env`.

4.  **Ngrok Setup:**
    - Start ngrok: `ngrok http 8000`.
    - Copy the HTTPS URL (e.g., `https://your-id.ngrok-free.app`).
    - Go to "Event Subscriptions" in your Slack App settings.
    - Update the "Request URL" to `https://your-id.ngrok-free.app/slack/events`.
    - It should verify successfully.
