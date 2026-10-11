"""Heuristic prompt-injection and jailbreak guard.

Regex rules run first (fast, deterministic). The module is intentionally
modular: an LLM-based classifier can be added later by appending another
detector stage inside ``GuardService.inspect``.
"""

import re
from dataclasses import dataclass

# (label, weight, compiled pattern). Weight drives the risk score.
_RULES: list[tuple[str, int, re.Pattern]] = [
    (
        "instruction_override",
        3,
        re.compile(
            r"(ignore|disregard)\s+(all\s+)?(the\s+|previous\s+|prior\s+)*instructions",
            re.IGNORECASE,
        ),
    ),
    (
        "system_prompt_disclosure",
        3,
        re.compile(
            r"(reveal|print|show|output|repeat|display)\s+(me\s+)?(your\s+|the\s+)?system\s*prompt",
            re.IGNORECASE,
        ),
    ),
    (
        "role_hijack",
        1,
        re.compile(r"you\s+are\s+now", re.IGNORECASE),
    ),
    (
        "unrestricted_mode",
        3,
        re.compile(r"act\s+as\s+(an?\s+)?unrestricted", re.IGNORECASE),
    ),
    (
        "guard_bypass",
        3,
        re.compile(
            r"bypass\s+(the\s+)?(security\s+)?(filters?|controls?|guard)",
            re.IGNORECASE,
        ),
    ),
    (
        "document_exfiltration",
        3,
        re.compile(
            r"(output|print|show|dump)\s+(the\s+)?(full|entire|whole)\s+document",
            re.IGNORECASE,
        ),
    ),
    (
        "sensitive_data_probe",
        3,
        re.compile(
            r"(show|reveal|expose)\s+(hidden\s+)?sensitive\s+(data|information|info)",
            re.IGNORECASE,
        ),
    ),
    (
        "data_exfiltration",
        2,
        re.compile(r"send\s+(this\s+)?data\s+to", re.IGNORECASE),
    ),
    (
        "document_upload",
        2,
        re.compile(r"upload\s+(this\s+)?document\s+to", re.IGNORECASE),
    ),
]

_HIGH_THRESHOLD = 3


@dataclass
class GuardVerdict:
    allowed: bool
    risk_level: str
    reasons: list[str]
    score: int


class GuardService:
    def inspect(self, text: str) -> GuardVerdict:
        reasons: list[str] = []
        score = 0
        for label, weight, pattern in _RULES:
            if pattern.search(text):
                reasons.append(label)
                score += weight

        if score >= _HIGH_THRESHOLD:
            risk_level = "high"
        elif score > 0:
            risk_level = "medium"
        else:
            risk_level = "low"

        return GuardVerdict(
            allowed=risk_level != "high",
            risk_level=risk_level,
            reasons=reasons,
            score=score,
        )


guard_service = GuardService()
