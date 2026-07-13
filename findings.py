#!/usr/bin/env python3
"""Shared finding vocabulary used by every auditor check.

A `Finding` is one issue discovered during an audit. Keeping it in its own module
means the A2A protocol checks and the Agent Self-Model checks (and whatever we add
later) all speak the same language and can be collected into one report.
"""

from dataclasses import dataclass


@dataclass
class Finding:
    """One issue discovered while validating something.

    severity: "error" (breaks compliance) or "warning" (suspicious but legal).
    location: a JSON-path-ish string pointing at the offending field.
    message:  human-readable explanation.
    """

    severity: str
    location: str
    message: str
