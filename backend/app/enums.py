"""Domain enums shared across models, schemas and the policy engine."""
from enum import StrEnum


class UserRole(StrEnum):
    """Authentication roles - who a person is, NOT what a purchase may cost.

    Roles gate which screens and endpoints a human can reach. They are
    deliberately absent from the policy engine's inputs: no role, including
    ADMIN, can raise a spending limit or unblock a transaction.
    """

    BUYER = "buyer"
    MERCHANT = "merchant"
    ADMIN = "admin"


class AutonomyLevel(StrEnum):
    """US-6b - how much authority the buyer has delegated to their agent."""

    RECOMMEND = "L1_RECOMMEND"          # suggest only; no PurchaseIntent created
    PREPARE = "L2_PREPARE"              # create intent, always require human approval
    BOUNDED_AUTO = "L3_BOUNDED_AUTO"    # auto-purchase below threshold, within policy


class IntentStatus(StrEnum):
    CREATED = "CREATED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    AUTO_AUTHORIZED = "AUTO_AUTHORIZED"
    ORDER_CREATED = "ORDER_CREATED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOMMENDATION_ONLY = "RECOMMENDATION_ONLY"


class TransactionStatus(StrEnum):
    CREATED = "CREATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    FAILED = "FAILED"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class OpportunityStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AgentId(StrEnum):
    """Actors that can emit audit events (US-9)."""

    BUYER_AGENT = "buyer_agent"
    MERCHANT_AGENT = "merchant_agent"
    POLICY_ENGINE = "policy_engine"
    PERMISSION_SYSTEM = "permission_system"
    TRUST_ENGINE = "trust_engine"
    HUMAN = "human"
    RAZORPAY = "razorpay"
    SYSTEM = "system"


class AuditAction(StrEnum):
    """Minimum event set from US-9, plus the failure-path events."""

    USER_INTENT_RECEIVED = "USER_INTENT_RECEIVED"
    INTENT_CLARIFICATION_REQUESTED = "INTENT_CLARIFICATION_REQUESTED"
    CATALOG_SEARCH = "CATALOG_SEARCH"
    PRODUCT_SELECTED = "PRODUCT_SELECTED"
    OFFER_GENERATED = "OFFER_GENERATED"
    NO_BUNDLE_OFFERED = "NO_BUNDLE_OFFERED"
    TRUST_EVALUATED = "TRUST_EVALUATED"
    PERMISSION_CHECK = "PERMISSION_CHECK"
    POLICY_CHECK = "POLICY_CHECK"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    AUTO_AUTHORIZED = "AUTO_AUTHORIZED"
    RAZORPAY_ORDER_CREATED = "RAZORPAY_ORDER_CREATED"
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    WEBHOOK_PROCESSED = "WEBHOOK_PROCESSED"
    ORDER_COMPLETED = "ORDER_COMPLETED"
    # authentication
    LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    SESSION_REJECTED = "SESSION_REJECTED"
    POLICY_UPDATED = "POLICY_UPDATED"
    # failure paths
    POLICY_BLOCKED = "POLICY_BLOCKED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    PAYMENT_TIMEOUT = "PAYMENT_TIMEOUT"
    PAYMENT_STATE_RESOLVED = "PAYMENT_STATE_RESOLVED"
    INVALID_REQUEST = "INVALID_REQUEST"
    DUPLICATE_WEBHOOK = "DUPLICATE_WEBHOOK"
    WEBHOOK_SIGNATURE_INVALID = "WEBHOOK_SIGNATURE_INVALID"


class AuditStatus(StrEnum):
    OK = "OK"
    BLOCKED = "BLOCKED"
    DENIED = "DENIED"
    FAILED = "FAILED"
    PENDING = "PENDING"
    IGNORED = "IGNORED"
