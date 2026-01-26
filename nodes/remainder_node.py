import logging
from datetime import datetime, timedelta, timezone

from schema.DataClassifer import DataClassifier
from tools.calendar_tool import create_calendar_event
from workflow.state import WorkflowState

logger = logging.getLogger(__name__)


class RemainderTool:
    """Creates a Google Calendar event for interviews and assessment deadlines."""

    @staticmethod
    def execute(state: WorkflowState) -> WorkflowState:
        """Reminder graph node — builds and inserts a Calendar event."""
        try:
            extracted = state.get("extracted_data")
            email = state["email_data"]
            classification = state.get("classification")
            category = classification.category if classification else None

            if not extracted:
                logger.warning("RemainderTool: no extracted_data")
                return {**state, "action_failed": True, "action_error": "No extracted data", "execution_result": "FAILED"}

            trigger_time_str = getattr(extracted, "meeting_at", None) or extracted.deadline
            if not trigger_time_str:
                logger.warning("RemainderTool: no schedulable time found")
                return {**state, "action_failed": True, "action_error": "No meeting_at or deadline found", "execution_result": "FAILED"}

            trigger_time = datetime.fromisoformat(trigger_time_str)
            if trigger_time <= datetime.now(timezone.utc):
                logger.warning("RemainderTool: trigger_time is in the past")
                return {**state, "action_failed": True, "action_error": "Trigger time is in the past", "execution_result": "FAILED"}

            role = getattr(extracted, "role", None) or "Unknown Role"
            company = getattr(extracted, "company", None) or "Unknown Company"
            meeting_link = getattr(extracted, "meeting_link", None)
            event_end = trigger_time + timedelta(hours=1)

            summary = (
                f"Interview – {role} @ {company}"
                if category == DataClassifier.INTERVIEW
                else f"Assessment Deadline – {role} @ {company}"
            )
            description = (
                f"Source Email: {email.subject}\n"
                f"From: {email.sender}\n"
                f"Role: {role}\n"
                f"Company: {company}\n"
                f"Meeting Link: {meeting_link or 'N/A'}\n"
            )

            event_body = {
                "summary": summary,
                "description": description,
                "start": {"dateTime": trigger_time.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": event_end.isoformat(), "timeZone": "UTC"},
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": 60},
                        {"method": "email", "minutes": 60},
                    ],
                },
            }
            if meeting_link:
                event_body["location"] = meeting_link

            created_event = create_calendar_event(event_body)
            event_url = created_event.get("htmlLink", "N/A")
            logger.info("Calendar event created | summary='%s' | time=%s | url=%s", summary, trigger_time_str, event_url)

            return {**state, "action_failed": False, "execution_result": "SUCCESS", "error": None, "calendar_event_url": event_url}

        except Exception as e:
            logger.exception("RemainderTool error: %s", str(e))
            return {**state, "action_failed": True, "action_error": str(e), "execution_result": "FAILED"}
