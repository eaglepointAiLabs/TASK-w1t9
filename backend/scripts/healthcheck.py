from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


HEALTHCHECK_URL = os.getenv("HEALTHCHECK_URL", "http://127.0.0.1:5000/healthz")


def main() -> int:
    try:
        with urlopen(HEALTHCHECK_URL, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if response.status != 200 or payload.get("code") != "ok":
                print(f"Healthcheck failed: {payload}", file=sys.stderr)
                return 1
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        print(f"Healthcheck request failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
