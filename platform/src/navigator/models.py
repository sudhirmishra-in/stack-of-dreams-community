"""Typed domain and API models (pydantic v2). The frontend mirrors the API shapes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ResourceType = Literal["baby_formula", "groceries", "diapers", "food_assistance"]
Urgency = Literal["today", "three_days", "this_week"]
SortBy = Literal["nearest", "availability", "capacity"]
Namespace = Literal["real", "demo"]
FacilityKind = Literal["food_bank", "soup_kitchen", "pantry", "other"]
Verification = Literal["unverified", "verified"]

RESOURCE_TYPES: tuple[str, ...] = ("baby_formula", "groceries", "diapers", "food_assistance")
INVENTORY_TYPES: tuple[str, ...] = ("baby_formula", "groceries", "diapers")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------- stored entities ----------


class SourceRef(BaseModel):
    """Where a fact came from. Timestamps are kept separate on purpose."""

    sourceId: str
    sourceRecordId: str
    sourceUrl: str | None = None
    license: str | None = None
    attribution: str | None = None
    sourceUpdatedAt: str | None = None  # when the *source* says it changed
    lastSyncedAt: str | None = None  # when we last fetched it
    lastVerifiedAt: str | None = None  # when a human/partner verified it (None = never)


class ResourceRecord(BaseModel):
    id: str
    namespace: Namespace
    name: str
    city: str | None = None
    borough: str | None = None
    zipCode: str | None = None
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    resourceTypes: list[ResourceType]
    facilityKind: FacilityKind = "other"
    hours: str | None = None
    operatingDays: list[str] = Field(default_factory=list)
    eligibility: str | None = None
    verification: Verification = "unverified"
    isDemoData: bool = False
    weeklyCapacity: int | None = None  # households/week; ONLY ever set for demo records
    sources: list[SourceRef]
    fingerprint: str
    active: bool = True


class InventoryRecord(BaseModel):
    resourceId: str
    itemType: Literal["baby_formula", "groceries", "diapers"]
    quantity: int = Field(ge=0)
    unit: str
    asOf: str | None = None
    sourceId: str
    isDemoData: bool


class ActivityRecord(BaseModel):
    """Historical service activity. NOT capacity and NOT inventory."""

    sourceId: str
    program: Literal["food_pantry", "soup_kitchen"]
    metric: Literal["individuals_served", "meals_served"]
    value: int
    periodStart: str
    periodEnd: str
    scope: Literal["citywide"] = "citywide"
    meaning: str


# ---------- API: requests ----------


class SearchRequest(Strict):
    zipCode: str
    resourceType: ResourceType
    quantity: int | None = Field(default=None, gt=0, le=100_000)
    formulaType: str | None = Field(default=None, max_length=40)
    urgency: Urgency | None = None
    sortBy: SortBy | None = None
    radiusMiles: float | None = Field(default=None, gt=0, le=100)
    includeDemo: bool = False
    limit: int = Field(default=20, ge=1, le=50)
    cursor: str | None = Field(default=None, max_length=200)

    @field_validator("zipCode")
    @classmethod
    def _zip(cls, v: str) -> str:
        if not (len(v) == 5 and v.isdigit()):
            raise ValueError("zipCode must be exactly 5 digits")
        return v


class HistoryMessage(Strict):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class AssistantRequest(Strict):
    message: str = Field(min_length=1)
    sessionId: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]+$")
    agentId: str = Field(default="community-navigator", max_length=64)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)
    idempotencyKey: str | None = Field(default=None, min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    context: dict[str, str] | None = None  # small, optional, e.g. {"zipCode": "10027"}


# ---------- API: responses ----------


class ResourceView(BaseModel):
    """Frontend-compatible resource, with provenance."""

    id: str
    name: str
    city: str
    borough: str | None = None
    zipCode: str | None = None  # some real records have coordinates but no ZIP
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    resourceTypes: list[ResourceType]
    availableQuantity: int | None = None
    inventory: dict[str, int] | None = None
    inventoryIsDemo: bool = False
    inventoryAsOf: str | None = None
    weeklyCapacity: int | None = None
    operatingDays: list[str] | None = None
    hours: str | None = None
    eligibility: str | None = None
    lastUpdated: str | None = None
    source: str
    sourceId: str
    sourceUrl: str | None = None
    attribution: str | None = None
    sourceUpdatedAt: str | None = None
    lastSyncedAt: str | None = None
    lastVerifiedAt: str | None = None
    freshness: Literal["fresh", "stale", "unknown"] = "unknown"
    verified: bool = False
    isDemoData: bool = False
    distanceMiles: float | None = None


class Origin(BaseModel):
    zipCode: str
    latitude: float | None = None
    longitude: float | None = None
    geocoded: bool = False


class SearchResponse(BaseModel):
    resources: list[ResourceView]
    totalResults: int
    dataSource: str
    isDemoData: bool
    origin: Origin
    nextCursor: str | None = None
    attributions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    correlationId: str


class UsageLimitView(BaseModel):
    limit: int
    used: int
    remaining: int
    resetsAt: str


class UsageResponse(BaseModel):
    daily: UsageLimitView
    monthly: UsageLimitView
    tokensToday: UsageLimitView
    maxQueryChars: int
    concurrentLimit: int
    applicationDaily: UsageLimitView | None = None
    disabled: bool = False
    # "pending" = signed in with an external provider (Google) but not yet approved by an administrator.
    accountStatus: Literal["approved", "pending", "disabled"] = "approved"
    correlationId: str


class AgentUsage(BaseModel):
    inputTokens: int = 0
    outputTokens: int = 0
    modelInvocations: int = 0
    specialistCalls: int = 0
    estimatedUsd: float | None = None


class Citation(BaseModel):
    sourceId: str
    resourceId: str | None = None
    isDemoData: bool = False
    verification: Verification = "unverified"
    freshness: Literal["fresh", "stale", "unknown"] = "unknown"


class AssistantResponse(BaseModel):
    response: str
    sessionId: str
    agentId: str
    citations: list[Citation] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    usage: AgentUsage = Field(default_factory=AgentUsage)
    remaining: UsageResponse | None = None
    correlationId: str
