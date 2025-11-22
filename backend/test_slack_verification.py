import requests
import json

def test_url_verification():
    url = "http://localhost:8000/slack/events"
    payload = {
        "token": "Jhj5dZrVaK7ZwHHjRyZWjbDl",
        "challenge": "3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P",
        "type": "url_verification"
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200 and response.json().get("challenge") == payload["challenge"]:
            print("✅ URL Verification Passed")
        else:
            print(f"❌ URL Verification Failed: {response.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    test_url_verification()
