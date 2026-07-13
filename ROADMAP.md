# Roadmap

Agent Auditor v0.1 is a complete reference implementation of the Agent Self-Model
concept (see [SPEC.md](SPEC.md)). Directions from here, roughly in priority order.

## Product framing (the "why")

The concept is designed to serve three modes, all riding the same self-model:

- **Onboarding gate** — audit an agent before it joins a mesh/fleet.
- **Continuous governance / SecOps monitor** — watch a live fleet and alert on drift,
  breaches, stale attestations, and end-of-life.
- **Governance learning module** — the pillars double as a curriculum; each finding is
  a teachable failure mode.

The core value is the **delta between what an agent *declares* and what is *observed***.

## Near-term

- **Run against real A2A agents** — exercise the fetch/validate path on live agents and
  handle real-world messiness (mixed versions, partial cards, auth).
- **Enable GitHub Pages** so the spec/schema URIs resolve in a browser.
- **More declared-vs-observed cross-checks** — extend the honesty audit.

## Medium-term

- **Delivery A end-to-end** — read the self-model from inside the A2A card's
  `capabilities.extensions` (today the standalone well-known document is primary).
- **Non-A2A adapter** — synthesize a partial self-model for agents that don't emit one
  (LangChain, MCP-only, vendor black boxes), so "any platform" is real.

## Larger

- **Continuous monitor mode** — a store + scheduler that watches a fleet and fires
  alerts on drift, constraint breaches, expired attestations, and EOL.
- **Signature verification** — cryptographic verification of the attestation signature.
  Deliberately out of scope in v0.1 (see [docs/decisions.md](docs/decisions.md), D4).
