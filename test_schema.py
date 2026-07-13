#!/usr/bin/env python3
"""Guards for the published JSON Schema.

These don't validate documents against the schema (that would need an external
library); they cheaply catch the schema file going missing, becoming invalid JSON,
or forgetting a pillar the Python validator supports. Run:  python3 -m unittest -v
"""

import json
import os
import unittest

import agent_self_model

_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "schema", "agent-self-model.schema.json"
)


class SchemaFileTests(unittest.TestCase):
    def setUp(self):
        with open(_SCHEMA_PATH, "r", encoding="utf-8") as handle:
            self.schema = json.load(handle)

    def test_schema_is_a_json_object(self):
        self.assertEqual(self.schema.get("type"), "object")

    def test_identity_is_required(self):
        self.assertIn("identity", self.schema.get("required", []))

    def test_every_validator_pillar_appears_in_schema(self):
        # The schema's top-level properties must cover identity + every optional
        # pillar the Python reference validator knows about, plus attestation.
        expected = {"identity", "attestation", *agent_self_model._OPTIONAL_PILLARS}
        self.assertTrue(expected.issubset(self.schema["properties"].keys()))


if __name__ == "__main__":
    unittest.main()
