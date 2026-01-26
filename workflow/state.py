from typing import TypedDict
from schema.email_dto import EmailDTO
from schema.DecisionType import DecisionType
from schema.OutputClassifer import ClassificationResult
from schema.mail_extractor import InterviewExtractionResult, TaskExtractionResult
from schema.planning_type import PlanningEvent


class WorkflowState(TypedDict, total=False):
    """
    WorkflowState defines the structure of the state used in the workflow graph.
    It includes the email content that will be processed by the agents in the workflow.
    """
    event_type: str
    email_data: EmailDTO

    classification: ClassificationResult | None
    decision: DecisionType | None
    extracted_data: InterviewExtractionResult | TaskExtractionResult | None
    plan_type: PlanningEvent

    concurrent_meeting: bool   
    calendar_conflict: dict 

    task_created: bool
    task_url: str
    task_reason: str 

    action_failed: bool
    action_error: str
    failure_handled: bool
    whatsapp_message: str
    execution_result: str | None
    error: str | None