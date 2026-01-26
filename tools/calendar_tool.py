"""Google Calendar helpers shared by ExtractionAgent and RemainderAgent."""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config.settings import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_PATH = Path(settings.TOKEN_PATH)


def get_calendar_service() -> Any:
    """Build and return an authenticated Google Calendar v3 service."""
    creds = None
    if TOKEN_PATH.exists():
        # Read token file with UTF-8 BOM handling
        try:
            token_content = TOKEN_PATH.read_text(encoding='utf-8-sig')  # Strips BOM if present
            token_dict = json.loads(token_content)
            creds = Credentials.from_authorized_user_info(token_dict, SCOPES)
        except Exception as e:
            logger.error("Failed to load token.json: %s", str(e))
            raise RuntimeError(f"token.json corrupted or invalid: {str(e)}")
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json(), encoding='utf-8')
        else:
            raise RuntimeError("token.json missing or invalid — re-run the OAuth flow.")
    return build("calendar", "v3", credentials=creds)


def is_slot_free(service: Any, start_dt: datetime, duration_minutes: int = 60) -> bool:
    """Return True if the primary calendar has no busy blocks in the given window."""
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    body = {
        "timeMin": start_dt.isoformat(),
        "timeMax": end_dt.isoformat(),
        "items": [{"id": "primary"}],
    }
    result = service.freebusy().query(body=body).execute()
    busy = result.get("calendars", {}).get("primary", {}).get("busy", [])
    return len(busy) == 0


def check_calendar_conflict(meeting_at_utc: str, duration_minutes: int = 60) -> dict:
    """
    Check for conflicts at the given UTC time and find the next free slot.

    Returns:
        {"has_conflict": bool, "alternate_time": str | None}
    """
    try:
        service = get_calendar_service()
        start_dt = datetime.fromisoformat(meeting_at_utc)

        if is_slot_free(service, start_dt, duration_minutes):
            return {"has_conflict": False, "alternate_time": None}

        candidate = start_dt + timedelta(hours=1)
        for _ in range(7 * 24):
            if is_slot_free(service, candidate, duration_minutes):
                return {"has_conflict": True, "alternate_time": candidate.isoformat()}
            candidate += timedelta(hours=1)

        return {"has_conflict": True, "alternate_time": None}
    except Exception as e:
        logger.warning("Calendar conflict check failed: %s", str(e))
        return {"has_conflict": False, "alternate_time": None}


def create_calendar_event(event_body: dict) -> dict:
    """Insert an event into the primary Google Calendar and return the created event dict."""
    service = get_calendar_service()
    return service.events().insert(calendarId="primary", body=event_body).execute()  # pylint: disable=no-member
