from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
import calendar, pytz

from app.db import schemas
from app.db.database import get_db, Base, engine
from app.db.models import Event
from app.services.google_calendar import (
    flow, create_google_event, update_google_event,
    delete_google_event, watch_calendar, sync_google_calendar
)

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

router = APIRouter()
Base.metadata.create_all(bind=engine)

scheduler = BackgroundScheduler()
scheduler.start()
notifications = []
SYNC_TOKEN = None

# --- Helpers ---
def send_notification(event_id: int, title: str, start_time: datetime):
    msg = f"🔔 Reminder: '{title}' starts at {start_time.strftime('%H:%M')}"
    notifications.append(msg)
    print(msg)
    try:
        scheduler.remove_job(f"reminder_{event_id}")
    except:
        pass

def schedule_event_notification(event_id: int, title: str, start_time: datetime):
    ist = pytz.timezone("Asia/Kolkata")
    if start_time.tzinfo is None:
        start_time = ist.localize(start_time)
    reminder_time = start_time - timedelta(minutes=30)
    if reminder_time > datetime.now(ist):
        trigger = DateTrigger(run_date=reminder_time)
        scheduler.add_job(
            send_notification,
            trigger=trigger,
            id=f"reminder_{event_id}",
            args=[event_id, title, start_time],
            replace_existing=True
        )
        print(f"⏰ Reminder scheduled for '{title}' at {reminder_time}")

# --- Routes ---
@router.get("/authorize")
def authorize():
    auth_url, _ = flow.authorization_url(prompt="consent")
    return {"auth_url": auth_url}

@router.get("/oauth2callback")
def oauth2callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(400, "Missing code")
    flow.fetch_token(code=code)
    creds = flow.credentials
    with open("token.json", "w") as token:
        token.write(creds.to_json())
    return {"message": "✅ Auth successful!"}

@router.get("/calendar/month")
def get_month(year: int, month: int, db: Session = Depends(get_db)):
    first_weekday, num_days = calendar.monthrange(year, month)
    days = []
    for day in range(1, num_days + 1):
        d = date(year, month, day)
        start = datetime(year, month, day, 0, 0, 0)
        end = datetime(year, month, day, 23, 59, 59)
        events = db.query(Event).filter(Event.start_time >= start, Event.start_time <= end).all()
        days.append({
            "date": d.isoformat(),
            "weekday": d.strftime("%A"),
            "events": [schemas.Event.from_orm(e) for e in events]
        })
    return {"year": year, "month": month, "days": days}

@router.post("/events/", response_model=schemas.Event)
def create_event(event: schemas.EventCreate, db: Session = Depends(get_db)):
    db_event = Event(**event.dict())
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    try:
        google_event_id = create_google_event(db_event)
        db_event.google_event_id = google_event_id
        db.commit()
    except Exception as e:
        print("⚠️ Google sync failed:", e)
    schedule_event_notification(db_event.id, db_event.title, db_event.start_time)
    return db_event

@router.put("/events/{event_id}", response_model=schemas.Event)
def update_event(event_id: int, updated: schemas.EventUpdate, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    for key, value in updated.dict(exclude_unset=True).items():
        setattr(event, key, value)
    db.commit()
    db.refresh(event)
    if event.google_event_id:
        try:
            update_google_event(event, event.google_event_id)
        except Exception as e:
            print("⚠️ Google update failed:", e)
    if updated.start_time:
        schedule_event_notification(event.id, event.title, event.start_time)
    return event

@router.delete("/events/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    if event.google_event_id:
        try:
            delete_google_event(event.google_event_id)
        except Exception as e:
            print("⚠️ Google delete failed:", e)
    db.delete(event)
    db.commit()
    try:
        scheduler.remove_job(f"reminder_{event_id}")
    except:
        pass
    return {"message": "Event deleted"}

@router.get("/notifications")
def get_notifications():
    return {"notifications": notifications}

@router.post("/watch")
def start_watch():
    global SYNC_TOKEN
    resp = watch_calendar()
    events, SYNC_TOKEN = sync_google_calendar()
    print(f"✅ Initial sync with {len(events)} events")
    return {"watch_started": True, "resp": resp}

@router.post("/calendar/notifications")
async def calendar_notifications(request: Request, db: Session = Depends(get_db)):
    global SYNC_TOKEN
    headers = request.headers
    print("📩 Calendar Notification Received", headers)
    events, SYNC_TOKEN = sync_google_calendar(SYNC_TOKEN)
    for g_event in events:
        if g_event.get("status") == "cancelled":
            db_event = db.query(Event).filter(Event.google_event_id == g_event["id"]).first()
            if db_event:
                db.delete(db_event)
                db.commit()
        else:
            db_event = db.query(Event).filter(Event.google_event_id == g_event["id"]).first()
            if not db_event:
                db_event = Event(
                    title=g_event.get("summary", "Untitled"),
                    description=g_event.get("description"),
                    start_time=g_event["start"]["dateTime"],
                    end_time=g_event["end"]["dateTime"],
                    google_event_id=g_event["id"]
                )
                db.add(db_event)
            else:
                db_event.title = g_event.get("summary", "")
                db_event.description = g_event.get("description")
                db_event.start_time = g_event["start"]["dateTime"]
                db_event.end_time = g_event["end"]["dateTime"]
            db.commit()
    return {"status": "synced", "events_processed": len(events)}
