from pydantic import BaseModel


class ExtractionResult(BaseModel):
    """Common fields shared by all email categories."""
    company: str | None = None
    role: str | None = None
    deadline: str | None = None
    requires_response: bool | None = None
    suggested_reply: str | None = None


class InterviewExtractionResult(ExtractionResult):
    meeting_at: str | None = None
    timezone: str | None = None
    meeting_link: str | None = None


class TaskExtractionResult(ExtractionResult):
    task_description: str | None = None
    estimated_time: str | None = None
    dependencies: str | None = None
