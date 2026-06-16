from googleapiclient.discovery import build
from auth import get_credentials
from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/Chicago")  # Central Time

def get_calendar_events(start_iso: str, end_iso: str) -> str:
    """
    Fetch calendar events between two ISO 8601 timestamps.
    Returns a plain-text summary Claude can read.

    Example inputs:
        start_iso = "2025-04-22T08:00:00-05:00"
        end_iso   = "2025-04-22T18:00:00-05:00"
    """
    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)

    # Ask Google for all events in the time window, sorted by start time
    result = service.events().list(
        calendarId="primary",
        timeMin=start_iso,
        timeMax=end_iso,
        singleEvents=True,       # Expand recurring events into individual instances
        orderBy="startTime",
    ).execute()

    events = result.get("items", [])

    if not events:
        return "No events found in this time range."

    # Format each event into a readable line
    lines = []
    for event in events:
        summary = event.get("summary", "(No title)")

        # Google returns either a datetime (timed event) or a date (all-day event)
        start_raw = event["start"].get("dateTime") or event["start"].get("date")
        end_raw   = event["end"].get("dateTime")   or event["end"].get("date")

        # Parse and convert to Central Time for display
        start_dt = _parse_time(start_raw)
        end_dt   = _parse_time(end_raw)

        lines.append(f"- {summary}: {start_dt} → {end_dt}")

    return "\n".join(lines)


def create_calendar_event(title: str, start_iso: str, end_iso: str, description: str = None) -> str:
    """
    Create a new event on Louis's primary Google Calendar.
    Returns a confirmation string.
    """
    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)

    event_body = {
        "summary": title,
        "start": {"dateTime": start_iso, "timeZone": "America/Chicago"},
        "end":   {"dateTime": end_iso,   "timeZone": "America/Chicago"},
    }
    if description:
        event_body["description"] = description

    created = service.events().insert(calendarId="primary", body=event_body).execute()
    start_dt = _parse_time(created["start"]["dateTime"])
    end_dt   = _parse_time(created["end"]["dateTime"])
    return f"Event created: '{created['summary']}' on {start_dt} → {end_dt}"


def _parse_time(time_str: str) -> str:
    """Convert an ISO time string to a friendly Central Time display string."""
    try:
        # Full datetime string (e.g. "2025-04-22T09:00:00-05:00")
        dt = datetime.fromisoformat(time_str)
        dt = dt.astimezone(TIMEZONE)
        return dt.strftime("%-I:%M %p %a %b %-d")  # e.g. "9:00 AM Tue Apr 22"
    except ValueError:
        # Date-only string for all-day events (e.g. "2025-04-22")
        return f"All day ({time_str})"
