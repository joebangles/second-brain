"""Google Calendar tools for Second Brain."""

import os
from datetime import datetime, timedelta

from google.adk.tools import FunctionTool
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Google Calendar API scopes
CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar']

# Cache the calendar service
_calendar_service = None


def get_calendar_service():
    """Get or create the Google Calendar service with OAuth authentication."""
    global _calendar_service
    
    if _calendar_service is not None:
        return _calendar_service
    
    creds = None
    
    # Load existing credentials from token.json
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', CALENDAR_SCOPES)
    
    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError(
                    "credentials.json not found. Download it from Google Cloud Console:\n"
                    "1. Go to https://console.cloud.google.com/apis/credentials\n"
                    "2. Create OAuth 2.0 Client ID (Desktop app)\n"
                    "3. Download and save as 'credentials.json' in this directory"
                )
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', CALENDAR_SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    _calendar_service = build('calendar', 'v3', credentials=creds)
    return _calendar_service


def add_calendar_event(title: str, date: str, time: str, duration_minutes: int = 60, description: str = "", location: str = "") -> str:
    """Add an event to Google Calendar.
    
    Args:
        title: The title of the event
        date: The date in YYYY-MM-DD format
        time: The time in HH:MM format (24-hour)
        duration_minutes: Duration of the event in minutes (default 60)
        description: Optional description for the event
        location: Optional location for the event
    """
    try:
        service = get_calendar_service()
        
        # Parse date and time
        start_datetime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)
        
        # Get timezone from system or default to UTC
        timezone = os.getenv('TIMEZONE', 'UTC')
        
        event = {
            'summary': title,
            'description': description,
            'start': {
                'dateTime': start_datetime.isoformat(),
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_datetime.isoformat(),
                'timeZone': timezone,
            },
        }
        
        if location:
            event['location'] = location
        
        event = service.events().insert(calendarId='primary', body=event).execute()
        
        location_str = f" at {location}" if location else ""
        return f"Event created: '{title}' on {date} at {time}{location_str} ({duration_minutes} min)"
        
    except FileNotFoundError as e:
        return f"Error: Calendar not configured: {e}"
    except HttpError as e:
        return f"Error: Calendar API error: {e}"
    except ValueError as e:
        return f"Error: Invalid date/time format: {e}. Use YYYY-MM-DD for date and HH:MM for time."
    except Exception as e:
        return f"Error: Error creating event: {e}"


def list_calendar_events(date: str = "", max_results: int = 10) -> str:
    """List upcoming calendar events.
    
    Args:
        date: Optional date to start listing from (YYYY-MM-DD format). Defaults to today.
        max_results: Maximum number of events to return (default 10)
    """
    try:
        service = get_calendar_service()
        
        # Parse start date or use now
        if date:
            time_min = datetime.strptime(date, "%Y-%m-%d")
        else:
            time_min = datetime.now()
        
        # Get events
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min.isoformat() + 'Z',
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return "📅 No upcoming events found."
        
        # Format events list
        output = "📅 Upcoming events:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            # Parse and format the datetime
            if 'T' in start:
                dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                formatted = dt.strftime("%Y-%m-%d %H:%M")
            else:
                formatted = start
            
            summary = event.get('summary', '(No title)')
            output += f"  • {formatted}: {summary}\n"
        
        return output
        
    except FileNotFoundError as e:
        return f"❌ Calendar not configured: {e}"
    except HttpError as e:
        return f"❌ Calendar API error: {e}"
    except ValueError as e:
        return f"❌ Invalid date format: {e}. Use YYYY-MM-DD."
    except Exception as e:
        return f"❌ Error listing events: {e}"


def delete_calendar_event(event_title: str, date: str = "") -> str:
    """Delete a calendar event by title.
    
    Args:
        event_title: The title of the event to delete
        date: Optional date to narrow down search (YYYY-MM-DD format)
    """
    try:
        service = get_calendar_service()
        
        # Search for the event
        if date:
            time_min = datetime.strptime(date, "%Y-%m-%d")
            time_max = time_min + timedelta(days=1)
        else:
            time_min = datetime.now()
            time_max = time_min + timedelta(days=30)  # Search next 30 days
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min.isoformat() + 'Z',
            timeMax=time_max.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        # Find matching event
        for event in events:
            if event_title.lower() in event.get('summary', '').lower():
                service.events().delete(calendarId='primary', eventId=event['id']).execute()
                return f"Deleted event: '{event.get('summary')}'"
        
        return f"No event found matching '{event_title}'"
        
    except FileNotFoundError as e:
        return f"Error: Calendar not configured: {e}"
    except HttpError as e:
        return f"Error: Calendar API error: {e}"
    except Exception as e:
        return f"Error: Error deleting event: {e}"


# Create tool instances
calendar_add_tool = FunctionTool(add_calendar_event)
calendar_list_tool = FunctionTool(list_calendar_events)
calendar_delete_tool = FunctionTool(delete_calendar_event)
