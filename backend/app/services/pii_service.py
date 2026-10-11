"""PII detection and reversible tokenization.

Pipeline: Presidio Analyzer detects entities (spaCy ``en_core_web_lg`` plus a
custom German-IBAN regex). A custom Presidio anonymizer operator replaces each
entity with an opaque ``[PII_<TYPE>_<hex>]`` placeholder and records the
original value in a vault that is encrypted with Fernet before it leaves this
class. Raw PII never reaches the LLM and is never returned by the API.
"""

import secrets
from dataclasses import dataclass
from functools import lru_cache

from presidio_analyzer import (
    AnalyzerEngine,
    Pattern,
    PatternRecognizer,
    RecognizerResult,
)
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from presidio_anonymizer.operators import Operator, OperatorType

from app.core.security import decrypt_string, encrypt_string

SUPPORTED_ENTITIES = [
    "PERSON",
    "LOCATION",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "IBAN_CODE",
    "CREDIT_CARD",
    "DATE_TIME",
]

# German IBAN: DE + 2 check digits + 18 digits, optionally space-grouped,
# e.g. "DE89 3704 0044 0532 0130 00".
GERMAN_IBAN_PATTERN = r"\bDE\d{2}(?:[ ]?\d{4}){4}[ ]?\d{2}\b"


@dataclass
class PIIEntity:
    """Metadata about a single detected entity (no raw value)."""

    entity_type: str
    start: int
    end: int
    placeholder: str


@dataclass
class RedactionResult:
    sanitized_text: str
    encrypted_mappings: dict[str, str]
    entity_count: int
    entities: list[PIIEntity]


class _VaultOperator(Operator):
    """Replaces an entity with a placeholder and stores the value in a vault."""

    def operate(self, text: str, params: dict | None = None) -> str:
        params = params or {}
        vault: dict[str, str] = params["vault"]
        entity_type: str = params.get("entity_type", "PII")
        placeholder = f"[PII_{entity_type.upper()}_{secrets.token_hex(5)}]"
        vault[placeholder] = text
        return placeholder

    def validate(self, params: dict | None = None) -> None:
        if not params or "vault" not in params:
            raise ValueError("vault parameter is required")

    def operator_name(self) -> str:
        return "vault"

    def operator_type(self) -> OperatorType:
        return OperatorType.Anonymize


class PIIService:
    def __init__(self) -> None:
        self._analyzer = self._build_analyzer()
        self._anonymizer = AnonymizerEngine()
        self._anonymizer.add_anonymizer(_VaultOperator)

    @staticmethod
    def _build_analyzer() -> AnalyzerEngine:
        analyzer = AnalyzerEngine()
        analyzer.registry.add_recognizer(
            PatternRecognizer(
                supported_entity="IBAN_CODE",
                name="GermanIbanRecognizer",
                patterns=[Pattern("german_iban", GERMAN_IBAN_PATTERN, 0.6)],
            )
        )
        return analyzer

    def analyze(self, text: str) -> list[RecognizerResult]:
        return self._analyzer.analyze(
            text=text, language="en", entities=SUPPORTED_ENTITIES
        )

    def redact(self, text: str) -> RedactionResult:
        results = self.analyze(text)
        if not results:
            return RedactionResult(text, {}, 0, [])

        vault: dict[str, str] = {}
        operators = {
            result.entity_type: OperatorConfig("vault", {"vault": vault})
            for result in results
        }
        anonymized = self._anonymizer.anonymize(
            text=text, analyzer_results=results, operators=operators
        )

        entities = [
            PIIEntity(
                entity_type=item.entity_type,
                start=item.start,
                end=item.end,
                placeholder=item.text,
            )
            for item in anonymized.items
        ]
        encrypted = {token: encrypt_string(value) for token, value in vault.items()}
        return RedactionResult(
            sanitized_text=anonymized.text,
            encrypted_mappings=encrypted,
            entity_count=len(entities),
            entities=entities,
        )

    def rehydrate(self, text: str, encrypted_mappings: dict[str, str]) -> str:
        for placeholder, token in encrypted_mappings.items():
            text = text.replace(placeholder, decrypt_string(token))
        return text


@lru_cache
def get_pii_service() -> PIIService:
    """Lazily build the (heavy) Presidio engine once per process."""
    return PIIService()
