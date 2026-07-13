#!/usr/bin/env python3
"""Tests for the Agent Self-Model validator (Identity & Ownership pillar).

Same discipline as the A2A tests: start from a known-good model, break one field
at a time, assert the specific rule fires. Run with:  python3 -m unittest -v
"""

import copy
import unittest

from agent_self_model import (
    validate_assurance,
    validate_attestation,
    validate_capabilities,
    validate_confidence,
    validate_constraints,
    validate_dependencies,
    validate_escalation,
    validate_identity_ownership,
    validate_permissions,
    validate_provenance,
    validate_self_model,
    validate_state,
)


GOOD_MODEL = {
    "selfModelVersion": "0.1",
    "identity": {
        "agentId": "urn:agent:example:invoice-assistant",
        "displayName": "Invoice Assistant",
        "owner": {
            "name": "Finance Automation Team",
            "organization": "Example Corp",
            "contact": "ai-ownership@example.com",
            "role": "Product Owner",
        },
    },
}


def error_locations(model) -> set[str]:
    return {f.location for f in validate_self_model(model) if f.severity == "error"}


class WholeModelTests(unittest.TestCase):
    def test_good_model_has_no_errors(self):
        findings = validate_self_model(GOOD_MODEL)
        errors = [f for f in findings if f.severity == "error"]
        self.assertEqual(errors, [], f"expected no errors, got {errors}")

    def test_missing_identity_pillar_is_required(self):
        self.assertIn("identity", error_locations({"selfModelVersion": "0.1"}))

    def test_non_object_model_is_rejected(self):
        self.assertTrue(any(f.severity == "error" for f in validate_self_model("nope")))


class IdentityFieldTests(unittest.TestCase):
    def test_agent_id_is_required(self):
        model = copy.deepcopy(GOOD_MODEL)
        del model["identity"]["agentId"]
        self.assertIn("identity.agentId", error_locations(model))

    def test_empty_agent_id_is_rejected(self):
        model = copy.deepcopy(GOOD_MODEL)
        model["identity"]["agentId"] = "   "
        self.assertIn("identity.agentId", error_locations(model))

    def test_display_name_wrong_type_is_reported(self):
        model = copy.deepcopy(GOOD_MODEL)
        model["identity"]["displayName"] = 123
        self.assertIn("identity.displayName", error_locations(model))

    def test_display_name_is_optional(self):
        model = copy.deepcopy(GOOD_MODEL)
        del model["identity"]["displayName"]
        self.assertNotIn("identity.displayName", error_locations(model))


class OwnerTests(unittest.TestCase):
    def test_owner_is_required(self):
        model = copy.deepcopy(GOOD_MODEL)
        del model["identity"]["owner"]
        self.assertIn("identity.owner", error_locations(model))

    def test_each_required_owner_field_is_reported(self):
        for field in ("name", "organization", "contact"):
            with self.subTest(field=field):
                model = copy.deepcopy(GOOD_MODEL)
                del model["identity"]["owner"][field]
                self.assertIn(f"identity.owner.{field}", error_locations(model))

    def test_role_is_optional(self):
        model = copy.deepcopy(GOOD_MODEL)
        del model["identity"]["owner"]["role"]
        self.assertNotIn("identity.owner.role", error_locations(model))

    def test_unreachable_contact_is_a_warning_not_error(self):
        pillar = copy.deepcopy(GOOD_MODEL["identity"])
        pillar["owner"]["contact"] = "call-me-maybe"
        findings = validate_identity_ownership(pillar)
        errors = [f for f in findings if f.severity == "error"]
        warnings = [f for f in findings if f.severity == "warning"]
        self.assertEqual(errors, [])
        self.assertTrue(any(f.location == "identity.owner.contact" for f in warnings))


GOOD_CAPABILITIES = {
    "declared": [
        {
            "skillId": "summarize-invoice",
            "maturity": "stable",
            "proficiency": "high",
            "tested": True,
            "knownLimits": ["Invoices up to 10 MB"],
            "failureModes": ["Struggles with handwritten scans"],
        }
    ]
}


class CapabilitiesTests(unittest.TestCase):
    def _errors(self, pillar):
        return {f.location for f in validate_capabilities(pillar) if f.severity == "error"}

    def test_good_capabilities_has_no_errors(self):
        self.assertEqual(self._errors(GOOD_CAPABILITIES), set())

    def test_capabilities_pillar_is_optional(self):
        # A model with only identity (no capabilities) still passes overall.
        model = copy.deepcopy(GOOD_MODEL)
        self.assertNotIn("capabilities", model)
        errors = [f for f in validate_self_model(model) if f.severity == "error"]
        self.assertEqual(errors, [])

    def test_declared_is_required(self):
        self.assertIn("capabilities.declared", self._errors({}))

    def test_declared_must_be_a_list(self):
        self.assertIn("capabilities.declared", self._errors({"declared": "nope"}))

    def test_empty_declared_is_a_warning_not_error(self):
        findings = validate_capabilities({"declared": []})
        self.assertEqual([f for f in findings if f.severity == "error"], [])
        self.assertTrue(any(f.severity == "warning" for f in findings))

    def test_skill_id_is_required_per_entry(self):
        pillar = {"declared": [{"maturity": "stable"}]}
        self.assertIn("capabilities.declared[0].skillId", self._errors(pillar))

    def test_maturity_is_required(self):
        pillar = {"declared": [{"skillId": "s1"}]}
        self.assertIn("capabilities.declared[0].maturity", self._errors(pillar))

    def test_unknown_maturity_is_rejected(self):
        pillar = {"declared": [{"skillId": "s1", "maturity": "super-stable"}]}
        self.assertIn("capabilities.declared[0].maturity", self._errors(pillar))

    def test_unknown_proficiency_is_rejected(self):
        pillar = {"declared": [{"skillId": "s1", "maturity": "stable", "proficiency": "godlike"}]}
        self.assertIn("capabilities.declared[0].proficiency", self._errors(pillar))

    def test_tested_must_be_boolean(self):
        pillar = {"declared": [{"skillId": "s1", "maturity": "stable", "tested": "yes"}]}
        self.assertIn("capabilities.declared[0].tested", self._errors(pillar))

    def test_known_limits_must_be_list_of_strings(self):
        pillar = {"declared": [{"skillId": "s1", "maturity": "stable", "knownLimits": "big"}]}
        self.assertIn("capabilities.declared[0].knownLimits", self._errors(pillar))


class PermissionsTests(unittest.TestCase):
    GOOD = {
        "authorityLevel": "act-with-approval",
        "allowedActions": ["read"],
        "prohibitedActions": ["pay"],
        "requiresAuthentication": True,
        "spendingLimit": {"currency": "USD", "maxPerAction": 0},
    }

    def _errors(self, pillar):
        return {f.location for f in validate_permissions(pillar) if f.severity == "error"}

    def test_valid_permissions_has_no_errors(self):
        self.assertEqual(self._errors(self.GOOD), set())

    def test_authority_level_is_required(self):
        self.assertIn("permissions.authorityLevel", self._errors({}))

    def test_unknown_authority_level_is_rejected(self):
        self.assertIn("permissions.authorityLevel", self._errors({"authorityLevel": "god-mode"}))

    def test_spending_limit_requires_max_per_action(self):
        pillar = {"authorityLevel": "read-only", "spendingLimit": {"currency": "USD"}}
        self.assertIn("permissions.spendingLimit.maxPerAction", self._errors(pillar))

    def test_allowed_actions_must_be_list_of_strings(self):
        pillar = {"authorityLevel": "read-only", "allowedActions": "read"}
        self.assertIn("permissions.allowedActions", self._errors(pillar))


class ConstraintsTests(unittest.TestCase):
    def _errors(self, pillar):
        return {f.location for f in validate_constraints(pillar) if f.severity == "error"}

    def test_valid_constraints_has_no_errors(self):
        good = {"dataSensitivity": "confidential", "rateLimitPerMinute": 60, "jurisdictions": ["EU"]}
        self.assertEqual(self._errors(good), set())

    def test_data_sensitivity_is_required(self):
        self.assertIn("constraints.dataSensitivity", self._errors({"dataResidency": "EU"}))

    def test_unknown_sensitivity_is_rejected(self):
        self.assertIn("constraints.dataSensitivity", self._errors({"dataSensitivity": "top-secret"}))

    def test_negative_rate_limit_is_rejected(self):
        pillar = {"dataSensitivity": "public", "rateLimitPerMinute": -1}
        self.assertIn("constraints.rateLimitPerMinute", self._errors(pillar))


class DependenciesTests(unittest.TestCase):
    def _errors(self, pillar):
        return {f.location for f in validate_dependencies(pillar) if f.severity == "error"}

    def test_valid_dependencies_has_no_errors(self):
        good = {"declared": [{"type": "model", "name": "claude-opus-4-8", "critical": True}]}
        self.assertEqual(self._errors(good), set())

    def test_declared_is_required(self):
        self.assertIn("dependencies.declared", self._errors({}))

    def test_entry_type_is_required_and_enumerated(self):
        self.assertIn("dependencies.declared[0].type", self._errors({"declared": [{"name": "x"}]}))
        self.assertIn(
            "dependencies.declared[0].type",
            self._errors({"declared": [{"type": "wormhole", "name": "x"}]}),
        )

    def test_entry_name_is_required(self):
        self.assertIn(
            "dependencies.declared[0].name", self._errors({"declared": [{"type": "tool"}]})
        )


class EscalationTests(unittest.TestCase):
    GOOD = {
        "triggers": ["low-confidence"],
        "target": {"type": "human", "contact": "oncall@example.com"},
        "fallbackBehavior": "halt",
    }

    def _errors(self, pillar):
        return {f.location for f in validate_escalation(pillar) if f.severity == "error"}

    def test_valid_escalation_has_no_errors(self):
        self.assertEqual(self._errors(self.GOOD), set())

    def test_empty_triggers_is_rejected(self):
        pillar = copy.deepcopy(self.GOOD)
        pillar["triggers"] = []
        self.assertIn("escalation.triggers", self._errors(pillar))

    def test_target_is_required(self):
        pillar = {"triggers": ["x"]}
        self.assertIn("escalation.target", self._errors(pillar))

    def test_target_type_is_enumerated(self):
        pillar = copy.deepcopy(self.GOOD)
        pillar["target"]["type"] = "robot"
        self.assertIn("escalation.target.type", self._errors(pillar))


class StateTests(unittest.TestCase):
    def _errors(self, pillar):
        return {f.location for f in validate_state(pillar) if f.severity == "error"}

    def test_valid_state_has_no_errors(self):
        good = {"status": "operational", "degradationPolicy": "graceful"}
        self.assertEqual(self._errors(good), set())

    def test_status_is_required(self):
        self.assertIn("state.status", self._errors({}))

    def test_unknown_status_is_rejected(self):
        self.assertIn("state.status", self._errors({"status": "on-fire"}))


class ConfidenceTests(unittest.TestCase):
    def _errors(self, pillar):
        return {f.location for f in validate_confidence(pillar) if f.severity == "error"}

    def test_valid_confidence_has_no_errors(self):
        good = {"calibration": "calibrated", "reportsConfidence": True}
        self.assertEqual(self._errors(good), set())

    def test_calibration_is_required(self):
        self.assertIn("confidence.calibration", self._errors({"reportsConfidence": True}))


class AssuranceTests(unittest.TestCase):
    def _errors(self, pillar):
        return {f.location for f in validate_assurance(pillar) if f.severity == "error"}

    def test_valid_assurance_has_no_errors(self):
        good = {"securityTier": "high", "certifications": ["SOC2"], "sandboxed": True}
        self.assertEqual(self._errors(good), set())

    def test_security_tier_is_required(self):
        self.assertIn("assurance.securityTier", self._errors({"certifications": ["SOC2"]}))

    def test_unknown_tier_is_rejected(self):
        self.assertIn("assurance.securityTier", self._errors({"securityTier": "ultra"}))


class ProvenanceTests(unittest.TestCase):
    def _errors(self, pillar):
        return {f.location for f in validate_provenance(pillar) if f.severity == "error"}

    def test_valid_provenance_has_no_errors(self):
        good = {"lastUpdated": "2026-06-01", "lifecycleStage": "active"}
        self.assertEqual(self._errors(good), set())

    def test_last_updated_is_required(self):
        self.assertIn("provenance.lastUpdated", self._errors({"lifecycleStage": "active"}))

    def test_unknown_lifecycle_stage_is_rejected(self):
        pillar = {"lastUpdated": "2026-06-01", "lifecycleStage": "zombie"}
        self.assertIn("provenance.lifecycleStage", self._errors(pillar))


class CrossPillarConsistencyTests(unittest.TestCase):
    """Whole-model checks: one pillar contradicting another (warnings)."""

    def _warnings(self, model):
        return {f.location for f in validate_self_model(model) if f.severity == "warning"}

    def _base(self):
        return copy.deepcopy(GOOD_MODEL)  # has identity only; passes with no errors

    def test_sensitive_data_with_low_assurance_is_flagged(self):
        model = self._base()
        model["constraints"] = {"dataSensitivity": "restricted"}
        model["assurance"] = {"securityTier": "standard"}
        self.assertIn("assurance.securityTier", self._warnings(model))

    def test_sensitive_data_with_high_assurance_is_clean(self):
        model = self._base()
        model["constraints"] = {"dataSensitivity": "restricted"}
        model["assurance"] = {"securityTier": "critical"}
        self.assertNotIn("assurance.securityTier", self._warnings(model))

    def test_model_version_not_in_dependencies_is_flagged(self):
        model = self._base()
        model["provenance"] = {"lastUpdated": "2026-06-01", "lifecycleStage": "active", "modelVersion": "gpt-5"}
        model["dependencies"] = {"declared": [{"type": "model", "name": "claude-opus-4-8"}]}
        self.assertIn("provenance.modelVersion", self._warnings(model))

    def test_model_version_present_in_dependencies_is_clean(self):
        model = self._base()
        model["provenance"] = {"lastUpdated": "2026-06-01", "lifecycleStage": "active", "modelVersion": "claude-opus-4-8"}
        model["dependencies"] = {"declared": [{"type": "model", "name": "claude-opus-4-8"}]}
        self.assertNotIn("provenance.modelVersion", self._warnings(model))


class AttestationTests(unittest.TestCase):
    GOOD = {
        "assertedBy": "urn:org:example:governance",
        "assertedAt": "2026-06-01",
        "validUntil": "2027-06-01",
        "signature": {"algorithm": "RS256", "value": "abc123"},
    }

    def _errors(self, attestation):
        return {f.location for f in validate_attestation(attestation) if f.severity == "error"}

    def test_valid_attestation_has_no_errors(self):
        self.assertEqual(self._errors(self.GOOD), set())

    def test_asserted_by_is_required(self):
        att = copy.deepcopy(self.GOOD)
        del att["assertedBy"]
        self.assertIn("attestation.assertedBy", self._errors(att))

    def test_valid_until_is_required(self):
        att = copy.deepcopy(self.GOOD)
        del att["validUntil"]
        self.assertIn("attestation.validUntil", self._errors(att))

    def test_non_iso_date_is_a_warning(self):
        att = copy.deepcopy(self.GOOD)
        att["assertedAt"] = "sometime last June"
        findings = validate_attestation(att)
        self.assertTrue(
            any(f.location == "attestation.assertedAt" and f.severity == "warning" for f in findings)
        )

    def test_signature_requires_value(self):
        att = copy.deepcopy(self.GOOD)
        att["signature"] = {"algorithm": "RS256"}
        self.assertIn("attestation.signature.value", self._errors(att))

    def test_unattested_model_is_warned(self):
        # GOOD_MODEL has no attestation -> a warning at 'attestation'.
        warnings = {f.location for f in validate_self_model(GOOD_MODEL) if f.severity == "warning"}
        self.assertIn("attestation", warnings)


if __name__ == "__main__":
    unittest.main()
