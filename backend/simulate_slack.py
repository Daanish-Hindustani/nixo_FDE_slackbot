import requests
import time
import random
from datetime import datetime, timedelta
import json

BASE_URL = "http://localhost:8000"

# Simulated users
USERS = {
    "U001": "Alice (Engineer)",
    "U002": "Bob (Product Manager)",
    "U003": "Charlie (Designer)",
    "U004": "Diana (QA)",
    "U005": "Eve (Customer Support)"
}

# Simulated channels
CHANNELS = {
    "C001": "#engineering",
    "C002": "#product",
    "C003": "#support",
    "C004": "#general"
}

# Conversation scenarios
CONVERSATIONS = [
    {
        "name": "Bug Report - Login Issue",
        "channel": "C001",
        "messages": [
            {"user": "U004", "text": "Hey team, I'm seeing a weird issue with login. Users are getting stuck on the loading screen.", "delay": 0},
            {"user": "U001", "text": "Can you share the error logs?", "delay": 2},
            {"user": "U004", "text": "Sure, here's what I'm seeing: TypeError: Cannot read property 'token' of undefined", "delay": 3},
            {"user": "U001", "text": "Ah, looks like the auth response isn't being handled properly. I'll take a look.", "delay": 2},
            {"user": "U002", "text": "How critical is this? Should we roll back?", "delay": 1},
            {"user": "U001", "text": "It's affecting about 10% of users. I can push a fix in the next hour.", "delay": 2},
        ]
    },
    {
        "name": "Feature Request - Dark Mode",
        "channel": "C002",
        "messages": [
            {"user": "U005", "text": "We're getting a lot of requests for dark mode. Can we prioritize this?", "delay": 0},
            {"user": "U003", "text": "I actually have some designs ready. Want me to share them?", "delay": 2},
            {"user": "U002", "text": "Yes please! Let's review in our next planning meeting.", "delay": 1},
            {"user": "U003", "text": "Posted in Figma. The color palette should work well with our existing brand.", "delay": 3},
        ]
    },
    {
        "name": "Performance Issue",
        "channel": "C001",
        "messages": [
            {"user": "U001", "text": "The dashboard is loading really slowly for customers with large datasets.", "delay": 0},
            {"user": "U001", "text": "I think we need to implement pagination or virtualization.", "delay": 1},
            {"user": "U002", "text": "What's the current load time?", "delay": 2},
            {"user": "U001", "text": "About 8-10 seconds for 1000+ items. Should be under 2 seconds.", "delay": 2},
            {"user": "U004", "text": "I can help test once you have a fix ready.", "delay": 1},
        ]
    },
    {
        "name": "General Discussion",
        "channel": "C004",
        "messages": [
            {"user": "U003", "text": "Anyone want to grab lunch?", "delay": 0},
            {"user": "U005", "text": "I'm down! Thai food?", "delay": 1},
            {"user": "U003", "text": "Perfect, let's meet at noon.", "delay": 1},
        ]
    },
    {
        "name": "Customer Escalation",
        "channel": "C003",
        "messages": [
            {"user": "U005", "text": "URGENT: Customer XYZ Corp is unable to export their data. They have a deadline in 2 hours.", "delay": 0},
            {"user": "U002", "text": "On it. What's the error they're seeing?", "delay": 1},
            {"user": "U005", "text": "Export button just spins indefinitely. No error message.", "delay": 1},
            {"user": "U001", "text": "Checking the logs now. Might be a timeout issue with large exports.", "delay": 2},
            {"user": "U001", "text": "Found it - the export job is timing out after 30 seconds. Increasing the limit now.", "delay": 3},
            {"user": "U005", "text": "Thanks! I'll let the customer know.", "delay": 1},
        ]
    },
    {
        "name": "API Question",
        "channel": "C001",
        "messages": [
            {"user": "U002", "text": "Quick question - what's the rate limit on our public API?", "delay": 0},
            {"user": "U001", "text": "It's 100 requests per minute per API key.", "delay": 2},
            {"user": "U002", "text": "Got it, thanks!", "delay": 1},
        ]
    },
    {
        "name": "Database Migration Issue",
        "channel": "C001",
        "messages": [
            {"user": "U001", "text": "The database migration failed in staging. Getting a foreign key constraint error.", "delay": 0},
            {"user": "U001", "text": "Error: FOREIGN KEY constraint failed on table 'users'", "delay": 1},
            {"user": "U004", "text": "Did you run the migrations in order?", "delay": 2},
            {"user": "U001", "text": "Yeah, but I think there's orphaned data from the old schema. Let me clean that up first.", "delay": 2},
            {"user": "U001", "text": "Fixed! The issue was some test data that wasn't properly cleaned up.", "delay": 4},
        ]
    },
]

def send_slack_event(channel_id: str, user_id: str, text: str, ts: str = None):
    """Send a simulated Slack message event to the backend."""
    if ts is None:
        ts = str(time.time())
    
    event = {
        "type": "event_callback",
        "event": {
            "type": "message",
            "channel": channel_id,
            "user": user_id,
            "text": text,
            "ts": ts,
            "event_ts": ts
        }
    }
    
    try:
        response = requests.post(f"{BASE_URL}/slack/events", json=event)
        if response.status_code == 200:
            print(f"✓ [{CHANNELS.get(channel_id, channel_id)}] {USERS.get(user_id, user_id)}: {text[:50]}...")
        else:
            print(f"✗ Error {response.status_code}: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to send message: {e}")

def simulate_conversation(conversation: dict, delay_multiplier: float = 1.0):
    print(f"\n{'='*80}")
    print(f"Starting conversation: {conversation['name']}")
    print(f"Channel: {CHANNELS.get(conversation['channel'], conversation['channel'])}")
    print(f"{'='*80}\n")
    
    base_ts = time.time()
    
    for i, msg in enumerate(conversation['messages']):
        actual_delay = msg['delay'] * delay_multiplier * random.uniform(0.8, 1.2)
        time.sleep(actual_delay)
        
        ts = str(base_ts + sum(m['delay'] for m in conversation['messages'][:i+1]))
        
        send_slack_event(
            channel_id=conversation['channel'],
            user_id=msg['user'],
            text=msg['text'],
            ts=ts
        )
    
    print(f"\n✓ Conversation '{conversation['name']}' completed!\n")

def simulate_all_conversations(delay_multiplier: float = 1.0, pause_between: float = 3.0):
    """Simulate all predefined conversations."""
    print("\n" + "="*80)
    print("SLACK CONVERSATION SIMULATOR")
    print("="*80)
    print(f"\nSimulating {len(CONVERSATIONS)} conversations...")
    print(f"Delay multiplier: {delay_multiplier}x")
    print(f"Pause between conversations: {pause_between}s\n")
    
    for i, conversation in enumerate(CONVERSATIONS):
        simulate_conversation(conversation, delay_multiplier)
        
        if i < len(CONVERSATIONS) - 1:
            print(f"Waiting {pause_between}s before next conversation...\n")
            time.sleep(pause_between)
    
    print("\n" + "="*80)
    print("ALL CONVERSATIONS COMPLETED!")
    print("="*80)
    print(f"\nTotal conversations: {len(CONVERSATIONS)}")
    print(f"Total messages: {sum(len(c['messages']) for c in CONVERSATIONS)}")
    print("\nCheck your dashboard to see the results!")

def simulate_random_conversation():
    """Simulate a single random conversation."""
    conversation = random.choice(CONVERSATIONS)
    simulate_conversation(conversation, delay_multiplier=0.5)

def interactive_mode():
    """Interactive mode for custom message sending."""
    print("\n" + "="*80)
    print("INTERACTIVE MODE")
    print("="*80)
    print("\nAvailable channels:")
    for channel_id, channel_name in CHANNELS.items():
        print(f"  {channel_id}: {channel_name}")
    
    print("\nAvailable users:")
    for user_id, user_name in USERS.items():
        print(f"  {user_id}: {user_name}")
    
    print("\nType 'quit' to exit\n")
    
    while True:
        try:
            channel = input("Channel ID (or 'quit'): ").strip()
            if channel.lower() == 'quit':
                break
            
            user = input("User ID: ").strip()
            text = input("Message text: ").strip()
            
            if channel and user and text:
                send_slack_event(channel, user, text)
            else:
                print("All fields are required!")
        except KeyboardInterrupt:
            print("\n\nExiting interactive mode...")
            break

def main():
    """Main entry point with menu."""
    import sys
    
    print("\n" + "="*80)
    print("SLACK CONVERSATION SIMULATOR")
    print("="*80)
    print("\nOptions:")
    print("  1. Simulate all conversations (fast - 0.5x speed)")
    print("  2. Simulate all conversations (normal - 1x speed)")
    print("  3. Simulate all conversations (slow - 2x speed)")
    print("  4. Simulate random conversation")
    print("  5. Interactive mode (send custom messages)")
    print("  6. Exit")
    
    choice = input("\nSelect an option (1-6): ").strip()
    
    if choice == "1":
        simulate_all_conversations(delay_multiplier=0.5, pause_between=2.0)
    elif choice == "2":
        simulate_all_conversations(delay_multiplier=1.0, pause_between=3.0)
    elif choice == "3":
        simulate_all_conversations(delay_multiplier=2.0, pause_between=5.0)
    elif choice == "4":
        simulate_random_conversation()
    elif choice == "5":
        interactive_mode()
    elif choice == "6":
        print("Goodbye!")
        sys.exit(0)
    else:
        print("Invalid option!")

if __name__ == "__main__":
    main()
