import asyncio
import json
from pathlib import Path

import pytest

from proxy.config_manager import SettingsManager


@pytest.mark.asyncio
async def test_stage_and_apply(tmp_path: Path):
    config_path = tmp_path / "settings.json"
    manager = SettingsManager(config_path)
    await manager.startup()

    payload = {
        "providers": [
            {
                "id": "p1",
                "name": "OpenAI",
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-test",
                "models": [
                    {"proxy_name": "claude-sonnet", "upstream_name": "gpt-4.1"}
                ],
            }
        ]
    }

    staged = await manager.stage(payload)
    assert staged.needs_restart is True
    assert json.loads(config_path.read_text())["providers"][0]["api_key"] == "sk-test"

    applied = await manager.apply()
    assert applied.needs_restart is False
    active = await manager.get_active()
    assert active.providers[0].models[0].proxy_name == "claude-sonnet"
