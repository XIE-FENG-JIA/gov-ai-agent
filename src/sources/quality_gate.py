"""Live-ingest quality gate contract and reference helper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from src.core.models import PublicGovDoc
from src.sources.quality_config import get_quality_policy


class QualityGateError(RuntimeError):
    """Base error for live-ingest quality gate failures."""


class LiveIngestBelowFloor(QualityGateError):
    """Raised when an adapter returns fewer records than the configured floor."""

    def __init__(self, adapter_name: str, *, actual: int, expected_min_records: int) -> None:
        self.adapter_name = adapter_name
        self.actual = actual
        self.expected_min_records = expected_min_records
        super().__init__(
            f"{adapter_name} returned {actual} records; expected at least {expected_min_records}"
        )


class SchemaIntegrityError(QualityGateError):
    """Raised when a record cannot satisfy the required provenance fields."""

    def __init__(self, record_id: str, missing_fields: list[str], *, adapter_name: str) -> None:
        self.record_id = record_id
        self.missing_fields = missing_fields
        self.adapter_name = adapter_name
        missing = ", ".join(missing_fields)
        super().__init__(f"{adapter_name} record {record_id} missing required fields: {missing}")


class StaleRecord(QualityGateError):
    """Raised when a record is fixture-backed or older than the freshness window."""

    def __init__(self, record_id: str, reason: str, *, adapter_name: str) -> None:
        self.record_id = record_id
        self.reason = reason
        self.adapter_name = adapter_name
        super().__init__(f"{adapter_name} record {record_id} rejected as stale: {reason}")


class SyntheticContamination(QualityGateError):
    """Raised when a synthetic record appears in a live-ingest batch."""

    def __init__(self, record_id: str, *, adapter_name: str) -> None:
        self.record_id = record_id
        self.adapter_name = adapter_name
        super().__init__(f"{adapter_name} record {record_id} is flagged synthetic")


@dataclass(slots=True)
class GateReport:
    """Summary for a successful quality-gate evaluation."""

    adapter: str
    records_in: int
    records_out: int
    rejected_by: dict[str, int]
    pass_rate: float
    duration_seconds: float
    timestamp: datetime


class QualityGate:
    """Validate live-ingest outputs before they enter the staging corpus."""

    def __init__(
        self,
        *,
        expected_min_records: int = 1,
        freshness_window_days: int = 365,
        allow_fallback: bool = True,
    ) -> None:
        self.expected_min_records = expected_min_records
        self.freshness_window_days = freshness_window_days
        self.allow_fallback = allow_fallback

    @classmethod
    def from_adapter_name(cls, adapter_name: str) -> QualityGate:
        """Build a gate from configured per-adapter policy."""

        policy = get_quality_policy(adapter_name)
        return cls(
            expected_min_records=policy.expected_min_records,
            freshness_window_days=policy.freshness_window_days,
            allow_fallback=policy.allow_fallback,
        )

    def evaluate(self, records: list[PublicGovDoc | dict[str, Any]], adapter_name: str) -> GateReport:
        """Validate one adapter batch and return a success report."""

        started_at = perf_counter()
        records_in = len(records)
        if records_in < self.expected_min_records:
            raise LiveIngestBelowFloor(
                adapter_name,
                actual=records_in,
                expected_min_records=self.expected_min_records,
            )

        validated_docs = [self._validate_record(record, adapter_name=adapter_name) for record in records]
        duration_seconds = perf_counter() - started_at

        return GateReport(
            adapter=adapter_name,
            records_in=records_in,
            records_out=len(validated_docs),
            rejected_by={},
            pass_rate=1.0 if records_in else 0.0,
            duration_seconds=duration_seconds,
            timestamp=datetime.now(UTC),
        )

    def _validate_record(
        self,
        record: PublicGovDoc | dict[str, Any],
        *,
        adapter_name: str,
    ) -> PublicGovDoc:
        doc = self._coerce_public_doc(record, adapter_name=adapter_name)
        self._ensure_schema_integrity(doc, adapter_name=adapter_name)
        self._ensure_provenance(doc, adapter_name=adapter_name)
        return doc

    @staticmethod
    def _coerce_public_doc(
        record: PublicGovDoc | dict[str, Any],
        *,
        adapter_name: str,
    ) -> PublicGovDoc:
        if isinstance(record, PublicGovDoc):
            return record

        try:
            return PublicGovDoc.model_validate(record)
        except ValidationError as exc:
            record_id = str(record.get("source_id") or record.get("id") or "<unknown>").strip() or "<unknown>"
            raise SchemaIntegrityError(
                record_id,
                ["PublicGovDoc validation failed"],
                adapter_name=adapter_name,
            ) from exc

    @staticmethod
    def _ensure_schema_integrity(doc: PublicGovDoc, *, adapter_name: str) -> None:
        missing_fields: list[str] = []
        if not doc.source_url.strip():
            missing_fields.append("source_url")
        if not doc.source_agency.strip():
            missing_fields.append("source_agency")
        if not doc.source_doc_no or not str(doc.source_doc_no).strip():
            missing_fields.append("source_doc_no")
        if doc.source_date is None:
            missing_fields.append("source_date")

        if missing_fields:
            raise SchemaIntegrityError(doc.source_id, missing_fields, adapter_name=adapter_name)

    def _ensure_provenance(self, doc: PublicGovDoc, *, adapter_name: str) -> None:
        if doc.synthetic:
            raise SyntheticContamination(doc.source_id, adapter_name=adapter_name)

        if doc.fixture_fallback and not self.allow_fallback:
            raise StaleRecord(doc.source_id, "fixture fallback is not allowed", adapter_name=adapter_name)

        freshness_cutoff = date.today().toordinal() - self.freshness_window_days
        if doc.crawl_date.toordinal() < freshness_cutoff:
            raise StaleRecord(
                doc.source_id,
                f"crawl_date {doc.crawl_date.isoformat()} is older than {self.freshness_window_days} days",
                adapter_name=adapter_name,
            )
