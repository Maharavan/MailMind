from typing import Optional

from config.settings import settings
from schema.DataClassifer import DataClassifier
from schema.DecisionType import DecisionType
from schema.OutputClassifer import ClassificationResult
from schema.mail_extractor import ExtractionResult
from workflow.state import WorkflowState


class DecisionMakerTool:
    """Evaluates a classified email and returns a DecisionType for downstream planning."""

    @staticmethod
    def _confidence_decision(confidence: float) -> DecisionType:
        """Map a raw confidence score to AUTO_EXECUTE, REVIEW, or REJECT."""
        if confidence >= settings.AUTO_EXECUTE_THRESHOLD:
            return DecisionType.AUTO_EXECUTE
        if confidence >= settings.REVIEW_THRESHOLD:
            return DecisionType.REVIEW
        return DecisionType.REJECT

    @staticmethod
    def _get_best_decision(
        classification: ClassificationResult,
        extracted_data: Optional[ExtractionResult],
        calendar_conflict: dict,
    ) -> DecisionType:
        """
        Derive the best DecisionType based on classification, extracted fields,
        and calendar conflicts.

        Interviews are never rejected outright — REVIEW is the floor regardless
        of confidence, because a missed interview is worse than a spurious ping.
        """
        confidence: float = classification.confidence
        category: DataClassifier = classification.category
        meeting_at: Optional[str] = getattr(extracted_data, "meeting_at", None) if extracted_data else None
        requires_response: bool = (
            extracted_data.requires_response if extracted_data else False
        ) or False

        has_conflict: bool = calendar_conflict.get("has_conflict", False)
        has_alternate: bool = bool(calendar_conflict.get("alternate_time"))

        if category == DataClassifier.INTERVIEW:
            if requires_response and not meeting_at:
                if confidence >= settings.AUTO_EXECUTE_THRESHOLD:
                    return DecisionType.AUTO_EXECUTE
                return DecisionType.REVIEW  # floor: interviews never rejected outright
            if not meeting_at:
                return DecisionType.REVIEW
            if has_conflict and not has_alternate:
                return DecisionType.REVIEW
            return DecisionMakerTool._confidence_decision(confidence)

        return DecisionMakerTool._confidence_decision(confidence)

    @staticmethod
    def make_decision(state: WorkflowState) -> WorkflowState:
        """
        DecisionMaker graph node — sets state['decision'].

        Short-circuits to REJECT for unclassified emails and to REVIEW when
        extraction failed, since auto-executing without structured fields is unsafe.
        """
        classification = state.get("classification")
        if not classification or classification.category is DataClassifier.NOT_CLASSIFIED:
            return {**state, "decision": DecisionType.REJECT}

        extracted_data = state.get("extracted_data")
        if not extracted_data:
            return {**state, "decision": DecisionType.REVIEW}

        calendar_conflict = state.get("calendar_conflict", {})

        decision = DecisionMakerTool._get_best_decision(
            classification, extracted_data, calendar_conflict
        )
        return {**state, "decision": decision}
