from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from wm_doc.business_context_schema import BusinessContextKind, BusinessContextStatus

BUSINESS_DRAFT_SCHEMA_VERSION = "business-draft.v1"


class BusinessResultLanguage(StrEnum):
    PL = "pl"
    EN = "en"


class BusinessClaimSection(StrEnum):
    GENERAL = "general"
    PURPOSE = "purpose"
    ACTORS = "actors"
    TRIGGERS = "triggers"
    OUTCOMES = "outcomes"
    STAGES = "stages"
    OBJECTS = "objects"
    SYSTEMS = "systems"
    EXCEPTIONS = "exceptions"


class BusinessClaimConfidence(StrEnum):
    CONFIRMED = "CONFIRMED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class BusinessClaimBasis(StrEnum):
    APPROVED_METADATA = "APPROVED_METADATA"
    CANONICAL_TECHNICAL = "CANONICAL_TECHNICAL"
    MODEL_INFERENCE = "MODEL_INFERENCE"


class BusinessConflictSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"


class BusinessEnrichmentErrorCode(StrEnum):
    INPUT_MISSING = "BUSINESS_ENRICHMENT_INPUT_MISSING"
    INPUT_INVALID = "BUSINESS_ENRICHMENT_INPUT_INVALID"
    SCHEMA_UNSUPPORTED = "BUSINESS_ENRICHMENT_SCHEMA_UNSUPPORTED"
    PROVIDER_UNAVAILABLE = "BUSINESS_ENRICHMENT_PROVIDER_UNAVAILABLE"
    MODEL_NOT_FOUND = "BUSINESS_ENRICHMENT_MODEL_NOT_FOUND"
    PROVIDER_FAILED = "BUSINESS_ENRICHMENT_PROVIDER_FAILED"
    RESPONSE_INVALID = "BUSINESS_ENRICHMENT_RESPONSE_INVALID"
    DRAFT_INVALID = "BUSINESS_ENRICHMENT_DRAFT_INVALID"
    EVIDENCE_INVALID = "BUSINESS_ENRICHMENT_EVIDENCE_INVALID"
    DISCLOSURE_FAILED = "BUSINESS_ENRICHMENT_DISCLOSURE_FAILED"
    RESULT_INVALID = "BUSINESS_ENRICHMENT_RESULT_INVALID"
    TIMEOUT = "BUSINESS_ENRICHMENT_TIMEOUT"
    CONTEXT_BUDGET_EXCEEDED = "BUSINESS_ENRICHMENT_CONTEXT_BUDGET_EXCEEDED"
    OUTPUT_FAILED = "BUSINESS_ENRICHMENT_OUTPUT_FAILED"


class BusinessEnrichmentWarningCode(StrEnum):
    CONTEXT_PARTIAL = "BUSINESS_ENRICHMENT_CONTEXT_PARTIAL"
    CACHE_INVALID = "BUSINESS_ENRICHMENT_CACHE_INVALID"
    CACHE_WRITE_FAILED = "BUSINESS_ENRICHMENT_CACHE_WRITE_FAILED"
    MODEL_DIGEST_UNAVAILABLE = "BUSINESS_ENRICHMENT_MODEL_DIGEST_UNAVAILABLE"


class BusinessResultClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = ""
    section: BusinessClaimSection
    text: str
    confidence: BusinessClaimConfidence
    evidence_ids: list[str] = Field(default_factory=list)
    basis: BusinessClaimBasis
    related_service_ids: list[str] = Field(default_factory=list)
    related_document_ids: list[str] = Field(default_factory=list)
    inference_note: str | None = None


class BusinessDraftItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    section: str = "general"
    evidence_ids: list[str] = Field(default_factory=list)


class BusinessDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[BusinessDraftItem]
    inferences: list[BusinessDraftItem] = Field(default_factory=list)
    unknowns: list[BusinessDraftItem] = Field(default_factory=list)
    limitations: list[BusinessDraftItem] = Field(default_factory=list)


class BusinessResultUnknown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unknown_id: str = ""
    code: str
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)


class BusinessResultLimitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limitation_id: str = ""
    code: str
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)


class BusinessResultConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_id: str = ""
    severity: BusinessConflictSeverity
    description: str
    evidence_ids: list[str] = Field(default_factory=list)


class BusinessResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "business-result.v1"
    result_id: str = ""
    context_id: str
    source_context_sha256: str = ""
    context_kind: BusinessContextKind
    status: BusinessContextStatus
    language: BusinessResultLanguage
    subject: dict[str, Any] = Field(default_factory=dict)
    sections: dict[str, Any] = Field(default_factory=dict)
    claims: list[BusinessResultClaim] = Field(default_factory=list)
    unknowns: list[BusinessResultUnknown] = Field(default_factory=list)
    limitations: list[BusinessResultLimitation] = Field(default_factory=list)
    conflicts: list[BusinessResultConflict] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    omissions: dict[str, Any] = Field(default_factory=dict)


def business_draft_json_schema() -> dict[str, Any]:
    schema = BusinessDraft.model_json_schema()
    schema["title"] = "BusinessDraft"
    schema["additionalProperties"] = False
    return schema
