import copy
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "server": {
        "host": "0.0.0.0",
        "callback_port": 8100,
        "order_port": 9100,
    },
    "mysql": {
        "host": "localhost",
        "port": 3306,
        "user": "qwire",
        "password": "Qwire2026",
        "database": "qwire",
        "charset": "utf8mb4",
    },
    "order": {
        "poll_interval_seconds": 5,
        "callback_skip_amount_gte": 1000,
    },
    "logging": {
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "order_log": "order.log",
        "callback_log": "callback.log",
    },
}


def _deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _config_path() -> Path:
    value = os.environ.get("QWIRE_CONFIG_FILE")
    if value:
        return Path(value)
    return Path(__file__).resolve().parents[2] / "config.yaml"


def _apply_env_overrides(config: dict[str, Any]) -> None:
    if os.environ.get("QWIRE_HOST"):
        config["server"]["host"] = os.environ["QWIRE_HOST"]
    if os.environ.get("QWIRE_CALLBACK_PORT"):
        config["server"]["callback_port"] = int(os.environ["QWIRE_CALLBACK_PORT"])
    if os.environ.get("QWIRE_ORDER_PORT"):
        config["server"]["order_port"] = int(os.environ["QWIRE_ORDER_PORT"])

    if os.environ.get("QWIRE_MYSQL_HOST"):
        config["mysql"]["host"] = os.environ["QWIRE_MYSQL_HOST"]
    if os.environ.get("QWIRE_MYSQL_PORT"):
        config["mysql"]["port"] = int(os.environ["QWIRE_MYSQL_PORT"])
    if os.environ.get("QWIRE_MYSQL_USER"):
        config["mysql"]["user"] = os.environ["QWIRE_MYSQL_USER"]
    if os.environ.get("QWIRE_MYSQL_PASSWORD"):
        config["mysql"]["password"] = os.environ["QWIRE_MYSQL_PASSWORD"]
    if os.environ.get("QWIRE_MYSQL_DATABASE"):
        config["mysql"]["database"] = os.environ["QWIRE_MYSQL_DATABASE"]

    if os.environ.get("QWIRE_V2_POLL_INTERVAL_SECONDS"):
        config["order"]["poll_interval_seconds"] = int(os.environ["QWIRE_V2_POLL_INTERVAL_SECONDS"])
    if os.environ.get("QWIRE_V2_CALLBACK_SKIP_AMOUNT_GTE"):
        config["order"]["callback_skip_amount_gte"] = float(os.environ["QWIRE_V2_CALLBACK_SKIP_AMOUNT_GTE"])

    if os.environ.get("QWIRE_V2_ORDER_LOG"):
        config["logging"]["order_log"] = os.environ["QWIRE_V2_ORDER_LOG"]
    if os.environ.get("QWIRE_V2_CALLBACK_LOG"):
        config["logging"]["callback_log"] = os.environ["QWIRE_V2_CALLBACK_LOG"]


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    config = copy.deepcopy(DEFAULT_CONFIG)
    path = _config_path()

    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Invalid YAML root in {path}: expected mapping")
        _deep_merge(config, data)

    _apply_env_overrides(config)
    return config


def reload_config() -> dict[str, Any]:
    load_config.cache_clear()
    return load_config()
