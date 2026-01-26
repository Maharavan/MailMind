from enum import Enum

class DataClassifier(str,Enum):
    INTERVIEW = "interview"
    TASK = "task"
    NOT_CLASSIFIED = "not_classified"
