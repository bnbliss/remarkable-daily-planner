import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials.json'

class GoogleCalendarHelper:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.creds = None
        self._load_credentials()

    def _get_client_config(self):
        return {
            "installed": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"]
            }
        }

    def _load_credentials(self):
        """Load credentials from token file if it exists."""
        if os.path.exists(TOKEN_FILE):
            self.creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    def is_authenticated(self):
        """Check if we have valid credentials."""
        if not self.creds:
            return False
        if self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                self._save_credentials()
                return True
            except Exception:
                return False
        return self.creds.valid

    def _save_credentials(self):
        """Save credentials to token file."""
        with open(TOKEN_FILE, 'w') as token:
            token.write(self.creds.to_json())

    def run_local_auth(self):
        """Run local OAuth flow that opens browser and handles redirect."""
        flow = InstalledAppFlow.from_client_config(
            self._get_client_config(),
            SCOPES
        )
        # This will open browser and run local server to catch redirect
        self.creds = flow.run_local_server(port=8085)
        self._save_credentials()
        return True

    def get_calendars(self):
        """Fetch list of calendars from Google."""
        if not self.is_authenticated():
            return []

        try:
            service = build('calendar', 'v3', credentials=self.creds)
            calendar_list = service.calendarList().list().execute()

            calendars = []
            for cal in calendar_list.get('items', []):
                calendars.append({
                    'id': cal['id'],
                    'summary': cal.get('summary', 'Untitled'),
                    'primary': cal.get('primary', False),
                    'backgroundColor': cal.get('backgroundColor', '#4A4A4A')
                })
            return calendars
        except Exception as e:
            print(f"Error fetching calendars: {e}")
            return []

    def get_calendar_events(self, calendar_id, start_date, end_date, timezone):
        """Fetch events from a specific calendar."""
        if not self.is_authenticated():
            return []

        try:
            service = build('calendar', 'v3', credentials=self.creds)

            # Convert dates to RFC3339 format
            time_min = f"{start_date}T00:00:00Z"
            time_max = f"{end_date}T23:59:59Z"

            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime',
                timeZone=timezone
            ).execute()

            return events_result.get('items', [])
        except Exception as e:
            print(f"Error fetching events: {e}")
            return []

    def disconnect(self):
        """Remove stored credentials."""
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        self.creds = None
