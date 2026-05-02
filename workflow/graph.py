"""workflow/graph.py — LangGraph StateGraph definition for the email-agent pipeline."""
from typing import Any
from langgraph.graph import StateGraph, START, END

from nodes.auto_reply_node import AutoReplyNode
from nodes.classifer_agent import ClassifierAgent
from nodes.decision_maker_node import DecisionMakerTool
from nodes.extraction_agent import ExtractionAgent
from nodes.failure_node import FailureNode
from nodes.planning_node import PlanningNode
from nodes.remainder_node import RemainderTool
from nodes.research_node import ResearchNode
from nodes.task_node import TaskNode
from nodes.whatsapp_node import WhatsAppNode
from workflow.state import WorkflowState


class WorkflowGraph:
    """Builds and compiles the LangGraph StateGraph for email processing."""

    @staticmethod
    def create() -> Any:
        """
        Build and compile the email-processing StateGraph.

        Entry routing (event_type):
          EMAIL    → Classifier → Extraction → DecisionMaker → Planning
          APPROVED → Planning   (decision=AUTO_EXECUTE already set by caller)
          REJECTED → END

        After Planning:
          IGNORE          → END                   (no reply, no action)
          REQUEST_REVIEW  → Notification → END    (no reply, human decides)
          SET_REMINDER    → AutoReply → Reminder  (reply first, then calendar)
          UPDATE_TASK     → AutoReply → Task      (reply first, then Trello)

        AutoReply failures route to Failure node and stop; secondary action is skipped.
        """
        classifier_agent = ClassifierAgent()
        extraction_agent = ExtractionAgent()
        planning_node = PlanningNode()
        research_node = ResearchNode()

        build = StateGraph(WorkflowState)

        build.add_node("Classifier", classifier_agent.classify_email)
        build.add_node("Extraction", extraction_agent.extract_info)
        build.add_node("DecisionMaker", DecisionMakerTool.make_decision)
        build.add_node("Planning", planning_node.plan)
        build.add_node("AutoReply", AutoReplyNode.execute)
        build.add_node("Research", research_node.research)
        build.add_node("Task", TaskNode.execute)
        build.add_node("Reminder", RemainderTool.execute)
        build.add_node("Notification", WhatsAppNode.send_message)
        build.add_node("Failure", FailureNode.handle)

        build.add_conditional_edges(
            START,
            lambda state: state.get("event_type", "EMAIL"),
            {
                "EMAIL": "Classifier",
                "APPROVED": "Planning",
                "REJECTED": END,
            },
        )

        build.add_edge("Classifier", "Extraction")
        build.add_edge("Extraction", "DecisionMaker")
        build.add_edge("DecisionMaker", "Planning")

        build.add_conditional_edges(
            "Planning",
            lambda state: state["plan_type"],
            {
                "UPDATE_TASK": "AutoReply",
                "SET_REMINDER": "AutoReply",
                "REQUEST_REVIEW": "Notification",
                "IGNORE": END,
            },
        )

        def _after_reply_router(state: WorkflowState) -> str:
            if state.get("action_failed"):
                return "FAILED"
            return state["plan_type"]

        build.add_conditional_edges(
            "AutoReply",
            _after_reply_router,
            {
                "FAILED": "Failure",
                "SET_REMINDER": "Research",
                "UPDATE_TASK": "Research",
            },
        )

        # Research always routes onward to the correct action node.
        build.add_conditional_edges(
            "Research",
            lambda state: state["plan_type"],
            {
                "SET_REMINDER": "Reminder",
                "UPDATE_TASK": "Task",
            },
        )

        def _action_router(state: WorkflowState) -> str:
            return "FAILED" if state.get("action_failed") else "OK"

        _action_outcomes = {"OK": END, "FAILED": "Failure"}

        for node in ("Reminder", "Task"):
            build.add_conditional_edges(node, _action_router, _action_outcomes)

        build.add_edge("Notification", END)
        build.add_edge("Failure", END)

        return build.compile()
