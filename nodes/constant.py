from schema.DataClassifer import DataClassifier

CATEGORY_MAPPING = {
    "assessment": DataClassifier.TASK,  # assessments are treated as tasks
    "interview": DataClassifier.INTERVIEW,
    "task": DataClassifier.TASK,
}

PHRASE_PATTERNS = {
    DataClassifier.INTERVIEW: [
        r"interview\s+(scheduled|invitation|slot|time)",
        r"(schedule|reschedule)\s+an?\s+interview",
        r"meet\s+with\s+(the\s+)?(team|hiring\s+manager)",
        r"screening\s+call",
    ],
    DataClassifier.TASK: [
        r"task\s+(assigned|due|deadline)",
        r"complete\s+the\s+task",
        r"work\s+assignment",
        r"(complete|take|submit)\s+(the\s+)?(assessment|test|exam|quiz)",
        r"assessment\s+(due|deadline|link)",
        r"test\s+link",
    ],
}

PRIORITY_PATTERNS = {
    "HIGH": [
        r"\burgent\b",
        r"\basap\b",
        r"\bimmediately\b",
        r"\bright away\b",
        r"\baction required\b",
        r"\brespond immediately\b",
        r"\btime[-\s]?sensitive\b",
        r"\bpriority\b",
    ],
    "DEADLINE": [
        r"\bdeadline\b",
        r"\bdue (today|tomorrow)\b",
        r"\bdue by\b",
        r"\bno later than\b",
        r"\bbefore \d{1,2}(:\d{2})?\s?(am|pm)?\b",
        r"\bwithin \d+ (hours?|days?)\b",
        r"\bby (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    ],
    "MEDIUM": [
        r"\bplease respond\b",
        r"\bkindly complete\b",
        r"\brequest\b",
        r"\breminder\b",
        r"\bfollow[-\s]?up\b",
    ],
    "LOW": [
        r"\bfor your information\b",
        r"\bfyi\b",
        r"\bno action required\b",
        r"\boptional\b",
        r"\bjust letting you know\b",
        r"\bnot urgent\b",
    ],
}

PRIORITY_SCORES = {
    "HIGH": 3.0,
    "DEADLINE": 2.0,
    "MEDIUM": 1.0,
    "LOW": 0.0,
}

SENSITIVE_CATEGORIES = {
    DataClassifier.INTERVIEW,
    DataClassifier.TASK,
}

NEGATION_PATTERNS = [
    r"\bnot\s+urgent\b",
    r"\bno\s+urgent\s+action\b",
    r"\bnot\s+time[-\s]?sensitive\b",
    r"\bno\s+action\s+required\b",
    r"\bno\s+further\s+action\s+required\b",
    r"\bno\s+response\s+required\b",
    r"\bno\s+reply\s+needed\b",
    r"\bno\s+need\s+to\s+respond\b",
    r"\boptional\b",
    r"\bat\s+your\s+discretion\b",
    r"\bif\s+you\s+wish\b",
    r"\bif\s+you\s+would\s+like\b",
    r"\bfor\s+your\s+information\b",
    r"\bfyi\b",
    r"\bjust\s+letting\s+you\s+know\b",
    r"\bnot\s+required\b",
    r"\bnot\s+mandatory\b",
    r"\bno\s+obligation\b",
]