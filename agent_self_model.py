#!/usr/bin/env python3
"""Agent Self-Model validator.

The Agent Self-Model is the novel part of this project: a bounded, inspectable,
honest self-description an agent publishes *on top of* its A2A Agent Card. Where
the A2A card is a business card, the Self-Model is the due-diligence dossier.

This module validates a Self-Model document, pillar by pillar. Implemented:

  Identity & Ownership    — "who is this agent, and who is accountable for it?"
  Capabilities            — "what can it do, how well, under what limits?"
  Permissions & Authority — "what is it ALLOWED to do?" (authZ, not A2A's authN)
  Constraints & Policy    — "what limits/policy does it operate under?"
  Dependencies            — "what does it rely on? what's the blast radius?"
  Escalation Boundaries   — "when, and to whom, does it hand off?"
  Operational State       — "is it healthy enough to use right now?" (declared)
  Confidence & Evidence   — "should I believe its output?"
  Assurance & Attestation — "is it vetted enough to touch regulated data?"
  Provenance & Lifecycle  — "is it stale/abandoned/EOL — should I migrate off?"

Plus a verification envelope (`attestation`) wrapping the document: who asserted
these claims, when, until when, and (later) a verifiable signature.

Design principle: pillars that touch A2A AUGMENT, not DUPLICATE. Fields are tagged
in comments as [self-asserted] or [verifiable]. Cross-checks against the actual
A2A card live in audit.py; cross-*pillar* consistency checks live here.
"""

from __future__ import annotations

import datetime
from typing import Any

from findings import Finding

# The version of the Self-Model schema this validator implements.
SELF_MODEL_VERSION = "0.1"

# The A2A extension URI that identifies the Agent Self-Model — a stable, globally
# unique identifier (this project's GitHub Pages URL). See SPEC.md.
EXTENSION_URI = "https://supercool83.github.io/Agent-Auditor/ext/v0.1"

# Standalone delivery: a Self-Model can be published at this well-known path
# (Delivery B, for non-A2A agents). Delivery A — carrying it inside the A2A
# card's `capabilities.extensions` — is a later slice.
WELL_KNOWN_SELF_MODEL_PATH = "/.well-known/agent-self-model.json"

# Controlled vocabularies used across the pillars.
MATURITY_LEVELS = {"experimental", "beta", "stable", "deprecated"}
PROFICIENCY_LEVELS = {"low", "medium", "high"}
AUTHORITY_LEVELS = {"read-only", "act-with-approval", "autonomous"}
SENSITIVITY_LEVELS = {"public", "internal", "confidential", "restricted"}
DEPENDENCY_TYPES = {"model", "agent", "tool", "service"}
ESCALATION_TARGET_TYPES = {"human", "agent", "queue"}
FALLBACK_BEHAVIORS = {"halt", "defer", "handoff"}
STATE_STATUSES = {"operational", "degraded", "maintenance", "offline"}
DEGRADATION_POLICIES = {"graceful", "fail-closed", "fail-open"}
CALIBRATION_LEVELS = {"calibrated", "uncalibrated", "unknown"}
SECURITY_TIERS = {"none", "standard", "high", "critical"}
LIFECYCLE_STAGES = {"active", "maintenance", "deprecated", "retired"}


def validate_self_model(model: Any) -> list[Finding]:
    """Validate a whole Self-Model document. Empty list means it passed.

    `identity` is REQUIRED. The other pillars are optional for now (each validated
    when present). Cross-pillar consistency checks run at the end.
    """
    if not isinstance(model, dict):
        return [Finding("error", "(root)", "Self-model must be a JSON object.")]

    findings: list[Finding] = []
    if "identity" not in model:
        findings.append(Finding("error", "identity", "Missing required pillar 'identity'."))
    else:
        findings.extend(validate_identity_ownership(model["identity"]))

    for pillar_name, validator in _OPTIONAL_PILLARS.items():
        if pillar_name in model:
            findings.extend(validator(model[pillar_name]))

    if "attestation" in model:
        findings.extend(validate_attestation(model["attestation"], "attestation"))
    else:
        findings.append(
            Finding("warning", "attestation", "Self-Model is unattested (no verification envelope).")
        )

    findings.extend(_cross_pillar_consistency(model))
    return findings


# --------------------------------------------------------------------------- #
# Pillar 1 — Identity & Ownership
# --------------------------------------------------------------------------- #

def validate_identity_ownership(pillar: Any) -> list[Finding]:
    """Validate the Identity & Ownership pillar."""
    where = "identity"
    if not isinstance(pillar, dict):
        return [Finding("error", where, "'identity' pillar must be an object.")]

    findings: list[Finding] = []

    # agentId [verifiable] — a stable, unique identifier. A2A has no equivalent.
    _require_nonempty_string(pillar, "agentId", where, findings)

    # displayName [self-asserted] — optional; SHOULD equal the A2A card's `name`.
    _optional_string(pillar, "displayName", where, findings)

    # owner [verifiable] — the accountability chain A2A leaves out.
    owner = pillar.get("owner")
    if "owner" not in pillar:
        findings.append(
            Finding("error", f"{where}.owner", "Missing required 'owner' (the accountable party).")
        )
    elif not isinstance(owner, dict):
        findings.append(Finding("error", f"{where}.owner", "'owner' must be an object."))
    else:
        _validate_owner(owner, f"{where}.owner", findings)

    return findings


def _validate_owner(owner: dict[str, Any], where: str, findings: list[Finding]) -> None:
    for field in ("name", "organization", "contact"):
        _require_nonempty_string(owner, field, where, findings)

    _optional_string(owner, "role", where, findings)

    # Light sanity heuristic: the contact should look reachable.
    contact = owner.get("contact")
    if isinstance(contact, str) and contact.strip():
        looks_reachable = "@" in contact or contact.startswith(("http://", "https://"))
        if not looks_reachable:
            findings.append(
                Finding("warning", f"{where}.contact", "'contact' doesn't look like an email or URL.")
            )


# --------------------------------------------------------------------------- #
# Pillar 2 — Capabilities
# --------------------------------------------------------------------------- #

def validate_capabilities(pillar: Any) -> list[Finding]:
    """Validate the Capabilities pillar.

    NOT A2A's `AgentCapabilities` (streaming/push flags). This is the self-model's
    *qualitative envelope* around the agent's skills — each entry references a card
    `skills[].id` and adds what A2A can't say. The cross-check that a referenced
    skill actually exists lives in audit.py.
    """
    where = "capabilities"
    if not isinstance(pillar, dict):
        return [Finding("error", where, "'capabilities' pillar must be an object.")]

    findings: list[Finding] = []

    declared = pillar.get("declared")
    if "declared" not in pillar:
        findings.append(
            Finding("error", f"{where}.declared", "Missing required 'declared' (a list of capabilities).")
        )
        return findings
    if not isinstance(declared, list):
        findings.append(Finding("error", f"{where}.declared", "'declared' must be a list."))
        return findings
    if not declared:
        findings.append(Finding("warning", f"{where}.declared", "Declares no capabilities."))

    for index, capability in enumerate(declared):
        _validate_capability(capability, f"{where}.declared[{index}]", findings)
    return findings


def _validate_capability(capability: Any, where: str, findings: list[Finding]) -> None:
    if not isinstance(capability, dict):
        findings.append(Finding("error", where, "Capability must be an object."))
        return

    _require_nonempty_string(capability, "skillId", where, findings)  # [verifiable]
    _require_enum(capability, "maturity", MATURITY_LEVELS, where, findings)  # [self-asserted]
    _optional_enum(capability, "proficiency", PROFICIENCY_LEVELS, where, findings)
    _optional_bool(capability, "tested", where, findings)
    _optional_string_list(capability, "knownLimits", where, findings)
    _optional_string_list(capability, "failureModes", where, findings)


# --------------------------------------------------------------------------- #
# Pillar 3 — Permissions & Authority
# --------------------------------------------------------------------------- #

def validate_permissions(pillar: Any) -> list[Finding]:
    """Permissions & Authority — the agent's *authorization* scope.

    A2A only describes authentication (`securitySchemes`: who you are). This pillar
    describes what the agent is allowed to do and its spend/commit authority. The
    cross-check against the card's security lives in audit.py.
    """
    where = "permissions"
    if not isinstance(pillar, dict):
        return [Finding("error", where, "'permissions' pillar must be an object.")]

    findings: list[Finding] = []
    _require_enum(pillar, "authorityLevel", AUTHORITY_LEVELS, where, findings)
    _optional_string_list(pillar, "allowedActions", where, findings)
    _optional_string_list(pillar, "prohibitedActions", where, findings)
    _optional_bool(pillar, "requiresAuthentication", where, findings)

    if "spendingLimit" in pillar:
        limit = pillar["spendingLimit"]
        loc = f"{where}.spendingLimit"
        if not isinstance(limit, dict):
            findings.append(Finding("error", loc, "'spendingLimit' must be an object."))
        else:
            _require_nonempty_string(limit, "currency", loc, findings)
            if "maxPerAction" not in limit:
                findings.append(Finding("error", f"{loc}.maxPerAction", "Missing required 'maxPerAction'."))
            else:
                _optional_number(limit, "maxPerAction", loc, findings, minimum=0)
    return findings


# --------------------------------------------------------------------------- #
# Pillar 4 — Constraints & Policy
# --------------------------------------------------------------------------- #

def validate_constraints(pillar: Any) -> list[Finding]:
    """Constraints & Policy — the operational limits and policy the agent runs under."""
    where = "constraints"
    if not isinstance(pillar, dict):
        return [Finding("error", where, "'constraints' pillar must be an object.")]

    findings: list[Finding] = []
    _require_enum(pillar, "dataSensitivity", SENSITIVITY_LEVELS, where, findings)
    _optional_string(pillar, "dataResidency", where, findings)
    _optional_number(pillar, "rateLimitPerMinute", where, findings, minimum=0)
    _optional_string_list(pillar, "policyRefs", where, findings)
    _optional_string_list(pillar, "jurisdictions", where, findings)
    return findings


# --------------------------------------------------------------------------- #
# Pillar 5 — Dependencies
# --------------------------------------------------------------------------- #

def validate_dependencies(pillar: Any) -> list[Finding]:
    """Dependencies — the upstream models/agents/tools/services the agent relies on."""
    where = "dependencies"
    if not isinstance(pillar, dict):
        return [Finding("error", where, "'dependencies' pillar must be an object.")]

    findings: list[Finding] = []
    declared = pillar.get("declared")
    if "declared" not in pillar:
        findings.append(
            Finding("error", f"{where}.declared", "Missing required 'declared' (a list of dependencies).")
        )
        return findings
    if not isinstance(declared, list):
        findings.append(Finding("error", f"{where}.declared", "'declared' must be a list."))
        return findings

    for index, dependency in enumerate(declared):
        _validate_dependency(dependency, f"{where}.declared[{index}]", findings)
    return findings


def _validate_dependency(dependency: Any, where: str, findings: list[Finding]) -> None:
    if not isinstance(dependency, dict):
        findings.append(Finding("error", where, "Dependency must be an object."))
        return
    _require_enum(dependency, "type", DEPENDENCY_TYPES, where, findings)
    _require_nonempty_string(dependency, "name", where, findings)
    _optional_string(dependency, "provider", where, findings)
    _optional_bool(dependency, "critical", where, findings)


# --------------------------------------------------------------------------- #
# Pillar 6 — Escalation Boundaries
# --------------------------------------------------------------------------- #

def validate_escalation(pillar: Any) -> list[Finding]:
    """Escalation Boundaries — when, and to whom, the agent hands off."""
    where = "escalation"
    if not isinstance(pillar, dict):
        return [Finding("error", where, "'escalation' pillar must be an object.")]

    findings: list[Finding] = []

    triggers = pillar.get("triggers")
    if "triggers" not in pillar:
        findings.append(Finding("error", f"{where}.triggers", "Missing required 'triggers'."))
    elif not isinstance(triggers, list) or not all(isinstance(t, str) for t in triggers):
        findings.append(Finding("error", f"{where}.triggers", "'triggers' must be a list of strings."))
    elif not triggers:
        findings.append(Finding("error", f"{where}.triggers", "'triggers' must not be empty."))

    target = pillar.get("target")
    if "target" not in pillar:
        findings.append(Finding("error", f"{where}.target", "Missing required 'target'."))
    elif not isinstance(target, dict):
        findings.append(Finding("error", f"{where}.target", "'target' must be an object."))
    else:
        _require_enum(target, "type", ESCALATION_TARGET_TYPES, f"{where}.target", findings)
        _require_nonempty_string(target, "contact", f"{where}.target", findings)

    _optional_enum(pillar, "fallbackBehavior", FALLBACK_BEHAVIORS, where, findings)
    return findings


# --------------------------------------------------------------------------- #
# Pillar 7 — Operational State (declared envelope)
# --------------------------------------------------------------------------- #

def validate_state(pillar: Any) -> list[Finding]:
    """Operational State — the agent's declared health envelope.

    This is the DECLARED state ("I run 24/7 and degrade gracefully"). The OBSERVED
    state (is it actually healthy right now?) is measured by the auditor at runtime
    — a later slice. Keeping the two distinct avoids conflating self-report with
    measurement.
    """
    where = "state"
    if not isinstance(pillar, dict):
        return [Finding("error", where, "'state' pillar must be an object.")]

    findings: list[Finding] = []
    _require_enum(pillar, "status", STATE_STATUSES, where, findings)
    _optional_enum(pillar, "degradationPolicy", DEGRADATION_POLICIES, where, findings)
    _optional_string(pillar, "lastStatusChange", where, findings)

    if "availability" in pillar:
        availability = pillar["availability"]
        loc = f"{where}.availability"
        if not isinstance(availability, dict):
            findings.append(Finding("error", loc, "'availability' must be an object."))
        else:
            _optional_string(availability, "schedule", loc, findings)
            _optional_string(availability, "timezone", loc, findings)
    return findings


# --------------------------------------------------------------------------- #
# Pillar 8 — Confidence & Evidence
# --------------------------------------------------------------------------- #

def validate_confidence(pillar: Any) -> list[Finding]:
    """Confidence & Evidence — how much its output should be believed."""
    where = "confidence"
    if not isinstance(pillar, dict):
        return [Finding("error", where, "'confidence' pillar must be an object.")]

    findings: list[Finding] = []
    _require_enum(pillar, "calibration", CALIBRATION_LEVELS, where, findings)
    _optional_bool(pillar, "reportsConfidence", where, findings)
    _optional_bool(pillar, "evidenceProvided", where, findings)
    _optional_string_list(pillar, "knownBiases", where, findings)
    _optional_string_list(pillar, "evaluationRefs", where, findings)
    return findings


# --------------------------------------------------------------------------- #
# Pillar 9 — Assurance & Attestation
# --------------------------------------------------------------------------- #

def validate_assurance(pillar: Any) -> list[Finding]:
    """Assurance & Attestation — how vetted the agent is (security tier, certs)."""
    where = "assurance"
    if not isinstance(pillar, dict):
        return [Finding("error", where, "'assurance' pillar must be an object.")]

    findings: list[Finding] = []
    _require_enum(pillar, "securityTier", SECURITY_TIERS, where, findings)
    _optional_string_list(pillar, "certifications", where, findings)
    _optional_string_list(pillar, "dataClasses", where, findings)
    _optional_string(pillar, "lastPenTest", where, findings)
    _optional_bool(pillar, "sandboxed", where, findings)
    return findings


# --------------------------------------------------------------------------- #
# Pillar 10 — Provenance & Lifecycle
# --------------------------------------------------------------------------- #

def validate_provenance(pillar: Any) -> list[Finding]:
    """Provenance & Lifecycle — is it current, or stale/deprecated/EOL?"""
    where = "provenance"
    if not isinstance(pillar, dict):
        return [Finding("error", where, "'provenance' pillar must be an object.")]

    findings: list[Finding] = []
    # lastUpdated is required — staleness detection depends on it.
    _require_nonempty_string(pillar, "lastUpdated", where, findings)
    _require_enum(pillar, "lifecycleStage", LIFECYCLE_STAGES, where, findings)
    _optional_string(pillar, "createdAt", where, findings)
    _optional_string(pillar, "modelVersion", where, findings)
    _optional_string(pillar, "reviewBy", where, findings)
    _optional_string(pillar, "supersededBy", where, findings)
    return findings


# --------------------------------------------------------------------------- #
# Cross-pillar consistency (declared-vs-declared honesty checks)
# --------------------------------------------------------------------------- #

def _cross_pillar_consistency(model: dict[str, Any]) -> list[Finding]:
    """Warn when one pillar's claims contradict another's."""
    findings: list[Finding] = []

    # Sensitive data handling SHOULD come with an adequate assurance tier.
    constraints = model.get("constraints")
    assurance = model.get("assurance")
    if isinstance(constraints, dict) and isinstance(assurance, dict):
        sensitivity = constraints.get("dataSensitivity")
        tier = assurance.get("securityTier")
        if sensitivity in {"confidential", "restricted"} and tier in {"none", "standard"}:
            findings.append(
                Finding(
                    "warning",
                    "assurance.securityTier",
                    f"Handles {sensitivity!r} data but declares only {tier!r} assurance tier.",
                )
            )

    # A declared modelVersion SHOULD appear among the declared model dependencies.
    provenance = model.get("provenance")
    dependencies = model.get("dependencies")
    if isinstance(provenance, dict) and isinstance(dependencies, dict):
        model_version = provenance.get("modelVersion")
        declared = dependencies.get("declared")
        if isinstance(model_version, str) and model_version and isinstance(declared, list):
            model_names = {
                dep.get("name")
                for dep in declared
                if isinstance(dep, dict) and dep.get("type") == "model"
            }
            if model_version not in model_names:
                findings.append(
                    Finding(
                        "warning",
                        "provenance.modelVersion",
                        f"Declares modelVersion {model_version!r} but no model dependency lists it.",
                    )
                )
    return findings


# --------------------------------------------------------------------------- #
# Verification envelope (attestation)
# --------------------------------------------------------------------------- #

def validate_attestation(attestation: Any, where: str = "attestation") -> list[Finding]:
    """Validate the verification envelope's STRUCTURE.

    The envelope is what turns self-asserted claims into trustable ones: who
    asserted them, when, and until when. NOTE: the cryptographic `signature` is
    NOT verified here — verifying it would need a crypto library + key management,
    excluded from scope by choice (see README). We check its shape only. Freshness
    (is `validUntil` in the past?) is time-dependent and lives in audit.py.
    """
    if not isinstance(attestation, dict):
        return [Finding("error", where, "'attestation' must be an object.")]

    findings: list[Finding] = []
    _require_nonempty_string(attestation, "assertedBy", where, findings)
    _require_nonempty_string(attestation, "assertedAt", where, findings)
    _require_nonempty_string(attestation, "validUntil", where, findings)

    # assertedAt / validUntil SHOULD be ISO-8601 dates (warning if not).
    for field in ("assertedAt", "validUntil"):
        value = attestation.get(field)
        if isinstance(value, str) and value.strip() and parse_iso_date(value) is None:
            findings.append(
                Finding("warning", f"{where}.{field}", f"'{field}' is not an ISO-8601 date.")
            )

    if "signature" in attestation:
        signature = attestation["signature"]
        loc = f"{where}.signature"
        if not isinstance(signature, dict):
            findings.append(Finding("error", loc, "'signature' must be an object."))
        else:
            _require_nonempty_string(signature, "algorithm", loc, findings)
            _require_nonempty_string(signature, "value", loc, findings)
            # (Cryptographic verification is out of scope by choice — see README.)
    return findings


def parse_iso_date(value: Any) -> datetime.date | None:
    """Parse the date portion of an ISO-8601 date or datetime; None if unparseable.

    Tolerant on purpose: accepts 'YYYY-MM-DD' and full datetimes (taking the date
    part), so both `assertedAt: "2026-06-01"` and `"2026-06-01T12:00:00Z"` work.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()[:10]
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Shared field-check helpers
# --------------------------------------------------------------------------- #

def _require_nonempty_string(
    obj: dict[str, Any], field: str, where: str, findings: list[Finding]
) -> None:
    """A field must exist and be a non-empty string."""
    location = f"{where}.{field}"
    if field not in obj:
        findings.append(Finding("error", location, f"Missing required '{field}'."))
    elif not isinstance(obj[field], str) or not obj[field].strip():
        findings.append(Finding("error", location, f"'{field}' must be a non-empty string."))


def _require_enum(
    obj: dict[str, Any], field: str, allowed: set[str], where: str, findings: list[Finding]
) -> None:
    """A field must exist and be one of `allowed`."""
    location = f"{where}.{field}"
    if field not in obj:
        findings.append(Finding("error", location, f"Missing required '{field}'."))
    elif obj[field] not in allowed:
        findings.append(Finding("error", location, f"'{field}' must be one of {sorted(allowed)}."))


def _optional_enum(
    obj: dict[str, Any], field: str, allowed: set[str], where: str, findings: list[Finding]
) -> None:
    if field in obj and obj[field] not in allowed:
        findings.append(
            Finding("error", f"{where}.{field}", f"'{field}' must be one of {sorted(allowed)}.")
        )


def _optional_bool(obj: dict[str, Any], field: str, where: str, findings: list[Finding]) -> None:
    if field in obj and not isinstance(obj[field], bool):
        findings.append(Finding("error", f"{where}.{field}", f"'{field}' must be true or false."))


def _optional_string(obj: dict[str, Any], field: str, where: str, findings: list[Finding]) -> None:
    if field in obj and not isinstance(obj[field], str):
        findings.append(Finding("error", f"{where}.{field}", f"'{field}' must be a string."))


def _optional_string_list(obj: dict[str, Any], field: str, where: str, findings: list[Finding]) -> None:
    if field in obj:
        value = obj[field]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            findings.append(Finding("error", f"{where}.{field}", f"'{field}' must be a list of strings."))


def _optional_number(
    obj: dict[str, Any],
    field: str,
    where: str,
    findings: list[Finding],
    minimum: float | None = None,
) -> None:
    if field in obj:
        value = obj[field]
        # bool is a subclass of int, so exclude it explicitly.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            findings.append(Finding("error", f"{where}.{field}", f"'{field}' must be a number."))
        elif minimum is not None and value < minimum:
            findings.append(Finding("error", f"{where}.{field}", f"'{field}' must be >= {minimum}."))


# Registry of optional pillars (validated when present). Defined last so it can
# reference the validator functions above.
_OPTIONAL_PILLARS = {
    "capabilities": validate_capabilities,
    "permissions": validate_permissions,
    "constraints": validate_constraints,
    "dependencies": validate_dependencies,
    "escalation": validate_escalation,
    "state": validate_state,
    "confidence": validate_confidence,
    "assurance": validate_assurance,
    "provenance": validate_provenance,
}
