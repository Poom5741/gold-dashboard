"""Configuration loading. bias.yaml is the single source of weights/thresholds (SPEC §5)."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "bias.yaml"


def load_config(path: str | Path | None = None) -> dict:
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(p, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["_path"] = str(p)
    cfg["_hash"] = config_hash(cfg)
    return cfg


def config_hash(cfg: dict) -> str:
    import json

    payload = {k: v for k, v in cfg.items() if not k.startswith("_")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class Settings:
    """Environment settings (12-factor; nothing secret is committed)."""

    def __init__(self, env: dict | None = None):
        env = dict(env if env is not None else os.environ)
        self.db_path = env.get("GOLD_DB_PATH", "data/gold.db")
        self.port = int(env.get("GOLD_PORT", "8600"))
        # REQUIRED for pulling a private data branch (D10); empty in tests/mocks.
        self.github_data_token = env.get("GITHUB_DATA_TOKEN", "")
        self.github_data_repo = env.get("GITHUB_DATA_REPO", "Poom5741/gold-dashboard")
        self.github_data_branch = env.get("GITHUB_DATA_BRANCH", "data")
        self.cme_accept_mock = env.get("CME_ACCEPT_MOCK", "false").lower() == "true"
        self.scheduler_enabled = env.get("GOLD_SCHEDULER", "true").lower() == "true"

    @property
    def cme_raw_base(self) -> str:
        return (
            f"https://raw.githubusercontent.com/{self.github_data_repo}/"
            f"{self.github_data_branch}"
        )


def get_settings() -> Settings:
    return Settings()
