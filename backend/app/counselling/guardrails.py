import re
from typing import Final

CRISIS_KEYWORDS: Final[list[str]] = [
    "suicide",
    "suicidal",
    "kill myself",
    "killing myself",
    "end my life",
    "ending my life",
    "self-harm",
    "self harm",
    "harming myself",
    "harming oneself",
    "cutting",
    "overdose",
    "want to die",
    "wants to die",
    "better off dead",
    "ending it all",
    "can't go on",
    "hopeless and giving up",
]

_CRISIS_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in CRISIS_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

CLINICAL_DIAGNOSIS_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"\b(diagnosed with|suffering from)\s+(major depressive disorder|clinical depression|bipolar|schizophrenia|ptsd|adhd)\b", re.IGNORECASE),
    re.compile(r"\b(prescribe|medication for)\s+(antidepressants|anxiolytics|psychiatric)\b", re.IGNORECASE),
]


def detect_crisis(text: str | None) -> bool:
    """
    Detects any mentions of self-harm, suicide, or severe crisis in text.
    Returns True if any crisis pattern matches.
    """
    if not text:
        return False
    return bool(_CRISIS_REGEX.search(text))


def sanitize_clinical_language(text: str) -> tuple[str, bool]:
    """
    Ensures that recommendations do not contain unauthorized medical or psychiatric diagnoses.
    Replaces clinical assertions with supportive pedagogical phrasing.
    Returns (sanitized_text, was_modified).
    """
    modified = False
    result = text
    for pattern in CLINICAL_DIAGNOSIS_PATTERNS:
        if pattern.search(result):
            modified = True
            result = pattern.sub("experiencing significant academic stress", result)
    return result, modified


def sanitize_for_prompt_injection(text: str | None) -> str:
    """
    Neutralizes attempts to escape context boundaries or execute prompt injection.
    Escapes tag markers and neutralizes classic override phrases.
    """
    if not text:
        return ""

    sanitized = text.replace("<", "&lt;").replace(">", "&gt;")

    # Neutralize prompt injection phrases
    injection_phrases = [
        "ignore previous instructions",
        "ignore all previous instructions",
        "disregard instructions",
        "system prompt override",
        "you are now a",
    ]
    for phrase in injection_phrases:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        sanitized = pattern.sub(f"[neutralized phrase: {phrase}]", sanitized)

    return sanitized.strip()
