from database import SessionLocal, engine
from main import Event, normalize_referrer
from sqlalchemy import desc

def check_google_events():
    db = SessionLocal()
    try:
        # Get all pageviews
        events = db.query(Event).filter(Event.event_type == 'pageview').order_by(desc(Event.timestamp)).all()
        
        google_count = 0
        print(f"{'ID':<6} | {'Time (UTC)':<20} | {'Source Type':<15} | {'URL'}")
        print("-" * 80)
        
        for e in events:
            # Check 1: UTM Source
            utm_source = e.data.get('source', '').lower() if e.data else ''
            
            # Check 2: Referrer
            raw_url = e.url if e.url else ""
            raw_ref = e.referrer if e.referrer else ""
            raw_ua = e.user_agent if e.user_agent else ""
            
            is_google = False
            source_type = ""
            
            if 'google' in utm_source:
                is_google = True
                source_type = "UTM Param"
            elif 'google' in raw_ref:
                is_google = True
                source_type = "Referrer"
                
            if is_google:
                google_count += 1
                print(f"{e.id:<6} | {str(e.timestamp):<20} | {source_type:<15} | {e.url}")
        
        print("-" * 80)
        print(f"Total Google Events Found: {google_count}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_google_events()