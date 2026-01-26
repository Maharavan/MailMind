import logging

from schema.DataClassifer import DataClassifier
from schema.DecisionType import DecisionType
from schema.planning_type import PlanningEvent
from workflow.state import WorkflowState

logger = logging.getLogger(__name__)


class PlanningNode:
    """
    Maps a decision + category to a secondary PlanningEvent using deterministic rules.

    AutoReply is always the mandatory first action for AUTO_EXECUTE decisions.
    This node only decides the secondary action that follows the reply.

    REJECT  → IGNORE           (no reply, no action)
    REVIEW  → REQUEST_REVIEW   (no reply, human decides via WhatsApp)
    AUTO_EXECUTE + INTERVIEW → SET_REMINDER
    AUTO_EXECUTE + TASK      → UPDATE_TASK
    AUTO_EXECUTE + other     → IGNORE
    """

    def plan(self, state: WorkflowState) -> WorkflowState:
        decision = state.get("decision")

        if decision == DecisionType.REJECT:
            return {**state, "plan_type": PlanningEvent.IGNORE}

        if decision == DecisionType.REVIEW:
            return {**state, "plan_type": PlanningEvent.REQUEST_REVIEW}

        classification = state.get("classification")
        if classification is None:
            return {**state, "plan_type": PlanningEvent.IGNORE}

        category = classification.category

        if category == DataClassifier.INTERVIEW:
            plan = PlanningEvent.SET_REMINDER
        elif category == DataClassifier.TASK:
            plan = PlanningEvent.UPDATE_TASK
        else:
            plan = PlanningEvent.IGNORE

        logger.info("PlanningNode selected: %s (category=%s)", plan.value, category)
        return {**state, "plan_type": plan}
