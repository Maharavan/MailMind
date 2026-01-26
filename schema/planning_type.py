from enum import Enum
class PlanningEvent(str, Enum):
    """Dictates the secondary action after AutoReply runs (which is always mandatory for AUTO_EXECUTE)."""
    UPDATE_TASK = "UPDATE_TASK"
    SET_REMINDER = "SET_REMINDER"
    REQUEST_REVIEW = "REQUEST_REVIEW"
    IGNORE = "IGNORE"
