"""Heuristic prompt-injection and jailbreak guard.

Each rule contributes points to a 0–100 risk score. A request is blocked when the
score reaches ``block_threshold``. Rules also carry a category so callers can
report *what kind* of threat was seen, not just how severe it looked.

Evasion handling runs before matching: zero-width/invisible characters are
stripped, letter-spacing is collapsed, and unicode-escape or base64 payloads are
decoded and re-scanned, so a disguised instruction still trips the same rules.

Regex rules are fast and deterministic. The module is intentionally modular: an
LLM-based classifier can be added later as another detector stage inside
``GuardService.inspect``.
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass, field

# (label, category, points, compiled pattern). Points sum toward the 0–100 score.
_RULES: list[tuple[str, str, int, re.Pattern]] = [
    (
        "instruction_override",
        "instruction_override",
        45,
        re.compile(
            r"(ignore|disregard|forget)\s+(all\s+)?(the\s+|previous\s+|prior\s+|above\s+)*"
            r"(instructions|prompts?|rules|context)",
            re.IGNORECASE,
        ),
    ),
    (
        "system_prompt_disclosure",
        "prompt_disclosure",
        45,
        re.compile(
            r"(reveal|print|show|output|repeat|display|expose)\s+(me\s+)?(your\s+|the\s+)?"
            r"(system\s*prompt|initial\s+instructions|hidden\s+instructions)",
            re.IGNORECASE,
        ),
    ),
    (
        "role_hijack",
        "role_hijack",
        20,
        re.compile(r"you\s+are\s+now", re.IGNORECASE),
    ),
    (
        "unrestricted_mode",
        "jailbreak",
        45,
        re.compile(r"act\s+as\s+(an?\s+)?(unrestricted|unfiltered|uncensored)", re.IGNORECASE),
    ),
    (
        "guard_bypass",
        "guard_bypass",
        45,
        re.compile(
            r"(bypass|disable|ignore|circumvent|turn\s+off|remove)\s+(the\s+)?"
            r"(safety\s+|security\s+|content\s+)?(filters?|controls?|guard|guardrails?|checks?|restrictions?)",
            re.IGNORECASE,
        ),
    ),
    (
        "document_exfiltration",
        "exfiltration",
        40,
        re.compile(
            r"(output|print|show|dump|expose)\s+(the\s+)?(full|entire|whole|raw)\s+document",
            re.IGNORECASE,
        ),
    ),
    (
        "sensitive_data_probe",
        "sensitive_data_probe",
        40,
        re.compile(
            r"(show|reveal|expose|give)\s+(me\s+)?(the\s+|all\s+|any\s+)?"
            r"(hidden\s+|stored\s+|raw\s+)?sensitive\s+(data|information|info)",
            re.IGNORECASE,
        ),
    ),
    (
        "data_exfiltration",
        "exfiltration",
        30,
        re.compile(r"(send|forward|email|post)\s+(this\s+)?(data|document|file|text)\s+to", re.IGNORECASE),
    ),
    (
        "document_upload",
        "exfiltration",
        30,
        re.compile(r"upload\s+(this\s+)?document\s+to", re.IGNORECASE),
    ),
    # --- synonym / paraphrase overrides (the base rule only knew ignore|disregard|forget)
    (
        "instruction_override_synonym",
        "instruction_override",
        45,
        re.compile(
            r"\b(override|discard|replace|supersede)\s+(the\s+|your\s+|all\s+|any\s+)*"
            r"(previous\s+|prior\s+|earlier\s+|existing\s+|above\s+)*"
            r"(instructions|directives|prompts?|rules|guidelines)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "instruction_override_new",
        "instruction_override",
        45,
        re.compile(
            r"(\b(new|updated)\s+instructions?\s*[:\-]"
            r"|as\s+(your\s+|the\s+)?(new|updated)\s+instructions)",
            re.IGNORECASE,
        ),
    ),
    (
        "instruction_override_notfollow",
        "instruction_override",
        45,
        re.compile(
            r"\b(do\s+not|don'?t|stop)\s+follow(ing)?\s+(the\s+)?"
            r"(earlier|previous|prior|above|system|original)\s+"
            r"(instructions|directives|rules|prompts?)\b",
            re.IGNORECASE,
        ),
    ),
    # --- non-English overrides (the base rules are English-only)
    (
        "multilingual_override",
        "instruction_override",
        45,
        re.compile(
            r"(ignoriere|ignorier|ignorieren|vergiss|vergesse|vergessen|missachte|missachten"
            r"|übergehe|übergehen|ignorez|oubliez|négligez|ignora|ignoren|olvida|omita)"
            r"\w*[\s\S]{0,40}?"
            r"(anweisung\w*|regel\w*|instruktion\w*|vorgabe\w*|consigne\w*|instruction\w*"
            r"|directive\w*|r[èe]gle\w*|regla\w*|instrucci\w*|indicaci\w*|directri\w*)",
            re.IGNORECASE,
        ),
    ),
    (
        "multilingual_new_instruction",
        "instruction_override",
        45,
        re.compile(r"\bneue\s+anweisung\b", re.IGNORECASE),
    ),
    # --- prompt disclosure, paraphrased
    (
        "prompt_disclosure_ask",
        "prompt_disclosure",
        45,
        re.compile(
            r"(reveal|print|show|output|repeat|display|expose|tell|list|give)\s+(me\s+)?"
            r"(your\s+|the\s+)?(rules|guidelines|instructions|prompts?|system\s*prompt|directives)",
            re.IGNORECASE,
        ),
    ),
    (
        "prompt_disclosure_interrogate",
        "prompt_disclosure",
        45,
        re.compile(
            r"\b(what|which)\s+(are|were)\s+(your|the)\s+(rules|instructions|guidelines|prompts?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "prompt_disclosure_repeat_above",
        "prompt_disclosure",
        45,
        re.compile(
            r"(repeat|show|print|output|reveal)\s+(everything|all|the\s+(full\s+)?text|the\s+words)\b"
            r"[\s\S]{0,30}?(above|before|preceding|prior)",
            re.IGNORECASE,
        ),
    ),
    # --- role-play jailbreaks
    (
        "roleplay_jailbreak",
        "jailbreak",
        45,
        re.compile(
            r"\b(pretend|imagine|roleplay|role-play)\s+(you\s+are|you'?re|to\s+be|as)\b"
            r"[\s\S]{0,60}?"
            r"(no\s+(restrictions|rules|limits|filters)|without\s+(any\s+)?(restrictions|rules|limits|filters)"
            r"|unrestricted|unfiltered|uncensored|no\s+(ethical|moral)\s+limits)",
            re.IGNORECASE,
        ),
    ),
    (
        "jailbreak_cue",
        "jailbreak",
        45,
        re.compile(
            r"\b(developer\s+mode|do\s+anything\s+now|dan\s+mode|jailbreak"
            r"|no\s+(restrictions|rules|limits)(\s+(or|and)\s+(restrictions|rules|limits))?"
            r"|without\s+(any\s+)?(restrictions|filters|rules|limits)"
            r"|no\s+(ethical|moral)\s+(limits|restrictions))\b",
            re.IGNORECASE,
        ),
    ),
    # --- exfiltration to an external address/URL
    (
        "exfil_to_external",
        "exfiltration",
        45,
        re.compile(
            r"\b(send|forward|email|mail|post|upload|exfiltrate|leak)\b[\s\S]{0,40}?"
            r"\b(this\s+|the\s+|our\s+|all\s+)*(data|document|files?|text|contents?|report)\b"
            r"[\s\S]{0,40}?(@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|https?://|evil|attacker|external)",
            re.IGNORECASE,
        ),
    ),
    # --- chat-template control tokens (never appear in legitimate documents)
    (
        "chat_control_token",
        "delimiter_injection",
        45,
        re.compile(
            r"(<\|(im_start|im_end|system|user|assistant|start_header_id)\|>|\[/?inst\])",
            re.IGNORECASE,
        ),
    ),
]

# Points added for a detected evasion technique (the disguised instruction itself
# is scored separately once decoded).
_OBFUSCATION_POINTS = 35

# Invisible / zero-width / bidi-control characters used to break up keywords.
_INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
_UNICODE_ESCAPE = re.compile(r"(?:\\u[0-9a-fA-F]{4}){2,}")
_BASE64_TOKEN = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")

_DEFAULT_THRESHOLD = 40
_MAX_SCORE = 100


@dataclass
class GuardVerdict:
    allowed: bool
    risk_level: str
    reasons: list[str]
    score: int
    categories: list[str] = field(default_factory=list)


class GuardService:
    def __init__(self, block_threshold: int = _DEFAULT_THRESHOLD) -> None:
        self._block_threshold = block_threshold

    def inspect(self, text: str) -> GuardVerdict:
        candidates = self._candidate_texts(text)

        matched: dict[str, str] = {}  # label -> category, insertion-ordered
        score = 0

        def add(label: str, category: str, points: int) -> None:
            nonlocal score
            if label not in matched:
                matched[label] = category
                score += points

        for label, category, points, pattern in _RULES:
            if any(pattern.search(candidate) for candidate in candidates):
                add(label, category, points)

        for label in self._obfuscation_labels(text, candidates):
            add(label, "obfuscation", _OBFUSCATION_POINTS)

        score = min(score, _MAX_SCORE)
        if score >= self._block_threshold:
            risk_level = "high"
        elif score > 0:
            risk_level = "medium"
        else:
            risk_level = "low"

        return GuardVerdict(
            allowed=risk_level != "high",
            risk_level=risk_level,
            reasons=list(matched.keys()),
            score=score,
            categories=sorted(set(matched.values())),
        )

    def _candidate_texts(self, text: str) -> list[str]:
        """Normalised text plus any decoded evasion payloads, all scanned alike."""
        candidates = [_INVISIBLE.sub("", text)]

        collapsed = self._collapse_separators(candidates[0])
        if collapsed != candidates[0]:
            candidates.append(collapsed)

        unicode_decoded = self._decode_unicode_escapes(text)
        if unicode_decoded:
            candidates.append(unicode_decoded)

        candidates.extend(self._decode_base64_payloads(text))
        return candidates

    @staticmethod
    def _collapse_separators(text: str) -> str:
        """Undo letter-spacing evasion: 'I g n o r e' / 'i.g.n.o.r.e' -> 'ignore'.

        shortcut: only single-char spacing and .-_ separators; hyphenated
        keyword runs ('Ignore-all-previous') are still missed, upgrade if abused.
        """
        collapsed = re.sub(r"(?<=\w)[.\-_](?=\w)", "", text)
        return re.sub(r"(?<=\b\w) (?=\w\b)", "", collapsed)

    def _obfuscation_labels(self, text: str, candidates: list[str]) -> list[str]:
        labels: list[str] = []
        if _INVISIBLE.search(text):
            labels.append("obfuscation_invisible_unicode")
        if _UNICODE_ESCAPE.search(text) and self._decode_unicode_escapes(text):
            labels.append("obfuscation_unicode_escape")
        if self._decode_base64_payloads(text):
            labels.append("obfuscation_base64_payload")
        return labels

    @staticmethod
    def _decode_unicode_escapes(text: str) -> str:
        if not _UNICODE_ESCAPE.search(text):
            return ""
        try:
            return bytes(text, "utf-8").decode("unicode_escape")
        except (UnicodeDecodeError, ValueError):
            return ""

    @staticmethod
    def _decode_base64_payloads(text: str) -> list[str]:
        """Decode base64 blobs that, once decoded, contain a known attack phrase."""
        payloads: list[str] = []
        for token in _BASE64_TOKEN.findall(text):
            padded = token + "=" * (-len(token) % 4)
            try:
                decoded = base64.b64decode(padded, validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError, ValueError):
                continue
            if any(pattern.search(decoded) for _, _, _, pattern in _RULES):
                payloads.append(decoded)
        return payloads


def build_guard_service(block_threshold: int = _DEFAULT_THRESHOLD) -> GuardService:
    return GuardService(block_threshold=block_threshold)


from app.core.config import settings  # noqa: E402  (avoids import cycle at module load)

guard_service = GuardService(block_threshold=settings.injection_block_threshold)
