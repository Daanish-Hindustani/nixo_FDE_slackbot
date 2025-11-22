import requests
import time
import json

def test_e2e_flow():
    # 1. Simulate Slack Event
    url = "http://localhost:8000/slack/events"
    ts = str(time.time())
    payload = {
        "token": "Jhj5dZrVaK7ZwHHjRyZWjbDl",
        "team_id": "T061EG9R6",
        "api_app_id": "A061EG9R6",
        "event": {
            "type": "message",
            "user": "U061F7AUR",
            "text": "I found a bug in the login page. It crashes when I click submit.",
            "ts": ts,
            "channel": "C061EG9SL",
            "event_ts": ts,
            "channel_type": "channel"
        },
        "type": "event_callback",
        "event_id": f"Ev{ts}",
        "event_time": int(time.time())
    }
    
    print(f"Sending event with ts={ts}...")
    try:
        response = requests.post(url, json=payload)
        print(f"Slack Event Response: {response.status_code} {response.json()}")
    except Exception as e:
        print(f"Failed to send event: {e}")
        return

    # 2. Wait for processing (async)
    print("Waiting for processing...")
    time.sleep(2)

    # 3. Check Issues API
    try:
        res = requests.get("http://localhost:8000/issues")
        issues = res.json()
        print(f"Issues response: {issues}")
        print(f"Found {len(issues)} issues.")
        
        found = False
        for issue in issues:
            # Check messages for this issue
            # SQLModel might return dicts or objects depending on serialization
            issue_id = issue.get('id') if isinstance(issue, dict) else issue
            
            msg_res = requests.get(f"http://localhost:8000/issues/{issue_id}/messages")
            messages = msg_res.json()
            for msg in messages:
                if msg['slack_ts'] == ts:
                    print("✅ Message found in DB and linked to issue!")
                    print(f"   Issue Title: {issue.get('title')}")
                    print(f"   Classification: {msg['classification']}")
                    found = True
                    if found: break
        
        if not found:
            print("❌ Message not found in DB.")
            
        # 4. Test Clustering (Send similar message)
        print("\nTesting Clustering...")
        ts2 = str(float(ts) + 10)
        payload2 = payload.copy()
        payload2["event"]["ts"] = ts2
        payload2["event"]["text"] = "Login is broken. It crashes on submit." # Similar text
        payload2["event_id"] = f"Ev{ts2}"
        
        requests.post(url, json=payload2)
        time.sleep(2)
        
        # Check if grouped
        res = requests.get("http://localhost:8000/issues")
        issues = res.json()
        print(f"Found {len(issues)} issues (Expect 1 if clustering works).")
        
        if len(issues) == 1:
            print("✅ Clustering worked! New message added to existing issue.")
            issue_id = issues[0]['id']
            
            # 5. Test Resolve
            print("\nTesting Resolve...")
            res = requests.put(f"http://localhost:8000/issues/{issue_id}/resolve")
            if res.status_code == 200 and res.json()['status'] == 'resolved':
                print("✅ Issue resolved successfully!")
            else:
                print(f"❌ Failed to resolve issue: {res.text}")
        else:
            print("❌ Clustering failed. Created new issue.")

    except Exception as e:
        print(f"Failed test: {e}")

if __name__ == "__main__":
    test_e2e_flow()
