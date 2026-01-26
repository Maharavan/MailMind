from enum import Enum

class DecisionType(str, Enum):
    AUTO_EXECUTE = "AUTO_EXECUTE"
    REVIEW = "REVIEW"
    REJECT = "REJECT"