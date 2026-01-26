from pydantic import BaseModel, Field
from schema import PriorityClassifier
from schema.DataClassifer import DataClassifier
from schema.PriorityClassifier import PriorityClassifier

class ClassificationResult(BaseModel):
    category: DataClassifier = DataClassifier.NOT_CLASSIFIED
    priority: PriorityClassifier
    confidence: float = Field(ge=0.0,le=1.0)
