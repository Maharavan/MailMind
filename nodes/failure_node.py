import logging

from nodes.whatsapp_node import WhatsAppNode
from workflow.state import WorkflowState

logger = logging.getLogger(__name__)


class FailureNode:
    """Logs pipeline failures and escalates via WhatsApp."""

    @staticmethod
    def handle(state: WorkflowState) -> WorkflowState:
        """Failure graph node — logs the error and sends a WhatsApp alert."""
        logger.error(
            "FailureNode triggered | step=%s | error=%s",
            state.get("plan_type", "N/A"),
            state.get("action_error", "Unknown"),
        )
        result = WhatsAppNode.send_message({**state, "action_failed": True})
        return {**result, "failure_handled": True}
