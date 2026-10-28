"""Konfiguration laden (YAML) und zur Laufzeit geänderte Werte (aus Home Assistant) speichern."""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

DEFAULTS: dict = {
    "mqtt": {
        "host": "homeassistant.local",
        "port": 1883,
        "username": "",
        "password": "",
        "topic_prefix": "werwardas",
        "discovery_prefix": "homeassistant",
    },
    "camera": {
        # auto | picamera2 | usb | http | file
        "type": "auto",
        "width": 1920,
        "height": 1080,
        "rotation": 0,
        "usb_index": 0,
        "url": "",  # für type=http, z. B. ESP32-CAM: http://192.168.1.50/capture
        "path": "",  # für type=file (Tests)
        "warmup_seconds": 2,
    },
    "interval_minutes": 30,
    "active_hours": "08:00-22:00",
    "threshold": 60,
    "active": True,
    # reference | ollama | claude
    "analyzer": "reference",
    "prompt_hint": "",
    "reference": {
        "sensitivity": 25,
        "gain": 5,
        "ignore_areas": [],  # Liste von [x, y, breite, hoehe] in Prozent
    },
    "ollama": {
        "url": "http://localhost:11434",
        "model": "qwen2.5vl:7b",
        "timeout_seconds": 600,
    },
    "claude": {
        "api_key": "",
        "model": "claude-opus-5-5",
    },
    "storage": {
        "dir": "/var/lib/werwardas",
        "keep_days": 7,
    },
}

# Diese Werte können aus Home Assistant geändert werden und überleben einen Neustart.
RUNTIME_KEYS = ("interval_minutes", "threshold", "active", "analyzer")


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


class Config:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        with open(self.path, encoding="utf-8") as fh:
            user = yaml.safe_load(fh) or {}
        self.data = _merge(DEFAULTS, user)
        self.storage_dir = Path(self.data["storage"]["dir"])
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._runtime_file = self.storage_dir / "runtime.json"
        self._load_runtime()

    def __getitem__(self, key):
        return self.data[key]

    def _load_runtime(self) -> None:
        if not self._runtime_file.exists():
            return
        try:
            saved = json.loads(self._runtime_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("runtime.json nicht lesbar: %s", exc)
            return
        for key in RUNTIME_KEYS:
            if key in saved:
                self.data[key] = saved[key]

    def set_runtime(self, key: str, value) -> None:
        if key not in RUNTIME_KEYS:
            raise KeyError(key)
        self.data[key] = value
        saved = {k: self.data[k] for k in RUNTIME_KEYS}
        self._runtime_file.write_text(json.dumps(saved, indent=2), encoding="utf-8")
