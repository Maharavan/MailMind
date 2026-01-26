from enum import Enum


class PriorityClassifier(str,Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"