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

@app.get("/wa.js")
async def get_tracker_js():
    """
    Serves the client-side JavaScript library.
    """
    file_path = os.path.join(os.path.dirname(__file__), "static", "wa.js")
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
async def get_analytics_stats(db: Session = Depends(get_db)):
    try:
        # Time range: Last 24 hours (for simplicity)
        # In a real app, accept start_date/end_date query params
        now = datetime.utcnow()
        # limit to recent data for performance
        events = db.query(Event).order_by(desc(Event.timestamp)).limit(5000).all()
        
        # 1. User & Session Metrics
        total_users = len(set(e.visitor_id for e in events))
        total_sessions = len(set(e.session_id for e in events))
        
        # 2. Page Views & Engagement
        page_views = len([e for e in events if e.event_type == 'pageview'])
        
        # Calculate Average Engagement Time
        engagement_events = [e for e in events if e.event_type == 'user_engagement']
        total_duration = sum(int(e.data.get('duration_seconds', 0)) for e in engagement_events if e.data)
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
        for e in events:
            if e.event_type == 'pageview':
                ua = (e.user_agent or "").lower()
                if "mobile" in ua or "android" in ua or "iphone" in ua:
                    dev = "Mobile"
                else:
                    dev = "Desktop"
                devices[dev] += 1
        
        return {
            "users": total_users,
            "sessions": total_sessions,
            "page_views": page_views,
            "avg_engagement_time": avg_engagement_time,
            "top_sources": [{"name": k, "value": v} for k, v in top_sources],
            "top_pages": [{"name": k, "value": v} for k, v in top_pages],
            "devices": [{"name": k, "value": v} for k, v in devices.items()]
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

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
                
                .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }}
                .metric-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #dee2e6; text-align: center; }}
                .metric-value {{ font-size: 32px; font-weight: bold; color: #007bff; margin-bottom: 5px; }}
                .metric-label {{ color: #6c757d; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }}
                
                .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }}
                .chart-container {{ height: 350px; border: 1px solid #eee; border-radius: 8px; padding: 10px; }}
                #sankey-chart {{ width: 100%; height: 500px; margin-bottom: 30px; border: 1px solid #eee; }}
                
                table {{ border-collapse: collapse; width: 100%; margin-top: 10px; font-size: 14px; }}
                th, td {{ border: 1px solid #dee2e6; padding: 12px; text-align: left; }}
                th {{ background-color: #f8f9fa; color: #495057; font-weight: 600; }}
                tr:nth-child(even) {{ background-color: #f8f9fa; }}
                tr:hover {{ background-color: #f2f2f2; }}
                
                .refresh-btn {{ float: right; padding: 8px 16px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; margin-left: 10px; }}
                .refresh-btn:hover {{ background: #218838; }}
                .clear-btn {{ float: right; padding: 8px 16px; background: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; }}
                .clear-btn:hover {{ background: #c82333; }}
            </style>
        </head>
        <body>
            <div class="container">
                <a href="/" class="refresh-btn">Refresh Data</a>
                <button onclick="clearData()" class="clear-btn">Clear All Data</button>
                <h1>Web Analytics Dashboard</h1>
                
                <div class="kpi-grid">
                    <div class="metric-card">
                        <div class="metric-value" id="val-users">-</div>
                        <div class="metric-label">Users</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" id="val-sessions">-</div>
                        <div class="metric-label">Sessions</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" id="val-views">-</div>
                        <div class="metric-label">Page Views</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" id="val-time">-</div>
                        <div class="metric-label">Avg. Engagement (s)</div>
                    </div>
                </div>

                <div class="charts-grid">
                    <div id="source-chart" class="chart-container"></div>
                    <div id="device-chart" class="chart-container"></div>
                </div>
                
                <h3>User Flow</h3>
                <div id="sankey-chart">Loading Chart...</div>

                <h3>Top Pages</h3>
                <div id="pages-chart" class="chart-container" style="margin-bottom: 30px;"></div>

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
                // Initialize Charts
                var sankeyChart = echarts.init(document.getElementById('sankey-chart'));
                var sourceChart = echarts.init(document.getElementById('source-chart'));
                var deviceChart = echarts.init(document.getElementById('device-chart'));
                var pagesChart = echarts.init(document.getElementById('pages-chart'));
                
                function loadData() {{
                    // 1. Load Stats
                    fetch('/api/analytics/stats')
                        .then(r => r.json())
                        .then(data => {{
                            if(data.error) return;
                            
                            // KPIs
                            document.getElementById('val-users').innerText = data.users;
                            document.getElementById('val-sessions').innerText = data.sessions;
                            document.getElementById('val-views').innerText = data.page_views;
                            document.getElementById('val-time').innerText = data.avg_engagement_time + 's';
                            
                            // Source Pie
                            sourceChart.setOption({{
                                title: {{ text: 'Traffic Acquisition', left: 'center' }},
                                tooltip: {{ trigger: 'item' }},
                                series: [{{
                                    name: 'Source',
                                    type: 'pie',
                                    radius: '50%',
                                    data: data.top_sources,
                                    emphasis: {{ itemStyle: {{ shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' }} }}
                                }}]
                            }});
                            
                            // Device Pie
                            deviceChart.setOption({{
                                title: {{ text: 'Device Category', left: 'center' }},
                                tooltip: {{ trigger: 'item' }},
                                series: [{{
                                    name: 'Device',
                                    type: 'pie',
                                    radius: ['40%', '70%'],
                                    avoidLabelOverlap: false,
                                    itemStyle: {{ borderRadius: 10, borderColor: '#fff', borderWidth: 2 }},
                                    label: {{ show: false, position: 'center' }},
                                    emphasis: {{ label: {{ show: true, fontSize: 20, fontWeight: 'bold' }} }},
                                    data: data.devices
                                }}]
                            }});
                            
                            // Pages Bar
                            pagesChart.setOption({{
                                title: {{ text: 'Top Pages', left: 'center' }},
                                tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }} }},
                                grid: {{ left: '3%', right: '4%', bottom: '3%', containLabel: true }},
                                xAxis: {{ type: 'value' }},
                                yAxis: {{ type: 'category', data: data.top_pages.map(i => i.name).reverse() }},
                                series: [{{
                                    name: 'Views',
                                    type: 'bar',
                                    data: data.top_pages.map(i => i.value).reverse()
                                }}]
                            }});
                        }});

                    // 2. Load Sankey
                    fetch('/api/analytics/sankey')
                        .then(response => response.json())
                        .then(data => {{
                            var option = {{
                                tooltip: {{ trigger: 'item', triggerOn: 'mousemove' }},
                                series: [
                                    {{
                                        type: 'sankey',
                                        data: data.nodes,
                                        links: data.links,
                                        emphasis: {{ focus: 'adjacency' }},
                                        lineStyle: {{ color: 'gradient', curveness: 0.5 }},
                                        label: {{ position: 'right' }}
                                    }}
                                ]
                            }};
                            sankeyChart.setOption(option);
                        }});
                }}
                
                // Initial Load
                loadData();
                
                // Auto refresh chart every 30s
                setInterval(loadData, 30000);
                
                // Resize charts on window resize
                window.addEventListener('resize', function() {{
                    sankeyChart.resize();
                    sourceChart.resize();
                    deviceChart.resize();
                    pagesChart.resize();
                }});

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
