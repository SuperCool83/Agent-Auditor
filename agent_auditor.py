#!/usr/bin/env python3
"""A2A v1.0 Agent Card validation.

Pure validation: an already-loaded Agent Card (a dict parsed from JSON) goes in,
a list of Findings comes out. Loading lives in fetch.py; orchestration and the
CLI live in audit.py.

A2A facts this validator encodes (verified against the v1.0 spec / a2a.proto):
  - The Agent Card is served at:  GET /.well-known/agent-card.json
  - Required top-level fields: name, description, supportedInterfaces, version,
    capabilities, defaultInputModes, defaultOutputModes, skills
  - Each supportedInterfaces[] entry requires: url, protocolBinding, protocolVersion
  - Each skills[] entry requires: id, name, description, tags
Note: v1.0 is a hard reset from v0.2/0.3 — top-level `url`/`protocolVersion` and
the old `agent.json` path are legacy and intentionally NOT accepted here.
"""

from __future__ import annotations

from typing import Any

from findings import Finding

# The version of A2A this validator targets. Compatibility is negotiated on
# Major.Minor, so we track "1.0" (patch releases don't affect the protocol).
A2A_TARGET_VERSION = "1.0"

# The IANA-registered well-known path where an A2A agent publishes its card.
WELL_KNOWN_CARD_PATH = "/.well-known/agent-card.json"

# The three official transport bindings in A2A v1.0. Unknown values are legal
# (it's an open string) but we surface them as a warning.
KNOWN_PROTOCOL_BINDINGS = {"JSONRPC", "GRPC", "HTTP+JSON"}

# Required top-level fields mapped to the Python type we expect after JSON parse.
_REQUIRED_TOP_LEVEL: dict[str, type | tuple[type, ...]] = {
    "name": str,
    "description": str,
    "version": str,
    "supportedInterfaces": list,
    "capabilities": dict,
    "defaultInputModes": list,
    "defaultOutputModes": list,
    "skills": list,
}

_INTERFACE_REQUIRED = ("url", "protocolBinding", "protocolVersion")
_SKILL_REQUIRED = ("id", "name", "description", "tags")


def validate_agent_card(card: Any) -> list[Finding]:
    """Return a list of Findings. An empty list means the card passed."""
    findings: list[Finding] = []

    if not isinstance(card, dict):
        return [Finding("error", "(root)", "Agent Card must be a JSON object.")]

    _check_top_level(card, findings)
    _check_interfaces(card.get("supportedInterfaces"), findings)
    _check_skills(card.get("skills"), findings)
    _check_string_lists(card, findings)
    return findings


def _check_top_level(card: dict[str, Any], findings: list[Finding]) -> None:
    for field, expected_type in _REQUIRED_TOP_LEVEL.items():
        if field not in card:
            findings.append(Finding("error", field, f"Missing required field '{field}'."))
        elif not isinstance(card[field], expected_type):
            type_name = getattr(expected_type, "__name__", str(expected_type))
            findings.append(
                Finding("error", field, f"Field '{field}' must be a {type_name}.")
            )

    # A card with an empty interface list technically has the field but is
    # unusable — clients would have nowhere to connect.
    interfaces = card.get("supportedInterfaces")
    if isinstance(interfaces, list) and not interfaces:
        findings.append(
            Finding("error", "supportedInterfaces", "Must list at least one interface.")
        )


def _check_interfaces(interfaces: Any, findings: list[Finding]) -> None:
    if not isinstance(interfaces, list):
        return  # already reported by the top-level check
    for index, interface in enumerate(interfaces):
        where = f"supportedInterfaces[{index}]"
        if not isinstance(interface, dict):
            findings.append(Finding("error", where, "Interface must be an object."))
            continue
        for field in _INTERFACE_REQUIRED:
            if field not in interface:
                findings.append(Finding("error", f"{where}.{field}", f"Missing '{field}'."))
        binding = interface.get("protocolBinding")
        if isinstance(binding, str) and binding not in KNOWN_PROTOCOL_BINDINGS:
            findings.append(
                Finding(
                    "warning",
                    f"{where}.protocolBinding",
                    f"Unrecognized binding '{binding}' (expected one of "
                    f"{', '.join(sorted(KNOWN_PROTOCOL_BINDINGS))}).",
                )
            )


def _check_skills(skills: Any, findings: list[Finding]) -> None:
    if not isinstance(skills, list):
        return
    for index, skill in enumerate(skills):
        where = f"skills[{index}]"
        if not isinstance(skill, dict):
            findings.append(Finding("error", where, "Skill must be an object."))
            continue
        for field in _SKILL_REQUIRED:
            if field not in skill:
                findings.append(Finding("error", f"{where}.{field}", f"Missing '{field}'."))
        if "tags" in skill and not isinstance(skill["tags"], list):
            findings.append(Finding("error", f"{where}.tags", "'tags' must be an array."))


def _check_string_lists(card: dict[str, Any], findings: list[Finding]) -> None:
    """defaultInputModes / defaultOutputModes must be lists of media-type strings."""
    for field in ("defaultInputModes", "defaultOutputModes"):
        value = card.get(field)
        if isinstance(value, list) and not all(isinstance(item, str) for item in value):
            findings.append(Finding("error", field, f"'{field}' must be a list of strings."))
