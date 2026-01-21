from fastapi import FastAPI, Request, BackgroundTasks, Depends
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os
from sqlalchemy.orm import Session
from sqlalchemy import desc

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

@app.post("/api/track", response_model=EventResponse)
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
    
    print(f"Saved event: {payload.event_type} on {payload.url} (ID: {db_event.id})")
    
    return EventResponse(received_at=datetime.utcnow())

@app.get("/wa.js")
async def get_tracker_js():
    """
    Serves the client-side JavaScript library.
    """
    file_path = os.path.join(os.path.dirname(__file__), "static", "wa.js")
    return FileResponse(file_path, media_type="application/javascript")

from urllib.parse import urlparse
from collections import defaultdict

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

def normalize_referrer(referrer: str, current_url: str) -> str:
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
        
        return parsed_ref.netloc # Fallback to domain
    except Exception as e:
        print(f"Error normalizing referrer: {e}, referrer: {referrer}")
        return "Unknown"

@app.get("/api/analytics/sankey")
async def get_sankey_data(db: Session = Depends(get_db)):
    # Get pageviews from last 24 hours (or limit to last 2000 events for performance)
    events = db.query(Event).filter(Event.event_type == 'pageview').order_by(Event.timestamp).limit(2000).all()
    
    # Group by session
    sessions = defaultdict(list)
    session_referrers = {} # Store the first referrer of the session
    
    for event in events:
        sessions[event.session_id].append(normalize_url(event.url))
        
        # Capture the referrer of the *first* event in the session
        if event.session_id not in session_referrers:
            session_referrers[event.session_id] = normalize_referrer(event.referrer, event.url)

    # Build flows
    # Layer 0: Referrer -> Step 1
    # Layer 1: Step 1 -> Step 2
    # Layer 2: Step 2 -> Step 3
    links_count = defaultdict(int)
    nodes = set()
    
    for session_id, urls in sessions.items():
        if not urls: continue
        
        # Layer 0: Referrer -> First Page
        referrer = session_referrers.get(session_id, "Direct Entry")
        if referrer != "Internal": # Only map external/direct sources as start
            source_ref = f"{referrer} (Source)"
            target_1 = f"{urls[0]} (Step 1)"
            links_count[(source_ref, target_1)] += 1
            nodes.add(source_ref)
            nodes.add(target_1)
        
        # Layer 1: Step 1 -> Step 2
        if len(urls) >= 2:
            source = f"{urls[0]} (Step 1)"
            target = f"{urls[1]} (Step 2)"
            links_count[(source, target)] += 1
            nodes.add(source)
            nodes.add(target)
            
            # Layer 2: Step 2 -> Step 3
            if len(urls) >= 3:
                source_2 = f"{urls[1]} (Step 2)"
                target_2 = f"{urls[2]} (Step 3)"
                links_count[(source_2, target_2)] += 1
                nodes.add(source_2)
                nodes.add(target_2)

    # Format for ECharts
    echarts_nodes = [{"name": name} for name in nodes]
    echarts_links = [{"source": k[0], "target": k[1], "value": v} for k, v in links_count.items()]
    
    return {"nodes": echarts_nodes, "links": echarts_links}

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

@app.get("/", response_class=HTMLResponse)
async def root(db: Session = Depends(get_db)):
    events = db.query(Event).order_by(desc(Event.timestamp)).limit(50).all()
    count = db.query(Event).count()
    
    rows = ""
    for event in events:
        rows += f"""
        <tr>
            <td>{event.id}</td>
            <td>{event.event_type}</td>
            <td style="word-break: break-all;"><a href="{event.url}" target="_blank">{event.url}</a></td>
            <td>{event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td>
            <td><span title="{event.visitor_id}">{event.visitor_id[:8]}...</span></td>
            <td>{event.ip_address}</td>
            <td>{event.data}</td>
        </tr>
        """
        
    html_content = f"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>Web Analytics Dashboard</title>
            <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                h1 {{ color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
                .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 6px; display: inline-block; border: 1px solid #dee2e6; margin-bottom: 20px; margin-right: 10px; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #007bff; }}
                .metric-label {{ color: #6c757d; font-size: 14px; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 10px; font-size: 14px; }}
                th, td {{ border: 1px solid #dee2e6; padding: 12px; text-align: left; }}
                th {{ background-color: #f8f9fa; color: #495057; font-weight: 600; }}
                tr:nth-child(even) {{ background-color: #f8f9fa; }}
                tr:hover {{ background-color: #f2f2f2; }}
                .refresh-btn {{ float: right; padding: 8px 16px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; margin-left: 10px; }}
                .refresh-btn:hover {{ background: #218838; }}
                .clear-btn {{ float: right; padding: 8px 16px; background: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; }}
                .clear-btn:hover {{ background: #c82333; }}
                #sankey-chart {{ width: 100%; height: 500px; margin-bottom: 30px; border: 1px solid #eee; }}
            </style>
        </head>
        <body>
            <div class="container">
                <a href="/" class="refresh-btn">Refresh Data</a>
                <button onclick="clearData()" class="clear-btn">Clear All Data</button>
                <h1>Web Analytics Dashboard</h1>
                
                <div class="metric-card">
                    <div class="metric-value">{count}</div>
                    <div class="metric-label">Total Events Captured</div>
                </div>

                <h3>User Flow (First 3 Steps)</h3>
                <div id="sankey-chart">Loading Chart...</div>

                <h3>Recent Events (Last 50)</h3>
                <table>
                    <thead>
                        <tr>
                            <th width="50">ID</th>
                            <th width="100">Type</th>
                            <th>URL</th>
                            <th width="180">Time (UTC)</th>
                            <th width="100">Visitor</th>
                            <th width="120">IP</th>
                            <th>Data</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows if rows else '<tr><td colspan="7" style="text-align:center">No events recorded yet. Try navigating on the main site!</td></tr>'}
                    </tbody>
                </table>
            </div>

            <script>
                // Initialize Chart
                var chartDom = document.getElementById('sankey-chart');
                var myChart = echarts.init(chartDom);
                
                fetch('/api/analytics/sankey')
                    .then(response => response.json())
                    .then(data => {{
                        var option = {{
                            tooltip: {{
                                trigger: 'item',
                                triggerOn: 'mousemove'
                            }},
                            series: [
                                {{
                                    type: 'sankey',
                                    data: data.nodes,
                                    links: data.links,
                                    emphasis: {{
                                        focus: 'adjacency'
                                    }},
                                    lineStyle: {{
                                        color: 'gradient',
                                        curveness: 0.5
                                    }},
                                    label: {{
                                        position: 'right'
                                    }}
                                }}
                            ]
                        }};
                        myChart.setOption(option);
                    }});
                
                // Auto refresh chart every 30s
                setInterval(() => {{
                     fetch('/api/analytics/sankey')
                        .then(response => response.json())
                        .then(data => {{
                            myChart.setOption({{
                                series: [{{ data: data.nodes, links: data.links }}]
                            }});
                        }});
                }}, 30000);

                function clearData() {{
                    if(confirm("Are you sure you want to DELETE ALL analytics data? This cannot be undone.")) {{
                        fetch('/api/analytics/clear', {{ method: 'DELETE' }})
                            .then(response => response.json())
                            .then(data => {{
                                alert(data.message);
                                location.reload();
                            }});
                    }}
                }}
            </script>
        </body>
    </html>
    """
    return html_content
