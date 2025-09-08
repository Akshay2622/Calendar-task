from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import os, uuid

SCOPES = ["https://www.googleapis.com/auth/calendar"]
DEFAULT_CALENDAR_ID = "primary"

flow = Flow.from_client_secrets_file(
    "credentials.json",
    scopes=SCOPES,
    redirect_uri="http://localhost:8000/oauth2callback"
)

def get_calendar_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        raise Exception("Not authenticated. Visit /authorize first.")
    return build("calendar", "v3", credentials=creds)

# create, update, delete, watch, sync functions (same as yours)
def create_google_event(event):
    service = get_calendar_service()
    g_event = {
        "summary": event.title,
        "description": event.description,
        "start": {"dateTime": event.start_time.isoformat(), "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": (event.end_time or event.start_time).isoformat(), "timeZone": "Asia/Kolkata"},
    }
    created = service.events().insert(calendarId=DEFAULT_CALENDAR_ID, body=g_event).execute()
    return created.get("id")

def update_google_event(event, google_event_id):
    service = get_calendar_service()
    g_event = service.events().get(calendarId=DEFAULT_CALENDAR_ID, eventId=google_event_id).execute()
    g_event["summary"] = event.title
    g_event["description"] = event.description
    g_event["start"]["dateTime"] = event.start_time.isoformat()
    g_event["end"]["dateTime"] = (event.end_time or event.start_time).isoformat()
    updated = service.events().update(calendarId=DEFAULT_CALENDAR_ID, eventId=google_event_id, body=g_event).execute()
    return updated.get("id")

def delete_google_event(google_event_id):
    service = get_calendar_service()
    service.events().delete(calendarId=DEFAULT_CALENDAR_ID, eventId=google_event_id).execute()

def watch_calendar():
    """
    Registers a webhook channel with Google Calendar.
    """
    service = get_calendar_service()
    channel_id = str(uuid.uuid4())   # unique ID for channel
    body = {
        "id": channel_id,
        "type": "webhook",
        "address": "https://sharp-pipefish-smoothly.ngrok-free.app/calendar/notifications"  # must be HTTPS & public
    }
    resp = service.events().watch(calendarId=DEFAULT_CALENDAR_ID, body=body).execute()
    return resp

def sync_google_calendar(sync_token: str = None):
    """
    Returns changed events since last sync. If sync_token is None, does a full sync.
    """
    service = get_calendar_service()
    events = []
    page_token = None
    while True:
        if sync_token:
            events_result = service.events().list(
                calendarId=DEFAULT_CALENDAR_ID,
                syncToken=sync_token,
                pageToken=page_token
            ).execute()
        else:
            events_result = service.events().list(
                calendarId=DEFAULT_CALENDAR_ID,
                timeZone="Asia/Kolkata",
                showDeleted=True,
                singleEvents=True,
                maxResults=250,
                pageToken=page_token
            ).execute()

        items = events_result.get("items", [])
        events.extend(items)

        page_token = events_result.get("nextPageToken")
        if not page_token:
            new_sync_token = events_result.get("nextSyncToken")
            return events, new_sync_token
