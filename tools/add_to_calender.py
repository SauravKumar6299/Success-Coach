import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from googleapiclient.discovery import build

from tools.get_sheets_client import get_sheets_client 

# Load environment variables from .env file
load_dotenv()

# Fetch configs dynamically from .env
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

# Scopes to request both Sheets and Calendar access
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar"
]

def add_to_calendar(roll_no, ai_extracted_data):
    """
    Helper function to build a Google Calendar service using existing credentials
    and inject an emergency sync event directly into the authenticated account's primary schedule.
    """
    gc = get_sheets_client()
    if not gc:
        return False, "Auth client unavailable for Calendar mapping"
        
    try:
        # Reuse the authenticated credentials from your gspread/sheets client
        creds = gc.auth 
        calendar_service = build('calendar', 'v3', credentials=creds)
        
        severity = ai_extracted_data.get("severity", "Medium")
        signal_type = ai_extracted_data.get("signal_type", "Urgent Review")
        reason = ai_extracted_data.get("reason", "No details provided")
        
        # Define meeting metadata
        event_title = f"🚨 [{severity}] Student Emergency Sync | ID: {roll_no}"
        event_description = (
            f"Automated meeting scheduled due to an escalated student pipeline event.\n\n"
            f"Signal Type: {signal_type}\n"
            f"Reason: {reason}"
        )
        
        # Setup time window (scheduling a 30-min block for 1 hour from now)
        start_time = (datetime.utcnow() + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        end_time = (datetime.utcnow() + timedelta(hours=1, minutes=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        event_body = {
            'summary': event_title,
            'description': event_description,
            'start': {
                'dateTime': start_time,
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'UTC',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 15},
                    {'method': 'email', 'minutes': 60},
                ],
            },
        }
        
        # 'primary' targets the calendar of the authenticated account itself
        calendar_id = 'primary' 
        
        event = calendar_service.events().insert(
            calendarId=calendar_id, 
            body=event_body
            # Removed sendUpdates='all' since there are no guests to notify
        ).execute()
        
        return True, event.get('htmlLink')
        
    except Exception as e:
        return False, f"Calendar API failure: {str(e)}"


