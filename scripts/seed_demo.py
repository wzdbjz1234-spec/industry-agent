"""Seed the running API with the deterministic main Fixture Offset scenario."""

from __future__ import annotations

import argparse
import json

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, timeout=10.0) as client:
        health = client.get("/health")
        health.raise_for_status()
        seeded = client.post("/api/v1/demo/fixture-offset")
        seeded.raise_for_status()
        print(json.dumps({"health": health.json(), "seed": seeded.json()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
