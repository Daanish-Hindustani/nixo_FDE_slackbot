# FDE Slackbot

A real-time dashboard for Forward-Deployed Engineers to track and manage relevant customer messages from Slack. The system automatically classifies messages, groups related conversations, and provides a clean interface for monitoring issues.

## Demo

Watch the system in action:

[![FDE Slackbot Demo](https://img.youtube.com/vi/lPOSFj8ePfs/0.jpg)](https://youtu.be/lPOSFj8ePfs)

**[▶️ Watch Demo Video](https://youtu.be/lPOSFj8ePfs)**

The demo shows:
- Real-time message classification and filtering
- Automatic grouping of related messages into issues
- Dashboard interface for monitoring and resolving issues
- Seamless integration with Slack conversations

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Quick Start](#quick-start)
- [Database Setup](#database-setup)
- [Environment Variables](#environment-variables)
- [Slack App Setup](#slack-app-setup)
- [Testing with Simulated Conversations](#testing-with-simulated-conversations)
- [Troubleshooting](#troubleshooting)

## Architecture Overview

📖 **[View Detailed Architecture Documentation](https://docs.google.com/document/d/12DZ9r9s0F-DMmN7_Pb-R7DB9M3qnOnwKmT1m7avKjds/edit?usp=sharing)**

### Components

- **Backend (FastAPI)**: Handles Slack events, message classification, and real-time updates
- **Frontend (React + Vite)**: Dashboard UI for viewing and managing issues
- **Database (SQLite)**: Stores messages, issues, and classifications
- **OpenAI API**: Classifies messages and generates embeddings for similarity matching
- **Sentence Transformers**: Local embeddings for message grouping

### Data Flow

1. Slack sends message events to the backend via webhook
2. Backend classifies messages using OpenAI and filters irrelevant ones
3. Messages are grouped into issues using semantic similarity
4. Frontend receives real-time updates via Server-Sent Events (SSE)
5. FDEs can view and resolve issues through the dashboard

### Database Schema

**Issue Table:**
- `id`: Primary key
- `title`: Auto-generated issue title
- `summary`: Brief description of the issue
- `classification`: Type of issue (bug, feature_request, question, etc.)
- `status`: open/resolved
- `created_at`, `updated_at`: Timestamps

**Message Table:**
- `id`: Primary key
- `slack_ts`: Unique Slack timestamp
- `channel_id`: Slack channel ID
- `user_id`: Slack user ID
- `text`: Message content
- `classification`: Message type
- `confidence`: Classification confidence score
- `is_relevant`: Whether message is relevant to FDEs
- `embedding`: Vector embedding for similarity matching
- `issue_id`: Foreign key to Issue table

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+
- OpenAI API key
- Slack workspace (for production use)

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your API keys (see [Environment Variables](#environment-variables))

5. Start the backend server:
   ```bash
   uvicorn main:app --reload
   ```

   The server will start on `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

   The frontend will start on `http://localhost:5173`

## Database Setup

### Automatic Initialization

The database is automatically created when you first start the backend server. The `create_db_and_tables()` function in `main.py` handles this during the startup event.

**What happens:**
1. SQLModel creates `database.db` in the `backend/` directory
2. Tables are created based on models in `models.py`
3. All necessary indexes and foreign keys are set up

### Manual Database Reset

If you need to reset the database:

```bash
cd backend
rm database.db
uvicorn main:app --reload 
```

### Database Location

The SQLite database file is located at:
```
backend/database.db
```

### Inspecting the Database

You can inspect the database using any SQLite client:

```bash
sqlite3 backend/database.db
```

Common queries:
```sql
-- View all issues
SELECT * FROM issue;

-- View all messages
SELECT * FROM message;

-- View messages for a specific issue
SELECT * FROM message WHERE issue_id = 1;

-- Count messages by classification
SELECT classification, COUNT(*) FROM message GROUP BY classification;
```

### Database Management Script

A convenient `db_manager.py` script is provided for common database operations:

```bash
cd backend
python db_manager.py
```

**Available options:**
1. **Initialize database** - First time setup (creates tables)
2. **Reset database** - Delete all data and recreate tables
3. **Show statistics** - View counts of issues, messages, and classifications
4. **List all issues** - Display all issues with details
5. **List all messages** - Display all messages
6. **List messages for specific issue** - View messages grouped by issue

This script is useful for:
- Quick database inspection without SQL
- Resetting the database during development
- Viewing statistics and debugging data issues

## Environment Variables

Create a `.env` file in the `backend/` directory with the following variables:

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key for message classification and embeddings | `sk-proj-abc123...` |
| `SLACK_BOT_TOKEN` | Slack Bot User OAuth Token (starts with `xoxb-`) | `xoxb-1234567890...` |
| `SLACK_SIGNING_SECRET` | Slack app signing secret for request verification | `a1b2c3d4e5f6...` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLite database path | `sqlite:///database.db` |

### Getting API Keys

**OpenAI API Key:**
1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign in or create an account
3. Navigate to API Keys
4. Create a new secret key

**Slack Tokens:**
See [Slack App Setup](#slack-app-setup) section below.

## Slack App Setup

### Option 1: Using App Manifest (Recommended)

1. **Create App from Manifest:**
   - Go to [Your Apps](https://api.slack.com/apps)
   - Click "Create New App"
   - Select "From an app manifest"
   - Choose your workspace
   - Copy the contents of `slack_manifest.json`
   - **Important:** Replace `{ngrok_url}` with your actual ngrok URL (see step 4)
   - Paste into the JSON editor and click "Create"

2. **Install the App:**
   - In the app settings, go to "Install App"
   - Click "Install to Workspace"
   - Authorize the requested permissions

3. **Get Your Tokens:**
   - **Bot Token:** Go to "OAuth & Permissions" → Copy "Bot User OAuth Token" (starts with `xoxb-`)
   - **Signing Secret:** Go to "Basic Information" → Copy "Signing Secret"
   - Add both to your `backend/.env` file

4. **Set Up Ngrok (for local development):**
   ```bash
   ngrok http 8000
   ```
   
   - Copy the HTTPS URL (e.g., `https://abc123.ngrok-free.app`)
   - Go to "Event Subscriptions" in your Slack app settings
   - Enable events and set Request URL to: `https://abc123.ngrok-free.app/slack/events`
   - Slack will verify the URL (make sure your backend is running!)

### Option 2: Manual Setup

If you prefer to set up the app manually:

1. Create a new Slack app at [api.slack.com/apps](https://api.slack.com/apps)
2. Add the following **Bot Token Scopes** under "OAuth & Permissions":
   - `channels:history`
   - `groups:history`
   - `im:history`
   - `mpim:history`
   - `chat:write`
   - `app_mentions:read`
   - `users:read`
   - `channels:read`
   - `groups:read`

3. Enable **Event Subscriptions** and subscribe to:
   - `message.channels`
   - `message.groups`
   - `message.im`
   - `message.mpim`
   - `app_mention`

4. Install the app to your workspace and get the tokens

### Verifying the Setup

Once configured, send a test message in a Slack channel where the bot is added. You should see:
- Backend logs showing the received event
- Message appearing in the dashboard (if classified as relevant)

## Testing with Simulated Conversations

The `simulate_slack.py` script allows you to test the system without a real Slack workspace.

### Running the Simulator

```bash
cd backend
python simulate_slack.py
```

### Simulator Options

The script provides an interactive menu:

1. **Simulate all conversations (fast - 0.5x speed)**
   - Runs all 7 predefined conversations quickly
   - Good for initial testing

2. **Simulate all conversations (normal - 1x speed)**
   - Runs conversations at realistic timing
   - Best for demo purposes

3. **Simulate all conversations (slow - 2x speed)**
   - Slower pace for detailed observation
   - Useful for debugging

4. **Simulate random conversation**
   - Picks one random conversation to simulate
   - Quick testing of specific scenarios

5. **Interactive mode**
   - Send custom messages manually
   - Full control over channel, user, and message content

6. **Exit**

### Predefined Conversation Scenarios

The simulator includes 7 realistic scenarios:

1. **Bug Report - Login Issue**: Multi-user debugging conversation
2. **Feature Request - Dark Mode**: Product discussion
3. **Performance Issue**: Technical performance investigation
4. **General Discussion**: Non-relevant casual chat (should be filtered)
5. **Customer Escalation**: Urgent customer issue
6. **API Question**: Quick technical question
7. **Database Migration Issue**: Technical problem-solving

### Simulated Users and Channels

**Users:**
- `U001`: Alice (Engineer)
- `U002`: Bob (Product Manager)
- `U003`: Charlie (Designer)
- `U004`: Diana (QA)
- `U005`: Eve (Customer Support)

**Channels:**
- `C001`: #engineering
- `C002`: #product
- `C003`: #support
- `C004`: #general

### How the Simulator Works

1. Sends POST requests to `http://localhost:8000/slack/events`
2. Mimics Slack's event payload structure
3. Includes realistic timing delays between messages
4. Uses actual Slack timestamp format

### Example: Interactive Mode

```bash
$ python simulate_slack.py
# Select option 5

Channel ID (or 'quit'): C001
User ID: U001
Message text: We have a critical bug in production!

✓ [#engineering] Alice (Engineer): We have a critical bug in production!...
```

## Manual Testing in Slack

Once you have your Slack app set up and the backend running with ngrok, you can test the bot with real Slack messages.

### Prerequisites

1. Backend server running (`uvicorn main:app --reload`)
2. Ngrok forwarding to port 8000 (`ngrok http 8000`)
3. Slack app configured with ngrok URL
4. Frontend running (`npm run dev`) to view the dashboard

### Step 1: Invite the Bot to a Channel

**This is a critical step!** The bot can only see messages in channels where it has been invited.

To invite the bot to a channel:

1. Open the Slack channel where you want to test
2. Type `/invite @your-bot-name` (replace with your actual bot name)
3. Press Enter to send the command
4. You should see a message confirming the bot was added to the channel

**Alternative method:**
- Click the channel name at the top
- Go to "Integrations" tab
- Click "Add apps"
- Search for your bot and click "Add"

### Step 2: Send Test Messages

Once the bot is in the channel, send messages that should trigger classification:

**Bug Report Example:**
```
Hey team, users are reporting that the login page is broken. Getting a 500 error when trying to sign in.
```

**Feature Request Example:**
```
Would be great if we could add dark mode to the dashboard. Several customers have requested this.
```

**Question Example:**
```
Does anyone know how to configure the API rate limits?
```

**General Chat (should be filtered):**
```
Anyone want to grab lunch?
```

### Step 3: Verify in Dashboard

1. Open the dashboard at `http://localhost:5173`
2. Check that relevant messages appear in the "All Issues" tab
3. Verify that messages are properly classified (bug, feature_request, question, etc.)
4. Confirm that related messages are grouped into the same issue

### Step 4: Check Backend Logs

Monitor the backend terminal for processing logs:

```
INFO:     Received Slack event: message
INFO:     Processing message from user U12345 in channel C67890
INFO:     Message classified as: bug (confidence: 0.95)
INFO:     Message is relevant: True
INFO:     Grouped into issue: 1
```

### Testing Different Scenarios

**Test Message Grouping:**
1. Send a bug report: "Login is broken"
2. Wait a few seconds
3. Send a follow-up: "Still seeing the login error, tried clearing cache"
4. Both messages should appear under the same issue in the dashboard

**Test Filtering:**
1. Send irrelevant messages (casual chat, off-topic)
2. These should NOT appear in the dashboard
3. Check backend logs to confirm they were filtered

**Test Multiple Channels:**
1. Invite the bot to multiple channels
2. Send messages in different channels
3. Verify all relevant messages appear in the dashboard

### Important Notes

- **Bot must be invited to each channel** - It cannot see messages in channels where it hasn't been added
- **Direct messages work automatically** - No need to invite for DMs
- **Private channels** - Bot needs to be explicitly invited to private channels
- **Message history** - Bot only sees new messages sent after it joins a channel

### Troubleshooting Manual Testing

**Messages not appearing in dashboard:**
- Verify bot is in the channel (`/invite @bot-name`)
- Check backend logs for incoming events
- Ensure message isn't being filtered as irrelevant
- Verify ngrok URL is still active (ngrok URLs expire)

**Bot not responding:**
- Check that backend server is running
- Verify ngrok is forwarding correctly
- Ensure Event Subscriptions URL is verified in Slack app settings
- Check `.env` file has correct `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET`

**Classification seems wrong:**
- OpenAI API may need better prompts (check `services.py`)
- Try more explicit language in test messages
- Check confidence scores in backend logs

## Troubleshooting

### Backend Issues

**Error: "Address already in use"**
```bash
# Find and kill the process using port 8000
lsof -ti:8000 | xargs kill -9

# Or use a different port
uvicorn main:app --reload --port 8001
```

**Error: "No module named 'X'"**
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

**Error: "OPENAI_API_KEY not found"**
- Check that `.env` file exists in `backend/` directory
- Verify the variable name is exactly `OPENAI_API_KEY`
- Ensure no extra spaces around the `=` sign

**Database errors**
```bash
# Reset the database
cd backend
rm database.db
uvicorn main:app --reload
```

### Frontend Issues

**Error: "Failed to fetch"**
- Ensure backend is running on `http://localhost:8000`
- Check browser console for CORS errors
- Verify the API URL in frontend code

**Blank dashboard**
- Check that messages are being sent (use simulator)
- Open browser DevTools → Network tab to see SSE connection
- Verify backend logs show message processing

### Slack Integration Issues

**Event URL verification fails**
- Ensure backend is running before verifying URL
- Check that ngrok is forwarding to port 8000
- Verify the URL format: `https://your-id.ngrok-free.app/slack/events`

**Messages not appearing**
- Verify bot is added to the channel (`/invite @bot-name`)
- Check backend logs for incoming events
- Ensure message isn't being filtered as irrelevant

**"Invalid token" errors**
- Verify `SLACK_BOT_TOKEN` starts with `xoxb-`
- Check token hasn't been revoked in Slack app settings
- Ensure `.env` file is in the correct location

### General Tips

- **Check logs**: Backend logs provide detailed information about message processing
- **Use the simulator**: Test without Slack to isolate issues
- **Inspect database**: Use SQLite browser to verify data is being stored
- **Browser DevTools**: Check Network tab for API calls and SSE connection
- **Restart services**: Sometimes a simple restart fixes connection issues

### Getting Help

If you encounter issues not covered here:
1. Check backend logs for error messages
2. Verify all environment variables are set correctly
3. Test with the simulator to rule out Slack-specific issues
4. Inspect the database to see if data is being stored
