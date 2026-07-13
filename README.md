# Agent Auditor

Audits AI agents on two axes:

1. **A2A protocol compliance** — does the agent obey the [Agent2Agent](https://a2a-protocol.org)
   protocol (v1.0)?
2. **Agent Self-Model conformance** — does the agent expose a bounded, inspectable,
   honest self-model (identity, capabilities, permissions, constraints, state,
   confidence, dependencies, escalation boundaries, assurance, provenance)?

The Agent Self-Model is specified in **[SPEC.md](SPEC.md)**, with a machine-readable
**[JSON Schema](schema/agent-self-model.schema.json)**.

## Status

Early, built in thin slices:

- ✅ **A2A Agent Card validation** — fetch a card and check its v1.0 required fields.
- ✅ **Agent Self-Model** — all ten pillars: **Identity & Ownership**,
  **Capabilities**, **Permissions & Authority**, **Constraints & Policy**,
  **Dependencies**, **Escalation Boundaries**, **Operational State**,
  **Confidence & Evidence**, **Assurance & Attestation**, **Provenance & Lifecycle**.
- ✅ **Unified audit + honesty checks** — one command audits the card *and* the
  self-model and cross-checks them:
  - *card vs. self-model:* `displayName` vs card `name`; declared capabilities vs
    card skills; acting authority vs whether the card exposes `securitySchemes`.
  - *self-model internal consistency:* sensitive data vs assurance tier; declared
    `modelVersion` vs the declared model dependencies.
- ✅ **Verification envelope** (`attestation`: `assertedBy / assertedAt / validUntil`
  + optional `signature`) — structure validation, an *unattested* warning, and a
  **freshness check** (expired `validUntil` → flagged). This is what powers
  "overdue for review" / lapsed-attestation alerts.

### Scope decision: signature verification (considered, not included — by choice)

The `attestation.signature`'s **shape** is validated, but its cryptography is **not
verified**. This is a deliberate scoping choice, not an oversight. Verifying a
signature would require an external crypto library and key management, which cuts
against this project's standard-library-first stance and mainly pays off when
auditing *third-party* agents you don't control.

It was considered and may be worth adding in the future (e.g. if the auditor is
pointed at untrusted third-party agents at scale). For now, a signed self-model is
treated as *attested* but not cryptographically *proven*.

## Project layout

| File | What it is |
|---|---|
| `audit.py` | **The command.** Loads card + self-model, validates both, cross-checks, reports |
| `agent_auditor.py` | A2A v1.0 Agent Card validation (library) |
| `agent_self_model.py` | Agent Self-Model validator (pillar by pillar) |
| `fetch.py` | Loads a JSON doc from a file, a URL, or a base URL's well-known path |
| `findings.py` | The shared `Finding` type every check reports in |
| `test_*.py` | Standard-library `unittest` suites |
| `examples/` | Valid + deliberately-broken sample cards and self-models |

## Requirements

Python 3.10+ — standard library only, nothing to install.

## Usage

```bash
# Against a running agent: fetches /.well-known/agent-card.json AND
# /.well-known/agent-self-model.json (the self-model is optional):
python3 audit.py https://some-agent.example.com

# Against local files (handy for testing):
python3 audit.py examples/valid-card.json --self-model examples/valid-self-model.json

# Card only (no self-model) is fine too:
python3 audit.py examples/valid-card.json
```

Exit code is `0` on pass, `1` on compliance errors, `2` on fetch/parse failure —
so it can drop straight into CI later.

### Try it

```bash
# Both valid -> OVERALL PASS:
python3 audit.py examples/valid-card.json --self-model examples/valid-self-model.json

# Both broken -> per-field findings across both sections, OVERALL FAIL:
python3 audit.py examples/broken-card.json --self-model examples/broken-self-model.json
```

## Tests

```bash
python3 -m unittest -v
```

Standard-library `unittest` — no install. Each A2A rule is tested in isolation,
so a future change can't silently disable a check.

## What it checks so far

**A2A Agent Card (v1.0):** required fields `name`, `description`, `version`,
`supportedInterfaces[]` (each needs `url`, `protocolBinding`, `protocolVersion`),
`capabilities`, `defaultInputModes`, `defaultOutputModes`, `skills[]` (each needs
`id`, `name`, `description`, `tags`). Unknown transport bindings are flagged as
warnings.

**Agent Self-Model** (each pillar fills a gap A2A leaves open):
- *Identity & Ownership* — `agentId`, optional `displayName`, and an `owner`
  (`name`, `organization`, `contact`, optional `role`).
- *Capabilities* — `declared[]`, each referencing a card `skillId` with a required
  `maturity`, plus optional `proficiency`, `tested`, `knownLimits`, `failureModes`.
- *Permissions & Authority* — `authorityLevel` (read-only / act-with-approval /
  autonomous), optional allowed/prohibited actions, `requiresAuthentication`,
  `spendingLimit`. (A2A only covers authentication, never authorization.)
- *Constraints & Policy* — `dataSensitivity`, optional `dataResidency`,
  `rateLimitPerMinute`, `policyRefs`, `jurisdictions`.
- *Dependencies* — `declared[]` upstream models/agents/tools/services (blast radius).
- *Escalation Boundaries* — `triggers`, a handoff `target`, optional `fallbackBehavior`.
- *Operational State* — declared `status`, `availability`, `degradationPolicy`.
- *Confidence & Evidence* — `calibration`, `reportsConfidence`, `evidenceProvided`,
  `knownBiases`, `evaluationRefs`.
- *Assurance & Attestation* — `securityTier`, `certifications`, `dataClasses`,
  `lastPenTest`, `sandboxed`.
- *Provenance & Lifecycle* — `lastUpdated`, `lifecycleStage`, `modelVersion`,
  `reviewBy`, `supersededBy`.

**Cross-checks — card vs. self-model (declared vs. observed):**
- self-model `displayName` vs card `name`;
- each declared capability's `skillId` vs the card's actual skills;
- acting authority vs whether the card exposes `securitySchemes`.

**Cross-checks — self-model internal consistency:**
- `confidential`/`restricted` data vs an adequate `securityTier`;
- declared `modelVersion` vs the declared model dependencies.

**Verification envelope (`attestation`):** required `assertedBy`, `assertedAt`,
`validUntil`; optional `signature` (`algorithm`, `value`). Non-ISO dates warn; an
absent envelope warns ("unattested"); an expired `validUntil` is flagged. Signature
crypto verification is **not yet implemented** (see limitation above).

> Note: targets A2A **v1.0** (Linux Foundation). Legacy v0.2/0.3 shapes
> (`/.well-known/agent.json`, top-level `url`, `message/send`-style methods) are
> intentionally not treated as valid.
