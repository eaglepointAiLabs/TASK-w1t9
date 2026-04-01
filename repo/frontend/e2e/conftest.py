from __future__ import annotations

import os
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import pytest

DEFAULT_BASE_URL = "http://127.0.0.1:9100"


def _normalize_base_url(value: str) -> str:
    return value.rstrip("/")


@pytest.fixture(scope="session")
def base_url() -> str:
    return _normalize_base_url(os.getenv("TABLEPAY_E2E_BASE_URL", DEFAULT_BASE_URL))


@pytest.fixture(scope="session", autouse=True)
def ensure_live_runtime(base_url: str):
    health_url = f"{base_url}/healthz"
    try:
        with urlopen(health_url, timeout=5) as response:
            if response.status != 200:
                pytest.skip(f"Live runtime is unavailable at {health_url} (status={response.status}).")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        pytest.skip(f"Live runtime is unavailable at {health_url}: {exc}")
