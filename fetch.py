#!/usr/bin/env python3
"""Loading Agent Cards and Self-Model documents — from a URL or a local file.

Shared by every check so the "is this a file, a direct URL, or a base URL?"
logic lives in exactly one place.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


def load_json(source: str, well_known_path: str, timeout: float = 10.0) -> dict[str, Any]:
    """Load a JSON document from a local file, a direct URL, or a base URL.

    - an existing local file path            -> read it (great for testing/offline)
    - a URL ending in .json                  -> fetch it directly
    - a base URL like https://example.com    -> append `well_known_path` and fetch
    """
    if os.path.isfile(source):
        with open(source, "r", encoding="utf-8") as handle:
            return json.load(handle)

    url = source if source.endswith(".json") else source.rstrip("/") + well_known_path
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "agent-auditor/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())
