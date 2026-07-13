# Design decisions

Lightweight records of key choices and their rationale (ADR-style).

## D1 — The Self-Model *augments* A2A; it does not replace it

Only Identity and Capabilities overlap the A2A Agent Card, and there the Self-Model
**references** card fields rather than restating them. The other eight pillars fill
governance gaps A2A leaves open (authority, constraints, state, confidence,
dependencies, escalation, assurance, provenance).
**Why:** adoptability — build on A2A's extension mechanism instead of competing with it.

## D2 — Standard library only (no dependencies)

The validator and CLI use only the Python standard library.
**Why:** portability, zero install friction, and a deliberate high bar for adding any
dependency.

## D3 — The Python validator is the reference implementation

Where the hand-written validator and the JSON Schema differ, the validator is
authoritative (it is stricter and performs cross-pillar consistency checks the schema
cannot express). The JSON Schema is the machine-readable companion.
**Why:** richer, per-field diagnostics and checks that plain JSON Schema can't encode.

## D4 — Signature cryptography is out of scope in v0.1 (by choice)

The attestation `signature`'s shape is validated but **not** cryptographically verified.
**Why:** verification needs a crypto library + key management and mainly benefits
auditing of *untrusted third-party* agents. It was considered and may be added later
when that need is concrete; until then a signed self-model is *attested* but not *proven*.

## D5 — Only `identity` is required; other pillars are optional for now

**Why:** keeps early adoption low-friction. Which pillars become mandatory is a decision
for a later schema version, once the full set has been exercised in practice.

## D6 — Licence: Apache-2.0

Chosen over MIT for its explicit patent grant.
**Why:** the patent grant reassures organisations adopting the Self-Model as a standard,
and it matches the licensing of the A2A ecosystem this builds on.
