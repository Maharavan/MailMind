import logging

from tools.mail_tool import send_email
from schema.email_dto import EmailDTO
from workflow.state import WorkflowState

logger = logging.getLogger(__name__)


class AutoReplyNode:
    """Sends the LLM-drafted reply from ExtractionAgent back to the original sender."""

    @staticmethod
    def execute(state: WorkflowState) -> WorkflowState:
        """AutoReply graph node — sends a reply email and updates state."""
        try:
            extracted = state.get("extracted_data")
            if not extracted or not extracted.suggested_reply:
                logger.info("AutoReplyNode: skipped (no suggested_reply)")
                # Not a failure — just nothing to send; continue to next action
                return {**state, "action_failed": False, "execution_result": "SKIPPED"}
            
            send_email(
                to=state["email_data"].sender,
                body=extracted.suggested_reply,
                message_id=state["email_data"].message_id,
            )
            return {**state, "action_failed": False, "execution_result": "SUCCESS", "error": None}
        except Exception as e:
            logger.exception("AutoReplyNode failed: %s", str(e))
            return {**state, "action_failed": True, "action_error": str(e)}
