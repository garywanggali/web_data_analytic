import requests
import uuid
import random
import time
from datetime import datetime, timedelta

# Configuration
ANALYTICS_ENDPOINT = "http://localhost:8001/api/track"
BASE_URL = "http://110.40.153.38:5007"

# Simulation Parameters
NUM_USERS = 20
EVENTS_PER_USER = 10

# Helper Lists
URL_PATHS = [
    "/",
    "/courses/",
    "/rankings/",
    "/register/",
    "/login/",
]
# Generate some realistic course URLs (assuming IDs 1-10 exist)
URL_PATHS.extend([f"/course/{i}/" for i in range(1, 11)])

REFERRERS = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://twitter.com/",
    "http://110.40.153.38:5007/",
    None
]

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
]

def generate_session_data():
    visitor_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    user_agent = random.choice(USER_AGENTS)
    screen_res = random.choice([(1920, 1080), (1366, 768), (390, 844)])
    
    return {
        "visitor_id": visitor_id,
        "session_id": session_id,
        "user_agent": user_agent,
        "screen_width": screen_res[0],
        "screen_height": screen_res[1],
        "language": "zh-CN"
    }

def simulate_user_journey():
    user_data = generate_session_data()
    print(f"Simulating User: {user_data['visitor_id'][:8]}...")
    
    current_referrer = random.choice(REFERRERS)
    
    for _ in range(random.randint(3, EVENTS_PER_USER)):
        # Simulate browsing behavior
        path = random.choice(URL_PATHS)
        url = BASE_URL + path
        
        event_payload = {
            "event_type": "pageview",
            "url": url,
            "referrer": current_referrer,
            "timestamp": datetime.utcnow().isoformat(),
            **user_data
        }
        
        # Add random custom data for some events
        if "/course/" in path:
            if random.random() < 0.3:
                event_payload["event_type"] = "click"
                event_payload["data"] = {"element": "rate_button", "course_id": path.split("/")[2]}
        
        try:
            requests.post(ANALYTICS_ENDPOINT, json=event_payload)
            # print(f"  -> {event_payload['event_type']} {path}")
        except Exception as e:
            print(f"Error sending event: {e}")
            
        # Update referrer for next pageview
        current_referrer = url
        
        # Small delay to not overwhelm connection (though async handles it fine)
        time.sleep(0.05)

if __name__ == "__main__":
    print(f"Starting simulation of {NUM_USERS} users...")
    start_time = time.time()
    
    for i in range(NUM_USERS):
        simulate_user_journey()
        
    print(f"Simulation complete in {time.time() - start_time:.2f}s")
