# Agent Self-Model — Specification

**Version:** 0.1 (Draft) · **Status:** Proposal, seeking feedback · **License:** see `LICENSE`

The Agent Self-Model is a bounded, inspectable, honest self-description that an AI
agent publishes **on top of** its [A2A](https://a2a-protocol.org) Agent Card. If the
A2A Agent Card is a *business card*, the Self-Model is the *due-diligence dossier*.

This document is the human-readable specification. The machine-readable schema is
[`schema/agent-self-model.schema.json`](schema/agent-self-model.schema.json) (JSON
Schema, draft 2020-12). The **reference implementation** is the validator in this
repository (`agent_self_model.py` + `audit.py`); where the two differ, the reference
implementation is authoritative and is stricter (it rejects whitespace-only strings
and performs cross-pillar consistency checks the plain schema cannot express).

## 1. Conformance language

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are to
be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

## 2. Motivation

A2A standardizes how agents *communicate*, and its Agent Card describes an agent's
identity, skills, and authentication. But A2A is deliberately thin on
*self-description* for governance. It has no normative place to state **who is
accountable**, **what the agent is authorized to do**, **its constraints**, **its
runtime state**, **its confidence**, **its dependencies**, or **its escalation
boundaries**. The Self-Model fills those gaps so an agent can be *safely trusted*,
not merely reached.

Of the ten pillars below, only Identity and Capabilities overlap the Agent Card at
all — and there the Self-Model **MUST** reference the card rather than restate it.
The other eight are net-new.

## 3. Delivery

An agent MAY publish its Self-Model in either of two ways:

- **Delivery A — A2A extension (preferred for A2A agents).** Declare an extension in
  the Agent Card's `capabilities.extensions[]` with `uri` set to the Self-Model
  extension URI (see §4), and carry the Self-Model document under
  `metadata[<extension-uri>]`. Activation follows A2A's `A2A-Extensions` header
  mechanism.
- **Delivery B — standalone document (for non-A2A agents).** Serve the Self-Model
  document as JSON at `GET /.well-known/agent-self-model.json`.

An auditor SHOULD treat Delivery A as canonical when both are present.

## 4. Extension URI & versioning

The extension is identified by a stable URI:
`https://supercool83.github.io/Agent-Auditor/ext/v0.1`. Another party publishing an
independent deployment MUST use a URI they control. The document's `selfModelVersion`
field carries the schema version (`"0.1"`). Compatibility is negotiated on the
major.minor version.

## 5. Document overview

A Self-Model is a JSON object. `identity` is **REQUIRED**; every other pillar and the
`attestation` envelope are **OPTIONAL** in v0.1 but **RECOMMENDED**. Unknown fields
are permitted (the model is extensible). An auditor **SHOULD** warn when the
`attestation` envelope is absent ("unattested").

## 6. Pillars

Each table lists the pillar's fields. "Req" = REQUIRED when the pillar is present.

### 6.1 Identity & Ownership — *"who is this, and who is accountable?"*
| Field | Req | Type | Notes |
|---|---|---|---|
| `agentId` | ✔ | string | Stable, globally-unique id. A2A has no equivalent. |
| `displayName` | | string | SHOULD equal the A2A card's `name`. |
| `owner` | ✔ | object | `name`✔, `organization`✔, `contact`✔ (email/URL), `role`. The accountability chain A2A omits. |

### 6.2 Capabilities — *"what can it do, how well, under what limits?"*
References card skills; MUST NOT restate the catalog.
| Field | Req | Type | Notes |
|---|---|---|---|
| `declared[]` | ✔ | array | Each: `skillId`✔ (references a card `skills[].id`), `maturity`✔ (`experimental`\|`beta`\|`stable`\|`deprecated`), `proficiency` (`low`\|`medium`\|`high`), `tested` (bool), `knownLimits[]`, `failureModes[]`. |

### 6.3 Permissions & Authority — *"what is it ALLOWED to do?"*
Authorization, which A2A (authentication-only) does not cover.
| Field | Req | Type | Notes |
|---|---|---|---|
| `authorityLevel` | ✔ | enum | `read-only` \| `act-with-approval` \| `autonomous`. |
| `allowedActions[]` / `prohibitedActions[]` | | string[] | |
| `requiresAuthentication` | | bool | |
| `spendingLimit` | | object | `currency`✔, `maxPerAction`✔ (number ≥ 0). |

### 6.4 Constraints & Policy — *"what limits/policy does it run under?"*
| Field | Req | Type | Notes |
|---|---|---|---|
| `dataSensitivity` | ✔ | enum | `public` \| `internal` \| `confidential` \| `restricted`. |
| `dataResidency` | | string | e.g. `"EU"`. |
| `rateLimitPerMinute` | | number ≥ 0 | |
| `policyRefs[]` / `jurisdictions[]` | | string[] | |

### 6.5 Dependencies — *"what does it rely on? blast radius?"*
| Field | Req | Type | Notes |
|---|---|---|---|
| `declared[]` | ✔ | array | Each: `type`✔ (`model`\|`agent`\|`tool`\|`service`), `name`✔, `provider`, `critical` (bool). |

### 6.6 Escalation Boundaries — *"when, and to whom, does it hand off?"*
| Field | Req | Type | Notes |
|---|---|---|---|
| `triggers` | ✔ | string[] | Non-empty. |
| `target` | ✔ | object | `type`✔ (`human`\|`agent`\|`queue`), `contact`✔. |
| `fallbackBehavior` | | enum | `halt` \| `defer` \| `handoff`. |

### 6.7 Operational State — *"is it healthy enough to use now?"* (declared envelope)
| Field | Req | Type | Notes |
|---|---|---|---|
| `status` | ✔ | enum | `operational` \| `degraded` \| `maintenance` \| `offline`. |
| `availability` | | object | `schedule`, `timezone`. |
| `degradationPolicy` | | enum | `graceful` \| `fail-closed` \| `fail-open`. |
| `lastStatusChange` | | string | ISO-8601. |

> This is the *declared* envelope. *Observed* state is measured by an auditor at
> runtime and is out of scope for the document itself.

### 6.8 Confidence & Evidence — *"should I believe its output?"*
| Field | Req | Type | Notes |
|---|---|---|---|
| `calibration` | ✔ | enum | `calibrated` \| `uncalibrated` \| `unknown`. |
| `reportsConfidence` / `evidenceProvided` | | bool | |
| `knownBiases[]` / `evaluationRefs[]` | | string[] | |

### 6.9 Assurance & Attestation — *"is it vetted enough for regulated data?"*
| Field | Req | Type | Notes |
|---|---|---|---|
| `securityTier` | ✔ | enum | `none` \| `standard` \| `high` \| `critical`. |
| `certifications[]` / `dataClasses[]` | | string[] | e.g. `SOC2`; `PII`/`PHI`. |
| `lastPenTest` | | string | ISO-8601. |
| `sandboxed` | | bool | |

### 6.10 Provenance & Lifecycle — *"is it stale/EOL — migrate off?"*
| Field | Req | Type | Notes |
|---|---|---|---|
| `lastUpdated` | ✔ | string | ISO-8601. Staleness detection depends on it. |
| `lifecycleStage` | ✔ | enum | `active` \| `maintenance` \| `deprecated` \| `retired`. |
| `createdAt` / `modelVersion` / `reviewBy` / `supersededBy` | | string | |

## 7. Verification envelope (`attestation`)

The envelope wraps the document so claims are trustable, not merely stated.
| Field | Req | Type | Notes |
|---|---|---|---|
| `assertedBy` | ✔ | string | Who asserts these claims. |
| `assertedAt` | ✔ | string | ISO-8601; non-ISO SHOULD warn. |
| `validUntil` | ✔ | string | ISO-8601. A date in the past MUST be flagged (expired). |
| `signature` | | object | `algorithm`✔, `value`✔. See §9. |

An auditor **MUST** flag an `attestation` whose `validUntil` has passed, and
**SHOULD** flag a document with no `attestation` at all.

## 8. Consistency & honesty requirements

The Self-Model is self-asserted, so an auditor SHOULD hold it against observable
reality and against itself:

**Against the A2A card:**
- `identity.displayName` SHOULD equal the card's `name`.
- every `capabilities.declared[].skillId` SHOULD exist in the card's `skills[]`.
- an agent whose `authorityLevel` permits acting SHOULD have `securitySchemes` on
  its card.

**Internal consistency:**
- `confidential`/`restricted` `dataSensitivity` SHOULD carry an adequate
  `securityTier` (not `none`/`standard`).
- a declared `provenance.modelVersion` SHOULD appear among the model `dependencies`.

## 9. Signature verification (out of scope in v0.1, by choice)

The `signature`'s **structure** is validated, but its cryptography is **not
verified** in this version. Cryptographic verification requires a signing/key
infrastructure and mainly benefits auditing of *untrusted third-party* agents; it is
a candidate for a future version, not a current requirement. A signed Self-Model is
therefore treated as *attested* but not cryptographically *proven*.

## 10. Conformance

An implementation conforms if a Self-Model document it produces validates against the
JSON Schema and passes the reference validator (`python3 audit.py <agent>`). The test
suite (`python3 -m unittest`) exercises every rule in this specification.

## 11. Changelog

- **0.1** — Initial draft: ten pillars, verification envelope (structure + freshness),
  card cross-checks and internal-consistency checks. Signature crypto out of scope.
