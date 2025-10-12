"""Validates config/settings.json structure and required fields."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pydantic import ValidationError

from proxy.models import ProxyConfig

CONFIG_PATH = Path("config/settings.json")


def main() -> int:
    if not CONFIG_PATH.exists():
        print("config/settings.json does not exist")
        return 1
    data = json.loads(CONFIG_PATH.read_text())
    try:
        config = ProxyConfig.model_validate(data)
    except ValidationError as exc:
        print("Configuration invalid:\n")
        print(exc)
        return 1

    missing: List[str] = []
    for provider in config.providers:
        if not provider.models:
            missing.append(f"Provider {provider.name} ({provider.id}) has no model mappings")
    if missing:
        print("Warnings:")
        for item in missing:
            print(f" - {item}")
        return 1

    print("Configuration OK. Providers:")
    for provider in config.providers:
        print(f" - {provider.name} -> {len(provider.models)} mappings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
