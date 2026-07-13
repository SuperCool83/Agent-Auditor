#!/usr/bin/env python3
"""Tests for the Agent Card validator.

Uses only the standard library's `unittest` — no pytest, no installs.
Run with:  python3 -m unittest -v

The strategy: start from a known-good card, then break it one field at a time
and assert that the *specific* rule we expect actually fires. Testing each rule
in isolation is what stops a future edit from silently disabling a check.
"""

import copy
import unittest

from agent_auditor import Finding, validate_agent_card


# A minimal card that MUST pass. Each test copies this and breaks one thing.
GOOD_CARD = {
    "name": "Test Agent",
    "description": "An agent used in tests.",
    "version": "1.0.0",
    "supportedInterfaces": [
        {
            "url": "https://example.com/rpc",
            "protocolBinding": "JSONRPC",
            "protocolVersion": "1.0",
        }
    ],
    "capabilities": {"streaming": False},
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["text/plain"],
    "skills": [
        {
            "id": "s1",
            "name": "Skill One",
            "description": "Does one thing.",
            "tags": ["test"],
        }
    ],
}


def locations_with_errors(card) -> set[str]:
    """Helper: run the validator and return the set of error locations."""
    return {f.location for f in validate_agent_card(card) if f.severity == "error"}


class ValidCardTests(unittest.TestCase):
    def test_good_card_has_no_errors(self):
        findings = validate_agent_card(GOOD_CARD)
        errors = [f for f in findings if f.severity == "error"]
        self.assertEqual(errors, [], f"expected no errors, got {errors}")

    def test_non_object_card_is_rejected(self):
        findings = validate_agent_card(["not", "an", "object"])
        self.assertTrue(any(f.severity == "error" for f in findings))


class MissingRequiredFieldTests(unittest.TestCase):
    def test_each_missing_top_level_field_is_reported(self):
        # Every required top-level field, when removed, should produce an error
        # located at that field name.
        for field in (
            "name",
            "description",
            "version",
            "supportedInterfaces",
            "capabilities",
            "defaultInputModes",
            "defaultOutputModes",
            "skills",
        ):
            with self.subTest(field=field):
                card = copy.deepcopy(GOOD_CARD)
                del card[field]
                self.assertIn(field, locations_with_errors(card))

    def test_wrong_type_top_level_field_is_reported(self):
        card = copy.deepcopy(GOOD_CARD)
        card["name"] = 123  # should be a string
        self.assertIn("name", locations_with_errors(card))


class InterfaceTests(unittest.TestCase):
    def test_empty_interface_list_is_rejected(self):
        card = copy.deepcopy(GOOD_CARD)
        card["supportedInterfaces"] = []
        self.assertIn("supportedInterfaces", locations_with_errors(card))

    def test_missing_interface_subfields_are_reported(self):
        for field in ("url", "protocolBinding", "protocolVersion"):
            with self.subTest(field=field):
                card = copy.deepcopy(GOOD_CARD)
                del card["supportedInterfaces"][0][field]
                self.assertIn(f"supportedInterfaces[0].{field}", locations_with_errors(card))

    def test_unknown_binding_is_a_warning_not_error(self):
        card = copy.deepcopy(GOOD_CARD)
        card["supportedInterfaces"][0]["protocolBinding"] = "GraphQL"
        findings = validate_agent_card(card)
        errors = [f for f in findings if f.severity == "error"]
        warnings = [f for f in findings if f.severity == "warning"]
        self.assertEqual(errors, [])
        self.assertTrue(
            any(f.location == "supportedInterfaces[0].protocolBinding" for f in warnings)
        )


class SkillTests(unittest.TestCase):
    def test_missing_skill_subfields_are_reported(self):
        for field in ("id", "name", "description", "tags"):
            with self.subTest(field=field):
                card = copy.deepcopy(GOOD_CARD)
                del card["skills"][0][field]
                self.assertIn(f"skills[0].{field}", locations_with_errors(card))

    def test_tags_must_be_a_list(self):
        card = copy.deepcopy(GOOD_CARD)
        card["skills"][0]["tags"] = "test"  # string, not a list
        self.assertIn("skills[0].tags", locations_with_errors(card))


class ModeListTests(unittest.TestCase):
    def test_non_string_item_in_mode_list_is_reported(self):
        card = copy.deepcopy(GOOD_CARD)
        card["defaultInputModes"] = ["text/plain", 42]
        self.assertIn("defaultInputModes", locations_with_errors(card))


if __name__ == "__main__":
    unittest.main()
