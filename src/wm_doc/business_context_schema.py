from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from wm_doc.ir import SourceReference


class BusinessContextKind(StrEnum):
    PROCESS = "PROCESS"
    SERVICE = "SERVICE"
    SCOPE_SUMMARY = "SCOPE_SUMMARY"


class BusinessContextStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"


class BusinessEvidenceType(StrEnum):
    PROCESS = "PROCESS"
    SERVICE = "SERVICE"
    SERVICE_SIGNATURE = "SERVICE_SIGNATURE"
    DEPENDENCY = "DEPENDENCY"
    DOCUMENT = "DOCUMENT"
    DOCUMENT_FIELD = "DOCUMENT_FIELD"
    DOCUMENT_REFERENCE = "DOCUMENT_REFERENCE"
    MAPPING_OPERATION = "MAPPING_OPERATION"
    TRANSFORMER_BINDING = "TRANSFORMER_BINDING"
    SCOPE_MEMBERSHIP = "SCOPE_MEMBERSHIP"
    SCOPE_BOUNDARY = "SCOPE_BOUNDARY"
    FINDING = "FINDING"
    APPROVED_METADATA = "APPROVED_METADATA"
    DETERMINISTIC_SUMMARY = "DETERMINISTIC_SUMMARY"


class BusinessEvidenceOrigin(StrEnum):
    CANONICAL_TECHNICAL = "CANONICAL_TECHNICAL"
    APPROVED_HUMAN_METADATA = "APPROVED_HUMAN_METADATA"
    DETERMINISTIC_DERIVATION = "DETERMINISTIC_DERIVATION"
    LIMITATION = "LIMITATION"


class BusinessServiceGroup(StrEnum):
    PRIMARY = "PRIMARY"
    SUPPORTING = "SUPPORTING"
    TECHNICAL_UTILITY = "TECHNICAL_UTILITY"
    BOUNDARY = "BOUNDARY"


class BusinessContextErrorCode(StrEnum):
    INPUT_MISSING = "BUSINESS_CONTEXT_INPUT_MISSING"
    INPUT_INVALID = "BUSINESS_CONTEXT_INPUT_INVALID"
    SCHEMA_UNSUPPORTED = "BUSINESS_CONTEXT_SCHEMA_UNSUPPORTED"
    SCOPE_MISMATCH = "BUSINESS_CONTEXT_SCOPE_MISMATCH"
    REFERENCE_MISSING = "BUSINESS_CONTEXT_REFERENCE_MISSING"
    REFERENCE_AMBIGUOUS = "BUSINESS_CONTEXT_REFERENCE_AMBIGUOUS"
    OUTPUT_FAILED = "BUSINESS_CONTEXT_OUTPUT_FAILED"


class BusinessContextStatusReason(StrEnum):
    LIMIT_REACHED = "BUSINESS_CONTEXT_LIMIT_REACHED"
    DISCLOSURE_REDACTED = "BUSINESS_CONTEXT_DISCLOSURE_REDACTED"
    PARTIAL_SCOPE = "BUSINESS_CONTEXT_PARTIAL_SCOPE"
    UNKNOWN_BOUNDARY = "BUSINESS_CONTEXT_UNKNOWN_BOUNDARY"
    APPROVED_METADATA_MISSING = "BUSINESS_CONTEXT_APPROVED_METADATA_MISSING"


class BusinessContextEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    evidence_type: BusinessEvidenceType
    origin: BusinessEvidenceOrigin
    canonical_reference_id: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    source_samples: list[SourceReference] = Field(default_factory=list)


class BusinessContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "business-context.v1"
    context_id: str
    context_kind: BusinessContextKind
    status: BusinessContextStatus
    status_reasons: list[str] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)
    subject: dict[str, Any] = Field(default_factory=dict)
    approved_metadata: dict[str, Any] = Field(default_factory=dict)
    scope_summary: dict[str, Any] = Field(default_factory=dict)
    technical_summary: dict[str, Any] = Field(default_factory=dict)
    services: list[dict[str, Any]] = Field(default_factory=list)
    technical_stages: list[dict[str, Any]] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: list[dict[str, Any]] = Field(default_factory=list)
    mappings: list[dict[str, Any]] = Field(default_factory=list)
    boundaries: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[BusinessContextEvidence] = Field(default_factory=list)
    omissions: dict[str, Any] = Field(default_factory=dict)
    generation: dict[str, Any] = Field(default_factory=dict)
