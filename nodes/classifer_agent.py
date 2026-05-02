import logging
import re
from collections import defaultdict

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers.pydantic import PydanticOutputParser

from config.settings import settings
from schema.DataClassifer import DataClassifier
from schema.PriorityClassifier import PriorityClassifier
from schema.OutputClassifer import ClassificationResult
from nodes.constant import (
    NEGATION_PATTERNS,
    PHRASE_PATTERNS,
    PRIORITY_PATTERNS,
    PRIORITY_SCORES,
    SENSITIVE_CATEGORIES,
    CATEGORY_MAPPING,
)
from workflow.state import WorkflowState

logger = logging.getLogger(__name__)


class ClassifierAgent:
    """
    Hybrid email classifier: rule-based pattern matching with an LLM fallback
    for low-confidence cases (confidence < 0.7).

    The LLM is lazily initialised — only created on the first low-confidence email.
    """

    def __init__(self, llm=None):
        self._llm = llm

    @property
    def llm(self) -> ChatGroq | None:
        """Lazy LLM initialisation — only created when first needed."""
        if self._llm is None and settings.GROQ_API_KEY:
            self._llm = ChatGroq(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                temperature=0,
                api_key=settings.GROQ_API_KEY,
            )
        return self._llm

    def classify_email(self, state: WorkflowState) -> dict:
        """
        Classifier graph node — sets state['classification'].

        Runs rule-based classification first; falls back to LLM when
        rule-based confidence is below 0.7.
        """
        email = state["email_data"]
        content = email.body_text or ""

        rules_result = self.rules_classification(content)

        if rules_result.confidence >= 0.7:
            return {**state, "classification": rules_result}

        if self.llm:
            llm_result = self.call_llm(content)
            classification = self.choose_better(rules_result, llm_result)
        else:
            classification = rules_result

        return {**state, "classification": classification}

    def rules_classification(self, content: str) -> ClassificationResult:
        """Score the email against phrase patterns and return a ClassificationResult."""
        category_match = defaultdict(int)

        for category, patterns in PHRASE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    category_match[category] += 1

        if not category_match:
            return ClassificationResult(
                category=DataClassifier.NOT_CLASSIFIED,
                priority=PriorityClassifier.LOW,
                confidence=0.0,
            )

        total_matches = sum(category_match.values())
        best_category = max(category_match, key=category_match.get)
        confidence = category_match[best_category] / total_matches
        priority = self._detect_priority(content, best_category=best_category)

        return ClassificationResult(
            category=best_category,
            priority=priority,
            confidence=round(confidence, 2),
        )

    def _detect_priority(self, content: str, best_category) -> PriorityClassifier:
        """
        Weighted priority detection:
          1. If a negation pattern matches → always LOW
          2. Sum scores across all matching priority pattern groups
          3. If the category is sensitive and score > 0, boost to at least MEDIUM
          4. Map final score to HIGH / MEDIUM / LOW
        """
        for pattern in NEGATION_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return PriorityClassifier.LOW

        score = 0.0
        for group, patterns in PRIORITY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    score += PRIORITY_SCORES[group]
                    break

        if best_category in SENSITIVE_CATEGORIES and score > 0:
            score = max(score, PRIORITY_SCORES["MEDIUM"])

        if score >= PRIORITY_SCORES["HIGH"]:
            return PriorityClassifier.HIGH
        if score >= PRIORITY_SCORES["MEDIUM"]:
            return PriorityClassifier.MEDIUM
        return PriorityClassifier.LOW

    def call_llm(self, content: str) -> ClassificationResult:
        """Ask the LLM to classify the email and parse the structured response."""
        parser = PydanticOutputParser(pydantic_object=ClassificationResult)
        prompt = PromptTemplate.from_template(
            """Classify the email into one of these categories:
interview, task.
Use 'task' for assessments, tests, assignments, and work tasks.
If it doesn't fit any, use 'not_classified'.

Assign:
- priority: high, medium, or low
- confidence: a float from 0.0 to 1.0 reflecting how certain you are.
  Use 1.0 only if the email is unambiguously about that category.
  Use 0.5-0.7 for probable matches. Use below 0.5 if unsure.

{format_instructions}

Email:
{content}"""
        )
        try:
            response = self.llm.invoke(
                prompt.format(content=content, format_instructions=parser.get_format_instructions())
            )
            raw = response.content.strip().replace("```json", "").replace("```", "").strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                raise ValueError("No JSON found in LLM response")
            return parser.parse(match.group(0))
        except Exception:
            logger.exception("Unexpected error during LLM classification")

        return ClassificationResult(
            category=DataClassifier.NOT_CLASSIFIED,
            priority=PriorityClassifier.LOW,
            confidence=0.0,
        )

    @staticmethod
    def choose_better(
        rules_result: ClassificationResult,
        llm_result: ClassificationResult,
    ) -> ClassificationResult:
        """Prefer results with a valid category; break ties by confidence."""
        rules_has_category = rules_result.category is not None
        llm_has_category = llm_result.category is not None

        if llm_has_category and not rules_has_category:
            return llm_result
        if rules_has_category and not llm_has_category:
            return rules_result

        return llm_result if llm_result.confidence > rules_result.confidence else rules_result
