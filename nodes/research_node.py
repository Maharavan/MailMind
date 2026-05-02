"""nodes/research_node.py — Research & action-plan synthesis using Tavily + Groq."""
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from config.settings import settings
from schema.DataClassifer import DataClassifier
from tools.tavily_tool import format_results_for_llm, tavily_search
from workflow.state import WorkflowState

logger = logging.getLogger(__name__)

_INTERVIEW_SYSTEM = """You are a career preparation assistant.
Given web search results about a company and role, produce a concise interview prep plan.

Structure your response in markdown with these sections:
## Company Overview
(2-3 sentences about the company from search results)

## Likely Interview Topics
(5-7 bullet points based on role and company)

## Preparation Steps
(numbered action items the candidate should do before the interview)

## Useful Resources
(list the most relevant links from search results as markdown links)

Keep the entire response under 400 words. Be specific and actionable."""

_TASK_SYSTEM = """You are a productivity and technical planning assistant.
Given web search results about a task or assessment, produce a concrete action plan.

Structure your response in markdown with these sections:
## Task Overview
(1-2 sentences summarising what needs to be done)

## Recommended Approach
(numbered steps to complete the task efficiently)

## Key Resources
(list the most relevant links from search results as markdown links)

## Time Breakdown
(rough time estimate per step)

Keep the entire response under 400 words. Be specific and actionable."""


class ResearchNode:
    """Runs Tavily searches and synthesises an LLM action plan before tool execution."""

    def __init__(self, llm=None):
        self._llm = llm

    @property
    def llm(self) -> ChatGroq:
        if self._llm is None:
            self._llm = ChatGroq(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                temperature=0.3,
                api_key=settings.GROQ_API_KEY,
            )
        return self._llm

    # ------------------------------------------------------------------
    # Graph node entry point
    # ------------------------------------------------------------------

    def research(self, state: WorkflowState) -> dict:
        try:
            classification = state.get("classification")
            extracted = state.get("extracted_data")

            if not extracted:
                logger.info("ResearchNode: no extracted_data — skipping research")
                return {**state, "research_result": None}

            category = classification.category if classification else None
            company = getattr(extracted, "company", None) or "Unknown"
            role = getattr(extracted, "role", None) or "Unknown"

            if category == DataClassifier.INTERVIEW:
                plan = self._research_interview(company, role)
            else:
                task_desc = getattr(extracted, "task_description", None) or role
                plan = self._research_task(task_desc, company, role)

            logger.info("ResearchNode: plan generated (%d chars)", len(plan))
            return {**state, "research_result": plan}

        except Exception as e:
            logger.exception("ResearchNode failed: %s", e)
            return {**state, "research_result": None}

    # ------------------------------------------------------------------
    # Interview research
    # ------------------------------------------------------------------

    def _research_interview(self, company: str, role: str) -> str:
        q1 = f"{company} {role} interview questions"
        q2 = f"{company} engineering culture interview process"

        r1 = tavily_search(q1, max_results=4)
        r2 = tavily_search(q2, max_results=3)
        combined = r1 + r2

        web_context = format_results_for_llm(combined)
        user_msg = (
            f"Company: {company}\nRole: {role}\n\n"
            f"Web search results:\n{web_context}\n\n"
            "Generate a focused interview preparation plan."
        )

        response = self.llm.invoke([
            SystemMessage(content=_INTERVIEW_SYSTEM),
            HumanMessage(content=user_msg),
        ])
        return response.content.strip()

    # ------------------------------------------------------------------
    # Task research
    # ------------------------------------------------------------------

    def _research_task(self, task_description: str, company: str, role: str) -> str:
        q1 = f"{task_description} tutorial guide how to"
        q2 = f"{role} assessment best practices {company}"

        r1 = tavily_search(q1, max_results=4)
        r2 = tavily_search(q2, max_results=3)
        combined = r1 + r2

        web_context = format_results_for_llm(combined)
        user_msg = (
            f"Task: {task_description}\nRole: {role}\nCompany: {company}\n\n"
            f"Web search results:\n{web_context}\n\n"
            "Generate a focused action plan to complete this task/assessment."
        )

        response = self.llm.invoke([
            SystemMessage(content=_TASK_SYSTEM),
            HumanMessage(content=user_msg),
        ])
        return response.content.strip()
