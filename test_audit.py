#!/usr/bin/env python3
"""Tests for the audit orchestrator and the first cross-check.

Pure functions (dicts in, findings out) — no network. Run:  python3 -m unittest -v
"""

import copy
import datetime
import unittest

from audit import check_freshness, cross_check, run_audit


VALID_CARD = {
    "name": "Invoice Assistant",
    "description": "Processes invoices.",
    "version": "1.0.0",
    "supportedInterfaces": [
        {"url": "https://x/rpc", "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}
    ],
    "capabilities": {},
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["text/plain"],
    "skills": [{"id": "s1", "name": "S", "description": "d", "tags": ["t"]}],
}

VALID_SELF_MODEL = {
    "selfModelVersion": "0.1",
    "identity": {
        "agentId": "urn:agent:example:invoice-assistant",
        "displayName": "Invoice Assistant",
        "owner": {
            "name": "Team",
            "organization": "Example Corp",
            "contact": "team@example.com",
        },
    },
    "capabilities": {
        # skillId "s1" matches VALID_CARD's only skill, so cross-check is clean.
        "declared": [{"skillId": "s1", "maturity": "stable"}]
    },
}


class RunAuditTests(unittest.TestCase):
    def test_valid_card_and_self_model_passes(self):
        report = run_audit(VALID_CARD, VALID_SELF_MODEL)
        self.assertTrue(report.passed)
        self.assertTrue(report.self_model_present)

    def test_card_only_is_supported(self):
        report = run_audit(VALID_CARD, None)
        self.assertTrue(report.passed)
        self.assertFalse(report.self_model_present)
        self.assertEqual(report.self_model_findings, [])

    def test_broken_self_model_fails_the_whole_audit(self):
        broken = copy.deepcopy(VALID_SELF_MODEL)
        del broken["identity"]["agentId"]
        report = run_audit(VALID_CARD, broken)
        self.assertFalse(report.passed)
        self.assertTrue(any(f.location == "identity.agentId" for f in report.errors))

    def test_broken_card_fails_even_with_good_self_model(self):
        broken = copy.deepcopy(VALID_CARD)
        del broken["name"]
        report = run_audit(broken, VALID_SELF_MODEL)
        self.assertFalse(report.passed)


class CrossCheckTests(unittest.TestCase):
    def test_matching_names_produce_no_finding(self):
        self.assertEqual(cross_check(VALID_CARD, VALID_SELF_MODEL), [])

    def test_mismatched_display_name_is_flagged(self):
        model = copy.deepcopy(VALID_SELF_MODEL)
        model["identity"]["displayName"] = "Something Else"
        findings = cross_check(VALID_CARD, model)
        self.assertTrue(any(f.location == "identity.displayName" for f in findings))
        # It's a SHOULD, so a warning — never a hard error.
        self.assertTrue(all(f.severity == "warning" for f in findings))

    def test_no_display_name_means_nothing_to_cross_check(self):
        model = copy.deepcopy(VALID_SELF_MODEL)
        del model["identity"]["displayName"]
        self.assertEqual(cross_check(VALID_CARD, model), [])

    def test_capability_referencing_real_skill_is_clean(self):
        # VALID_SELF_MODEL declares skillId "s1", which VALID_CARD exposes.
        locations = {f.location for f in cross_check(VALID_CARD, VALID_SELF_MODEL)}
        self.assertNotIn("capabilities.declared[0].skillId", locations)

    def test_capability_referencing_missing_skill_is_flagged(self):
        model = copy.deepcopy(VALID_SELF_MODEL)
        model["capabilities"]["declared"][0]["skillId"] = "does-not-exist"
        findings = cross_check(VALID_CARD, model)
        self.assertTrue(
            any(f.location == "capabilities.declared[0].skillId" for f in findings)
        )
        self.assertTrue(all(f.severity == "warning" for f in findings))

    def test_acting_agent_without_security_schemes_is_flagged(self):
        # Card has no securitySchemes; self-model claims it can act -> warning.
        model = copy.deepcopy(VALID_SELF_MODEL)
        model["permissions"] = {"authorityLevel": "autonomous"}
        findings = cross_check(VALID_CARD, model)
        self.assertTrue(any(f.location == "permissions.authorityLevel" for f in findings))

    def test_acting_agent_with_security_schemes_is_clean(self):
        card = copy.deepcopy(VALID_CARD)
        card["securitySchemes"] = {"bearerAuth": {"type": "http", "scheme": "bearer"}}
        model = copy.deepcopy(VALID_SELF_MODEL)
        model["permissions"] = {"authorityLevel": "autonomous"}
        locations = {f.location for f in cross_check(card, model)}
        self.assertNotIn("permissions.authorityLevel", locations)

    def test_read_only_agent_without_security_schemes_is_fine(self):
        model = copy.deepcopy(VALID_SELF_MODEL)
        model["permissions"] = {"authorityLevel": "read-only"}
        locations = {f.location for f in cross_check(VALID_CARD, model)}
        self.assertNotIn("permissions.authorityLevel", locations)


class FreshnessTests(unittest.TestCase):
    TODAY = datetime.date(2026, 7, 13)

    def _with_attestation(self, valid_until):
        model = copy.deepcopy(VALID_SELF_MODEL)
        model["attestation"] = {
            "assertedBy": "urn:x",
            "assertedAt": "2026-01-01",
            "validUntil": valid_until,
        }
        return model

    def test_expired_attestation_is_flagged(self):
        findings = check_freshness(self._with_attestation("2025-01-01"), self.TODAY)
        self.assertTrue(any(f.location == "attestation.validUntil" for f in findings))

    def test_fresh_attestation_is_clean(self):
        self.assertEqual(check_freshness(self._with_attestation("2027-01-01"), self.TODAY), [])

    def test_missing_attestation_produces_no_freshness_finding(self):
        # (Absence is reported elsewhere as 'unattested', not by the freshness check.)
        self.assertEqual(check_freshness(VALID_SELF_MODEL, self.TODAY), [])

    def test_run_audit_surfaces_expired_attestation(self):
        report = run_audit(VALID_CARD, self._with_attestation("2025-01-01"), today=self.TODAY)
        self.assertTrue(any(f.location == "attestation.validUntil" for f in report.attestation_findings))


if __name__ == "__main__":
    unittest.main()
