import ast
import json
import logging
import re
from datetime import datetime, timezone, timedelta

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from pydantic import ValidationError

from config.settings import settings
from schema.DataClassifer import DataClassifier
from schema.mail_extractor import InterviewExtractionResult, TaskExtractionResult
from tools.calendar_tool import check_calendar_conflict
from workflow.state import WorkflowState

logger = logging.getLogger(__name__)


@tool
def check_conflict(meeting_time_iso: str) -> dict:
    """
    Check if a meeting time has a Google Calendar conflict and find the next free slot.

    Args:
        meeting_time_iso: ISO datetime string e.g. "2026-05-02T10:00:00+00:00"

    Returns:
        {"has_conflict": bool, "alternate_time": str | None}

    Call this whenever you extract a non-null meeting_at.
    """
    return check_calendar_conflict(meeting_time_iso)


def _date_context() -> dict:
    today = datetime.now(timezone.utc).date()
    today_end = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59)
    return {
        "today": today.isoformat(),
        "today_end": today_end.isoformat(),
        "tomorrow": (today + timedelta(days=1)).isoformat(),
        "next_week": (today + timedelta(days=7)).isoformat(),
    }


def _build_interview_system_prompt() -> str:
    d = _date_context()
    return f"""You are an email information extraction agent for INTERVIEW emails.

CURRENT DATE: {d['today']} (UTC)

DATE RESOLUTION — resolve relative references to these exact dates:
- "tomorrow" / "tmrw" / "next day" → {d['tomorrow']}
- "today" / "this day" → {d['today']}
- "end of today" / "by end of day" / "EOD" → {d['today_end']}
- "next week" → {d['next_week']}

WORKFLOW:
1. Extract all structured fields from the email.
2. If meeting_at is non-null, call the check_conflict tool with that ISO datetime.
3. If check_conflict returns has_conflict=true, update suggested_reply to mention the
   conflict and include the alternate_time if provided.
4. Return ONLY a valid JSON object — no markdown fences, no explanation.

FIELDS TO EXTRACT:
- meeting_at: YYYY-MM-DDTHH:MM:SS+HH:MM — requires BOTH date AND time, else null
- timezone: only if explicitly stated in email, else null
- deadline: YYYY-MM-DDTHH:MM:SS+HH:MM — response deadline if stated, else null
- meeting_link: URL if present in email, else null
- company: sender's company or organization, else null
- role: job role or position being discussed, else null
- requires_response: true if email asks for confirmation, availability, or a reply
- suggested_reply: only when requires_response=true; start with "Thanks for the mail.";
  no greeting, no signature

STRICT RULES:
- Extract ONLY explicitly stated values — do NOT infer or guess
- If unsure → null
- Times without timezone → assume UTC (+00:00)
- Output must be a single JSON object starting with {{ and ending with }}"""


def _build_task_system_prompt() -> str:
    d = _date_context()
    return f"""You are an email information extraction agent for TASK and ASSESSMENT emails.

CURRENT DATE: {d['today']} (UTC)

DATE RESOLUTION — resolve relative references to these exact dates:
- "tomorrow" / "tmrw" / "next day" → {d['tomorrow']}
- "today" / "this day" → {d['today']}
- "end of today" / "by end of day" / "EOD" → {d['today_end']}
- "next week" → {d['next_week']}

Return ONLY a valid JSON object — no markdown fences, no explanation.

FIELDS TO EXTRACT:
- company: sender's company or organization, else null
- role: task name, assessment title, or job role, else null
- deadline: YYYY-MM-DDTHH:MM:SS+HH:MM — submission/completion deadline; if time missing use 23:59:00; no tz → +00:00; else null
- task_description: concise summary of what needs to be done (1-3 sentences), else null
- estimated_time: human-readable time estimate if stated (e.g. "2 hours", "3 days"), else null
- dependencies: blockers, prerequisites, or required resources if stated, else null
- requires_response: true if email asks for acknowledgement or a reply
- suggested_reply: only when requires_response=true; start with "Thanks for the mail.";
  no greeting, no signature

STRICT RULES:
- Extract ONLY explicitly stated values — do NOT infer or guess
- If unsure → null
- Times without timezone → assume UTC (+00:00)
- Output must be a single JSON object starting with {{ and ending with }}"""


def _to_utc(iso_str: str | None) -> str | None:
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str).astimezone(timezone.utc).isoformat()
    except Exception:
        logger.warning("Failed to convert to UTC: %s", iso_str)
        return None


def _parse_conflict_from_messages(messages: list) -> dict:
    """Extract calendar conflict result from ToolMessage in agent output."""
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "tool":
            try:
                content = msg.content
                if isinstance(content, dict) and "has_conflict" in content:
                    return content
                if isinstance(content, str):
                    for parser in (json.loads, ast.literal_eval):
                        try:
                            result = parser(content)
                            if isinstance(result, dict) and "has_conflict" in result:
                                return result
                        except Exception:
                            continue
            except Exception:
                pass
    return {"has_conflict": False, "alternate_time": None}


def _extract_json(text: str) -> dict | None:
    clean = re.sub(r"```json\s*|\s*```", "", text).strip()
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


class ExtractionAgent:
    """
    Extracts structured fields from email using Groq LLM.

    - INTERVIEW: ReAct agent with check_conflict tool → InterviewExtractionResult
    - TASK: direct LLM call (no tools needed) → TaskExtractionResult
    """

    def __init__(self, llm=None):
        self._llm = llm
        self._interview_agent = None

    @property
    def llm(self) -> ChatGroq:
        if self._llm is None:
            self._llm = ChatGroq(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                temperature=0,
                api_key=settings.GROQ_API_KEY,
            )
        return self._llm

    @property
    def interview_agent(self):
        if self._interview_agent is None:
            self._interview_agent = create_react_agent(self.llm, tools=[check_conflict])
        return self._interview_agent

    # ------------------------------------------------------------------
    # Public graph node entry point
    # ------------------------------------------------------------------

    def extract_info(self, state: WorkflowState) -> dict:
        classification = state.get("classification")
        if classification is None or classification.category is DataClassifier.NOT_CLASSIFIED:
            logger.info("Skipping extraction: not classified")
            return {**state, "extracted_data": None}

        email = state["email_data"]
        content = email.body_text or email.body_html or ""
        if not content.strip():
            logger.warning("ExtractionAgent: empty email body")
            return {**state, "extracted_data": None}

        if classification.category == DataClassifier.INTERVIEW:
            return self._extract_interview(state, content)
        return self._extract_task(state, content)

    # ------------------------------------------------------------------
    # Category-specific extraction paths
    # ------------------------------------------------------------------

    def _extract_interview(self, state: WorkflowState, content: str) -> dict:
        try:
            result = self.interview_agent.invoke({
                "messages": [
                    SystemMessage(content=_build_interview_system_prompt()),
                    HumanMessage(content=content),
                ]
            })

            data = _extract_json(result["messages"][-1].content)
            if data is None:
                logger.error("No JSON in interview agent response")
                return {**state, "extracted_data": None}

            data["requires_response"] = bool(data.get("requires_response"))
            data["meeting_at"] = _to_utc(data.get("meeting_at"))
            data["deadline"] = _to_utc(data.get("deadline"))

            calendar_conflict = _parse_conflict_from_messages(result["messages"])
            logger.info("Calendar conflict result: %s", calendar_conflict)

            if calendar_conflict.get("has_conflict") and data.get("meeting_at"):
                if "conflict" not in (data.get("suggested_reply") or "").lower():
                    alt = calendar_conflict.get("alternate_time")
                    base = (data.get("suggested_reply") or "Thanks for the mail.").rstrip(".")
                    suffix = (
                        f" However, I have a conflict at the proposed time."
                        f" Could we reschedule to {alt} UTC instead?"
                        if alt
                        else " However, I have a conflict at the proposed time."
                        " Could you suggest an alternate slot?"
                    )
                    data["suggested_reply"] = base + "." + suffix
                    data["requires_response"] = True

            extracted = InterviewExtractionResult(**data)
            logger.info("Interview extraction: %s", extracted)
            return {**state, "extracted_data": extracted, "calendar_conflict": calendar_conflict}

        except ValidationError as e:
            logger.warning("Interview extraction validation failed: %s", e)
        except Exception as e:
            logger.exception("Interview extraction error: %s", str(e))

        return {**state, "extracted_data": None}

    def _extract_task(self, state: WorkflowState, content: str) -> dict:
        try:
            response = self.llm.invoke([
                SystemMessage(content=_build_task_system_prompt()),
                HumanMessage(content=content),
            ])

            data = _extract_json(response.content)
            if data is None:
                logger.error("No JSON in task extraction response")
                return {**state, "extracted_data": None}

            data["requires_response"] = bool(data.get("requires_response"))
            data["deadline"] = _to_utc(data.get("deadline"))

            extracted = TaskExtractionResult(**data)
            logger.info("Task extraction: %s", extracted)
            return {**state, "extracted_data": extracted, "calendar_conflict": {}}

        except ValidationError as e:
            logger.warning("Task extraction validation failed: %s", e)
        except Exception as e:
            logger.exception("Task extraction error: %s", str(e))

        return {**state, "extracted_data": None}
