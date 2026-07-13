#!/usr/bin/env python3
"""Agent Auditor — the tool.

Audit an agent's A2A Agent Card and its Agent Self-Model together, and print one
report. Given an agent (a base URL, or explicit card/self-model files or URLs) it:

  1. validates the A2A v1.0 Agent Card,
  2. validates the Agent Self-Model (if the agent publishes one),
  3. cross-checks the two — the first "declared vs. observed" honesty check:
     does the Self-Model's displayName actually match the A2A card's name?

Usage:
  python3 audit.py https://some-agent.example.com
  python3 audit.py examples/valid-card.json --self-model examples/valid-self-model.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.error
from dataclasses import dataclass, field
from typing import Any

import agent_auditor
import agent_self_model
from fetch import load_json
from findings import Finding


@dataclass
class AuditReport:
    """The combined result of auditing one agent."""

    card_findings: list[Finding] = field(default_factory=list)
    self_model_findings: list[Finding] = field(default_factory=list)
    cross_findings: list[Finding] = field(default_factory=list)
    attestation_findings: list[Finding] = field(default_factory=list)
    self_model_present: bool = False

    def all_findings(self) -> list[Finding]:
        return (
            self.card_findings
            + self.self_model_findings
            + self.cross_findings
            + self.attestation_findings
        )

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.all_findings() if f.severity == "error"]

    @property
    def passed(self) -> bool:
        return not self.errors


def cross_check(card: Any, self_model: Any) -> list[Finding]:
    """Declared-vs-observed checks between the Self-Model and the A2A card.

    This is the heart of the tool: the self-model is self-asserted, and here we
    hold each assertion up against the card the agent actually serves. Mismatches
    are warnings (these are SHOULD-level consistency checks, not MUSTs) — but they
    are exactly the inconsistencies an auditor exists to surface.
    """
    findings: list[Finding] = []
    if not isinstance(card, dict) or not isinstance(self_model, dict):
        return findings
    findings += _cross_check_identity(card, self_model)
    findings += _cross_check_capabilities(card, self_model)
    findings += _cross_check_permissions(card, self_model)
    return findings


def _cross_check_identity(card: dict[str, Any], self_model: dict[str, Any]) -> list[Finding]:
    """The Self-Model's displayName SHOULD match the card's name."""
    identity = self_model.get("identity")
    if not isinstance(identity, dict):
        return []

    display_name = identity.get("displayName")
    card_name = card.get("name")
    if (
        isinstance(display_name, str)
        and isinstance(card_name, str)
        and display_name != card_name
    ):
        return [
            Finding(
                "warning",
                "identity.displayName",
                f"Self-Model displayName {display_name!r} does not match "
                f"A2A card name {card_name!r}.",
            )
        ]
    return []


def _cross_check_capabilities(card: dict[str, Any], self_model: dict[str, Any]) -> list[Finding]:
    """Each declared capability SHOULD reference a skill the card actually exposes."""
    capabilities = self_model.get("capabilities")
    if not isinstance(capabilities, dict):
        return []
    declared = capabilities.get("declared")
    if not isinstance(declared, list):
        return []

    card_skill_ids = {
        skill["id"]
        for skill in card.get("skills", [])
        if isinstance(skill, dict) and isinstance(skill.get("id"), str)
    }

    findings: list[Finding] = []
    for index, capability in enumerate(declared):
        if not isinstance(capability, dict):
            continue
        skill_id = capability.get("skillId")
        if isinstance(skill_id, str) and skill_id and skill_id not in card_skill_ids:
            findings.append(
                Finding(
                    "warning",
                    f"capabilities.declared[{index}].skillId",
                    f"Self-Model declares a capability for skill {skill_id!r}, but the "
                    f"A2A card exposes no such skill.",
                )
            )
    return findings


def _cross_check_permissions(card: dict[str, Any], self_model: dict[str, Any]) -> list[Finding]:
    """An agent that claims authority to ACT SHOULD expose authentication.

    If the self-model says the agent can act (not just read) but the A2A card
    declares no `securitySchemes`, that's a governance red flag — an acting agent
    with no way to authenticate callers.
    """
    permissions = self_model.get("permissions")
    if not isinstance(permissions, dict):
        return []

    if permissions.get("authorityLevel") not in {"act-with-approval", "autonomous"}:
        return []

    schemes = card.get("securitySchemes")
    if not isinstance(schemes, dict) or not schemes:
        return [
            Finding(
                "warning",
                "permissions.authorityLevel",
                f"Self-Model claims authority {permissions.get('authorityLevel')!r} "
                f"(the agent can act), but the A2A card declares no securitySchemes.",
            )
        ]
    return []


def run_audit(card: Any, self_model: Any | None, today: datetime.date | None = None) -> AuditReport:
    """Orchestration: validate both docs, cross-check, and check attestation freshness.

    `today` is injectable so freshness checks are deterministic in tests; the CLI
    passes the real current date.
    """
    card_findings = agent_auditor.validate_agent_card(card)
    if self_model is None:
        return AuditReport(card_findings=card_findings, self_model_present=False)
    if today is None:
        today = datetime.date.today()
    return AuditReport(
        card_findings=card_findings,
        self_model_findings=agent_self_model.validate_self_model(self_model),
        cross_findings=cross_check(card, self_model),
        attestation_findings=check_freshness(self_model, today),
        self_model_present=True,
    )


def check_freshness(self_model: Any, today: datetime.date) -> list[Finding]:
    """Time-dependent check: has the attestation's validUntil passed?

    Absence of an attestation is reported by structure validation (as 'unattested'),
    not here — this only fires when there's a dated envelope to check.
    """
    if not isinstance(self_model, dict):
        return []
    attestation = self_model.get("attestation")
    if not isinstance(attestation, dict):
        return []
    valid_until = agent_self_model.parse_iso_date(attestation.get("validUntil"))
    if valid_until is not None and valid_until < today:
        return [
            Finding(
                "warning",
                "attestation.validUntil",
                f"Attestation expired on {valid_until.isoformat()} (as of {today.isoformat()}).",
            )
        ]
    return []


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

def _format_section(title: str, findings: list[Finding], present: bool = True) -> list[str]:
    if not present:
        return [f"{title}: — not provided —"]
    errors = [f for f in findings if f.severity == "error"]
    verdict = "PASS ✅" if not errors else f"FAIL ❌ ({len(errors)} error(s))"
    lines = [f"{title}: {verdict}"]
    for finding in findings:
        mark = "✗" if finding.severity == "error" else "⚠"
        lines.append(f"  {mark} [{finding.location}] {finding.message}")
    return lines


def format_audit_report(source: str, report: AuditReport) -> str:
    lines = [f"Agent Auditor — {source}", ""]
    lines += _format_section(f"A2A Agent Card (v{agent_auditor.A2A_TARGET_VERSION})", report.card_findings)
    lines.append("")
    lines += _format_section("Agent Self-Model", report.self_model_findings, report.self_model_present)
    if report.self_model_present:
        lines.append("")
        lines += _format_section("Cross-checks (declared vs. observed)", report.cross_findings)
        lines.append("")
        lines += _format_section("Attestation (freshness)", report.attestation_findings)
    lines.append("")
    if report.passed:
        lines.append("OVERALL: PASS ✅")
    else:
        lines.append(f"OVERALL: FAIL ❌ ({len(report.errors)} error(s))")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _looks_like_base_url(source: str) -> bool:
    return source.startswith(("http://", "https://")) and not source.endswith(".json")


def _load_or_exit(source: str, well_known_path: str, label: str, timeout: float) -> dict[str, Any]:
    try:
        return load_json(source, well_known_path, timeout=timeout)
    except FileNotFoundError:
        print(f"Could not open {label} file: {source}", file=sys.stderr)
        raise SystemExit(2)
    except urllib.error.URLError as exc:
        print(f"Could not fetch {label} from {source}: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except json.JSONDecodeError as exc:
        print(f"{label} is not valid JSON: {exc}", file=sys.stderr)
        raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit an agent's A2A card and Agent Self-Model.")
    parser.add_argument(
        "source",
        help="Agent base URL, a card URL, or a local card .json file.",
    )
    parser.add_argument(
        "--self-model",
        dest="self_model",
        default=None,
        help="Self-Model URL or local .json file. If omitted and `source` is a base "
        "URL, it is looked up at the well-known path.",
    )
    parser.add_argument(
        "--timeout", type=float, default=10.0, help="HTTP timeout in seconds (default 10)."
    )
    args = parser.parse_args(argv)

    # The card is required.
    card = _load_or_exit(args.source, agent_auditor.WELL_KNOWN_CARD_PATH, "card", args.timeout)

    # The self-model is optional. Use --self-model if given; otherwise, if the
    # source is a base URL, try the well-known path (a 404 there is not fatal).
    self_model: dict[str, Any] | None = None
    explicit = args.self_model is not None
    self_model_source = args.self_model or (args.source if _looks_like_base_url(args.source) else None)

    if self_model_source is not None:
        try:
            self_model = load_json(
                self_model_source, agent_self_model.WELL_KNOWN_SELF_MODEL_PATH, timeout=args.timeout
            )
        except (FileNotFoundError, urllib.error.URLError):
            if explicit:  # user asked for a specific self-model — missing is an error
                print(f"Could not load self-model from {self_model_source}", file=sys.stderr)
                return 2
            self_model = None  # derived lookup; agent simply doesn't publish one
        except json.JSONDecodeError as exc:
            print(f"Self-model is not valid JSON: {exc}", file=sys.stderr)
            return 2

    report = run_audit(card, self_model)
    print(format_audit_report(args.source, report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
