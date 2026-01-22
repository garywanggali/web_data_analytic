from fastapi import FastAPI, Request, BackgroundTasks, Depends
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os
from sqlalchemy.orm import Session
from sqlalchemy import desc
from collections import defaultdict # <--- Re-added this!

from schemas import EventPayload, EventResponse
from database import engine, Base, get_db
from models import Event

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Web Data Analytics")

# Enable CORS so rate_my_course (on a different port) can send data
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the rate_my_course domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/collect", response_model=EventResponse)
async def track_event(
    payload: EventPayload, 
    request: Request, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Endpoint to receive analytics events.
    """
    # Enrich with server-side data if missing
    user_agent = payload.user_agent or request.headers.get("user-agent")
    ip_address = request.client.host
    
    # Create DB model instance
    db_event = Event(
        event_type=payload.event_type,
        url=payload.url,
        referrer=payload.referrer,
        timestamp=payload.timestamp,
        session_id=payload.session_id,
        visitor_id=payload.visitor_id,
        user_id=payload.user_id,
        screen_width=payload.screen_width,
        screen_height=payload.screen_height,
        language=payload.language,
        user_agent=user_agent,
        ip_address=ip_address,
        data=payload.data
    )
    
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    # Normalize referrer for logging
    source = normalize_referrer(payload.referrer, payload.url, payload.user_agent)
    print(f"Saved event: {payload.event_type} on {payload.url} (Source: {source}) (ID: {db_event.id})")
    
    # Log Headers (excluding sensitive ones)
    headers = dict(request.headers)
    print(f"Request Headers: {headers}")
    
    return EventResponse(received_at=datetime.utcnow())

@app.get("/sdk.js")
async def get_tracker_js():
    """
    Serves the client-side JavaScript library.
    """
    file_path = os.path.join(os.path.dirname(__file__), "static", "sdk.js")
    return FileResponse(file_path, media_type="application/javascript")

from urllib.parse import urlparse, parse_qs

def normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        path = parsed.path
        if path == "/" or path == "": return "Home"
        if path.startswith("/course/"): return "Course Detail"
        if path.startswith("/courses"): return "Course List"
        if path.startswith("/rankings"): return "Rankings"
        if path.startswith("/login"): return "Login"
        if path.startswith("/register"): return "Register"
        if path.startswith("/admin"): return "Admin"
        return path
    except:
        return "Unknown"

def normalize_referrer(referrer: str, current_url: str, user_agent: str = "") -> str:
    # 1. Check UTM parameters in current_url first (Highest Priority)
    try:
        parsed_curr = urlparse(current_url)
        query_params = parse_qs(parsed_curr.query)
        if 'utm_source' in query_params:
            source = query_params['utm_source'][0].lower()
            if source == 'wechat': return 'WeChat'
            if source == 'dingtalk': return 'DingTalk'
            if source == 'google': return 'Google Search'
            return f"{source.capitalize()} (UTM)"
    except:
        pass

    # 2. Check User Agent (Secondary Priority)
    if user_agent:
        ua = user_agent.lower()
        if "micromessenger" in ua: return "WeChat"
        if "dingtalk" in ua: return "DingTalk"
        if "qq/" in ua: return "QQ"
        if "weibo" in ua: return "Weibo"

    # 3. Check Referrer
    if not referrer:
        return "Direct Entry"
    try:
        parsed_ref = urlparse(referrer)
        parsed_curr = urlparse(current_url)
        
        # If referrer is same domain, ignore it as "source" (it's internal navigation)
        if parsed_ref.netloc == parsed_curr.netloc:
            return "Internal"
            
        # Classify external sources
        if "google" in parsed_ref.netloc: return "Google Search"
        if "bing" in parsed_ref.netloc: return "Bing Search"
        if "twitter" in parsed_ref.netloc or "t.co" in parsed_ref.netloc: return "Twitter"
        if "facebook" in parsed_ref.netloc: return "Facebook"
        if "baidu" in parsed_ref.netloc: return "Baidu"
        if "dingtalk" in parsed_ref.netloc: return "DingTalk"
        if "weixin" in parsed_ref.netloc or "wechat" in parsed_ref.netloc: return "WeChat"
        
        return parsed_ref.netloc # Fallback to domain
    except Exception as e:
        print(f"Error normalizing referrer: {e}, referrer: {referrer}")
        return "Unknown"

@app.get("/api/analytics/sankey")
async def get_sankey_data(db: Session = Depends(get_db)):
    try:
        # Get pageviews
        events = db.query(Event).filter(Event.event_type == 'pageview').order_by(Event.timestamp).limit(2000).all()
        
        sessions = defaultdict(list)
        session_referrers = {}
        
        for event in events:
            try:
                # 1. Normalize URL (handle None)
                raw_url = event.url if event.url else ""
                norm_url = normalize_url(raw_url)
                sessions[event.session_id].append(norm_url)
                
                # 2. Capture Referrer (handle None)
                if event.session_id not in session_referrers:
                    raw_ref = event.referrer if event.referrer else ""
                    raw_ua = event.user_agent if event.user_agent else ""
                    session_referrers[event.session_id] = normalize_referrer(raw_ref, raw_url, raw_ua)
            except Exception as inner_e:
                print(f"Skipping event {event.id}: {inner_e}")
                continue

        links_count = defaultdict(int)
        nodes = set()
        
        for session_id, urls in sessions.items():
            if not urls: continue
            
            # Layer 0
            referrer = session_referrers.get(session_id, "Direct Entry")
            if referrer != "Internal":
                s = f"{referrer} (Source)"
                t = f"{urls[0]} (Step 1)"
                links_count[(s, t)] += 1
                nodes.add(s)
                nodes.add(t)
            
            # Layer 1
            if len(urls) >= 2:
                s = f"{urls[0]} (Step 1)"
                t = f"{urls[1]} (Step 2)"
                if s != t:
                    links_count[(s, t)] += 1
                    nodes.add(s)
                    nodes.add(t)
                
                # Layer 2
                if len(urls) >= 3:
                    s2 = f"{urls[1]} (Step 2)"
                    t2 = f"{urls[2]} (Step 3)"
                    if s2 != t2:
                        links_count[(s2, t2)] += 1
                        nodes.add(s2)
                        nodes.add(t2)

        echarts_nodes = [{"name": str(name)} for name in nodes]
        echarts_links = [{"source": str(k[0]), "target": str(k[1]), "value": int(v)} for k, v in links_count.items()]
        
        return {"nodes": echarts_nodes, "links": echarts_links}
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"CRITICAL Error: {e}")
        return {"nodes": [], "links": []}

@app.delete("/api/analytics/clear")
async def clear_data(db: Session = Depends(get_db)):
    """
    Clears all analytics data from the database.
    WARNING: This action is irreversible.
    """
    try:
        db.query(Event).delete()
        db.commit()
        return {"status": "success", "message": "All data cleared"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}

@app.get("/api/analytics/stats")
async def get_analytics_stats(range: str = "24h", db: Session = Depends(get_db)):
    try:
        # Time range filtering
        now = datetime.utcnow()
        if range == "24h":
            from datetime import timedelta
            start_time = now - timedelta(hours=24)
        elif range == "7d":
            from datetime import timedelta
            start_time = now - timedelta(days=7)
        elif range == "30d":
            from datetime import timedelta
            start_time = now - timedelta(days=30)
        elif range == "all":
            start_time = datetime.min
        else:
            # Default to 24h if invalid
            from datetime import timedelta
            start_time = now - timedelta(hours=24)

        # Query events with time filter
        query = db.query(Event).filter(Event.timestamp >= start_time)
        events = query.order_by(desc(Event.timestamp)).limit(5000).all()
        
        # 1. User & Session Metrics
        total_users = len(set(e.visitor_id for e in events))
        total_sessions = len(set(e.session_id for e in events))
        
        # 2. Page Views & Engagement
        page_views = len([e for e in events if e.event_type == 'pageview'])
        
        # Calculate Average Engagement Time
        engagement_events = [e for e in events if e.event_type == 'user_engagement']
        total_duration = 0
        valid_engagements = 0
        
        for e in engagement_events:
            if e.data:
                duration = int(e.data.get('duration_seconds', 0))
                # Filter outliers: cap at 30 minutes (1800s) per session to avoid skewing data
                # Or ignore extremely long durations that might be bugs or idle tabs
                if duration > 0 and duration < 86400: # Simple sanity check (less than 24h)
                    if duration > 1800: 
                        duration = 1800 # Cap at 30 mins
                    total_duration += duration
                    valid_engagements += 1
                    
        # Use valid_engagements count or total_sessions for average
        # Using total_sessions gives "Time per Session"
        avg_engagement_time = round(total_duration / total_sessions, 1) if total_sessions > 0 else 0
        
        # 3. Top Sources (Acquisition)
        sources = defaultdict(int)
        for e in events:
            if e.event_type == 'pageview':
                # Prefer UTM source, then Referrer source
                utm_source = e.data.get('source') if e.data else None
                if utm_source:
                    src = f"{utm_source} (UTM)"
                else:
                    # Re-use our normalize logic
                    # In a real DB, we should store normalized source in a column
                    raw_url = e.url if e.url else ""
                    raw_ref = e.referrer if e.referrer else ""
                    raw_ua = e.user_agent if e.user_agent else ""
                    src = normalize_referrer(raw_ref, raw_url, raw_ua)
                
                sources[src] += 1
        
        top_sources = sorted(sources.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # 4. Top Pages
        pages = defaultdict(int)
        for e in events:
            if e.event_type == 'pageview':
                path = normalize_url(e.url if e.url else "")
                pages[path] += 1
        
        top_pages = sorted(pages.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # 5. Device Breakdown
        devices = defaultdict(int)
        # 6. User Type (New vs Returning based on session count in period)
        # We track both User Count and Page View Count
        user_type_counts = {"New Visitors": 0, "Returning Visitors": 0}
        user_type_pvs = {"New Visitors": 0, "Returning Visitors": 0}
        
        visitor_sessions = defaultdict(set)
        visitor_pvs = defaultdict(int)

        for e in events:
            if e.event_type == 'pageview':
                # Device
                ua = (e.user_agent or "").lower()
                if "mobile" in ua or "android" in ua or "iphone" in ua:
                    dev = "Mobile"
                else:
                    dev = "Desktop"
                devices[dev] += 1
                
                # User Type Prep
                visitor_sessions[e.visitor_id].add(e.session_id)
                visitor_pvs[e.visitor_id] += 1
        
        # Calculate User Types & Attribution
        for vid, sessions in visitor_sessions.items():
            pvs = visitor_pvs[vid]
            if len(sessions) > 1:
                user_type_counts["Returning Visitors"] += 1
                user_type_pvs["Returning Visitors"] += pvs
            else:
                user_type_counts["New Visitors"] += 1
                user_type_pvs["New Visitors"] += pvs
        
        # 7. Trend Analysis
        trend_data = defaultdict(lambda: {"users": set(), "sessions": set(), "page_views": 0})
        
        for e in events:
            if e.event_type == 'pageview':
                if range == "24h":
                    # Bucket by hour: "YYYY-MM-DD HH:00"
                    time_key = e.timestamp.strftime("%Y-%m-%d %H:00")
                else:
                    # Bucket by day: "YYYY-MM-DD"
                    time_key = e.timestamp.strftime("%Y-%m-%d")
                
                trend_data[time_key]["users"].add(e.visitor_id)
                trend_data[time_key]["sessions"].add(e.session_id)
                trend_data[time_key]["page_views"] += 1

        # Sort by time
        sorted_keys = sorted(trend_data.keys())
        
        trend_users = []
        trend_sessions = []
        trend_pvs = []
        trend_labels = []

        for key in sorted_keys:
            data = trend_data[key]
            # Format label for display
            if range == "24h":
                # key is "YYYY-MM-DD HH:00", show "HH:00"
                label = key.split(" ")[1]
            else:
                label = key
            
            trend_labels.append(label)
            trend_users.append(len(data["users"]))
            trend_sessions.append(len(data["sessions"]))
            trend_pvs.append(data["page_views"])
        
        return {
            "users": total_users,
            "sessions": total_sessions,
            "page_views": page_views,
            "avg_engagement_time": avg_engagement_time,
            "trend": {
                "labels": trend_labels,
                "users": trend_users,
                "sessions": trend_sessions,
                "page_views": trend_pvs
            },
            "top_sources": [{"name": k, "value": v} for k, v in top_sources],
            "top_pages": [{"name": k, "value": v} for k, v in top_pages],
            "devices": [{"name": k, "value": v} for k, v in devices.items()],
            "user_types": [{"name": k, "value": v} for k, v in user_type_counts.items()],
            "user_type_pvs": [{"name": k, "value": v} for k, v in user_type_pvs.items()]
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

@app.get("/api/analytics/events")
async def get_recent_events(db: Session = Depends(get_db)):
    """
    Returns the most recent 50 events for the dashboard table.
    """
    events = db.query(Event).order_by(desc(Event.timestamp)).limit(50).all()
    return events

@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Serves the dashboard HTML file.
    """
    file_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if not os.path.exists(file_path):
        return HTMLResponse(content="<h1>Error: Template not found</h1>", status_code=404)
        
    with open(file_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return html_content
