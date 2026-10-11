import re

_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone": re.compile(r"\+?\d[\d\s().-]{7,}\d"),
}
# shortcut: regex PII only, swap for a NER-backed detector when recall matters
class PiiService:
    def tokenize(self, text: str) -> tuple[str, dict[str, str]]:
        vault: dict[str, str] = {}
        for kind, pattern in _PATTERNS.items():
            for match in pattern.findall(text):
                token = f"<{kind.upper()}_{len(vault)}>"
                vault[token] = match
                text = text.replace(match, token)
        return text, vault

    def detokenize(self, text: str, vault: dict[str, str]) -> str:
        for token, value in vault.items():
            text = text.replace(token, value)
        return text


pii_service = PiiService()
