import json
import logging

import redis
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from config.settings import settings
from schema.DataClassifer import DataClassifier
from schema.email_dto import EmailDTO
from schema.mail_extractor import InterviewExtractionResult, TaskExtractionResult, ExtractionResult
from workflow.state import WorkflowState

logger = logging.getLogger(__name__)


class WhatsAppNode:
    """Sends WhatsApp notifications via Twilio and persists review state to Redis."""

    def __init__(self):
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.from_whatsapp_number = f"whatsapp:{settings.TWILIO_PHONE_NUMBER}"
        self.to_whatsapp_number = f"whatsapp:{settings.TARGET_PHONE_NUMBER}"
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=2,
            decode_responses=True,
        )

    def build_failure_message(self, state: WorkflowState) -> str:
        email = state.get("email_data")
        return (
            f"❌ *Pipeline Action Failed*\n"
            f"📌 Subject: {email.subject if email else 'N/A'}\n"
            f"📩 From: {email.sender if email else 'N/A'}\n"
            f"⚙️ Failed Step: {state.get('plan_type', 'N/A')}\n"
            f"🔴 Error: {state.get('action_error', 'Unknown error')}"
        )

    def _build_conflict_block(self, calendar_conflict: dict) -> str:
        """Build calendar conflict indicator block if applicable."""
        if not calendar_conflict.get("has_conflict"):
            return ""
        alt = calendar_conflict.get("alternate_time")
        return (
            f"\n⚠️ *Calendar Conflict Detected*"
            f"\n🔁 Suggested alternate: {alt or 'None available'}"
        )

    def build_interview_message(self, state: WorkflowState) -> str:
        """Format approval request for INTERVIEW category."""
        email_body: EmailDTO = state["email_data"]
        extracted_data: ExtractionResult = state.get("extracted_data")
        classification = state.get("classification")

        sender = email_body.sender or "Unknown Sender"
        subject = email_body.subject or "No Subject"
        ref_id = email_body.uid
        company = extracted_data.company if extracted_data else "Unknown"
        role = extracted_data.role if extracted_data else "Unknown"
        priority = classification.priority.value if classification else "unknown"

        meeting_time = getattr(extracted_data, "meeting_at", None) if extracted_data else None
        timezone = getattr(extracted_data, "timezone", None) if extracted_data else None
        meeting_link = getattr(extracted_data, "meeting_link", None) if extracted_data else None

        calendar_conflict = state.get("calendar_conflict", {})
        conflict_block = self._build_conflict_block(calendar_conflict)
        timezone_block = f"\n🌍 Timezone: {timezone}" if timezone else ""
        link_block = f"\n🔗 Meeting Link: {meeting_link}" if meeting_link else ""

        return (
            f"🔔 *Interview Approval Required*\n"
            f"📩 From: {sender}\n"
            f"📌 Subject: {subject}\n"
            f"🏢 Company: {company}\n"
            f"🎯 Role: {role}\n"
            f"📅 Meeting Time: {meeting_time or 'Not specified'}\n"
            f"{timezone_block}"
            f"{link_block}"
            f"\n🚦 Priority: {priority}\n"
            f"🆔 Ref ID: {ref_id}"
            f"{conflict_block}\n\n"
            f"Reply with: APPROVE {ref_id} or REJECT {ref_id}"
        )

    def build_task_message(self, state: WorkflowState) -> str:
        """Format approval request for TASK category."""
        email_body: EmailDTO = state["email_data"]
        extracted_data: TaskExtractionResult = state.get("extracted_data")
        classification = state.get("classification")

        sender = email_body.sender or "Unknown Sender"
        subject = email_body.subject or "No Subject"
        ref_id = email_body.uid
        company = extracted_data.company if extracted_data else "Unknown"
        role = extracted_data.role if extracted_data else "Unknown"
        priority = classification.priority.value if classification else "unknown"

        deadline = extracted_data.deadline if extracted_data else None
        task_description = getattr(extracted_data, "task_description", None)
        estimated_time = getattr(extracted_data, "estimated_time", None)
        dependencies = getattr(extracted_data, "dependencies", None)

        desc_block = f"\n📋 Task: {task_description}" if task_description else ""
        time_block = f"\n⏱️ Estimate: {estimated_time}" if estimated_time else ""
        dep_block = f"\n🔗 Dependencies: {dependencies}" if dependencies else ""

        return (
            f"🔔 *Task Review Required*\n"
            f"📩 From: {sender}\n"
            f"📌 Subject: {subject}\n"
            f"🏢 Company: {company}\n"
            f"✓ Role: {role}\n"
            f"⏳ Due: {deadline or 'Not specified'}"
            f"{desc_block}"
            f"{time_block}"
            f"{dep_block}"
            f"\n🚦 Priority: {priority}\n"
            f"🆔 Ref ID: {ref_id}\n\n"
            f"Reply with: APPROVE {ref_id} or REJECT {ref_id}"
        )

    def build_generic_message(self, state: WorkflowState) -> str:
        """Fallback message for unclassified or unknown categories."""
        email_body: EmailDTO = state["email_data"]
        extracted_data: ExtractionResult = state.get("extracted_data")
        classification = state.get("classification")

        sender = email_body.sender or "Unknown Sender"
        subject = email_body.subject or "No Subject"
        ref_id = email_body.uid
        company = extracted_data.company if extracted_data else "Unknown"
        role = extracted_data.role if extracted_data else "Unknown"
        priority = classification.priority.value if classification else "unknown"

        deadline = getattr(extracted_data, "deadline", None) if extracted_data else None
        meeting_time = getattr(extracted_data, "meeting_at", None) if extracted_data else None

        content = (
            f"Meeting time: {meeting_time}"
            if meeting_time
            else f"Deadline: {deadline or 'unknown'}"
        )

        calendar_conflict = state.get("calendar_conflict", {})
        conflict_block = self._build_conflict_block(calendar_conflict)

        return (
            f"🔔 *Approval Required*\n"
            f"📩 From: {sender}\n"
            f"📌 Subject: {subject}\n"
            f"🏢 Company: {company}\n"
            f"🎯 Role: {role}\n"
            f"📅 {content}\n"
            f"🚦 Priority: {priority}\n"
            f"🆔 Ref ID: {ref_id}"
            f"{conflict_block}\n\n"
            f"Reply with: APPROVE {ref_id} or REJECT {ref_id}"
        )

    def build_review_message(self, state: WorkflowState) -> str:
        """
        Build the appropriate approval message based on email category.
        
        Routes to category-specific builders for optimized messaging.
        Falls back to generic message for unknown categories.
        """
        classification = state.get("classification")
        
        if not classification:
            return self.build_generic_message(state)

        category = classification.category
        if category == DataClassifier.INTERVIEW:
            return self.build_interview_message(state)
        elif category == DataClassifier.TASK:
            return self.build_task_message(state)
        else:
            return self.build_generic_message(state)

    def _save_state_to_redis(self, state: WorkflowState) -> None:
        ref_id = state["email_data"].uid
        serializable_state = {
            "email_data": state["email_data"].model_dump(mode="json"),
            "decision": state.get("decision"),
            "classification": (
                state["classification"].model_dump(mode="json")
                if state.get("classification") else None
            ),
            "extracted_data": (
                state["extracted_data"].model_dump(mode="json")
                if state.get("extracted_data") else None
            ),
            "plan_type": state.get("plan_type"),
            "calendar_conflict": state.get("calendar_conflict"),
        }
        self.redis.set(f"state:{ref_id}", json.dumps(serializable_state), ex=86400)
        logger.info("State saved to Redis for ref_id: %s", ref_id)

    def _send(self, body: str) -> str:
        message = self.client.messages.create(
            from_=self.from_whatsapp_number,
            body=body,
            to=self.to_whatsapp_number,
        )
        return message.sid

    @staticmethod
    def send_message(state: WorkflowState) -> WorkflowState:
        """Notification/Failure graph node — sends a WhatsApp message via Twilio."""
        tool = WhatsAppNode()
        try:
            if state.get("action_failed"):
                sid = tool._send(tool.build_failure_message(state))
                logger.info("Failure WhatsApp sent. SID: %s", sid)
                return {**state, "execution_result": "SUCCESS", "error": None}

            tool._save_state_to_redis(state)
            sid = tool._send(tool.build_review_message(state))
            logger.info("Review WhatsApp sent. SID: %s", sid)
            return {**state, "execution_result": "SUCCESS", "error": None}

        except TwilioRestException as e:
            logger.error("Twilio error: %s", str(e))
            return {**state, "action_failed": True, "action_error": str(e), "execution_result": "FAILED"}

        except redis.RedisError as e:
            logger.error("Redis error (attempting send anyway): %s", str(e))
            try:
                sid = tool._send(tool.build_review_message(state))
                logger.info("WhatsApp sent despite Redis failure. SID: %s", sid)
                return {**state, "execution_result": "SUCCESS", "error": str(e)}
            except Exception as inner:
                logger.exception("WhatsApp also failed: %s", str(inner))
                return {**state, "action_failed": True, "action_error": str(inner), "execution_result": "FAILED"}

        except Exception as e:
            logger.exception("Unexpected WhatsAppNode error: %s", str(e))
            return {**state, "action_failed": True, "action_error": str(e), "execution_result": "FAILED"}
