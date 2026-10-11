import re
from dataclasses import dataclass

_INJECTION = re.compile(
    r"(ignore (all )?previous|disregard .*instructions|system prompt|you are now)",
    re.IGNORECASE,
)
# shortcut: heuristic injection screen, upgrade to a classifier before trusting it
@dataclass
class GuardResult:
    text: str
    blocked: bool
    reason: str = ""


class GuardService:
    def screen(self, text: str) -> GuardResult:
        match = _INJECTION.search(text)
        if match:
            return GuardResult(text="", blocked=True, reason=match.group(0))
        return GuardResult(text=text, blocked=False)


guard_service = GuardService()
