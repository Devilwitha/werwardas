import json
from datetime import datetime
from unittest import mock

import numpy as np
import pytest
from PIL import Image, ImageDraw

from werwardas.analyzers.reference import ReferenceAnalyzer
from werwardas.config import Config
from werwardas.service import Service, in_active_hours


def room(clutter: int = 0, brightness: float = 1.0, seed: int = 1) -> Image.Image:
    """Synthetisches 'Zimmer': Wände, Bett, Schreibtisch und optional herumliegende Dinge."""
    img = Image.new("RGB", (640, 480), (200, 190, 170))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 300, 640, 480], fill=(120, 90, 60))  # Boden
    d.rectangle([40, 220, 300, 340], fill=(60, 80, 150))  # Bett
    d.rectangle([400, 200, 600, 260], fill=(90, 60, 40))  # Schreibtisch
    rng = np.random.default_rng(seed)
    for _ in range(clutter):
        x, y = int(rng.integers(0, 600)), int(rng.integers(310, 450))
        color = tuple(int(c) for c in rng.integers(0, 255, 3))
        d.ellipse([x, y, x + 40, y + 25], fill=color)
    if brightness != 1.0:
        arr = np.clip(np.asarray(img, dtype=np.float32) * brightness, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)
    return img


@pytest.fixture
def cfg_file(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        f"mqtt:\n  host: localhost\ncamera:\n  type: file\n  path: {tmp_path / 'cam.jpg'}\n"
        f"storage:\n  dir: {tmp_path / 'data'}\nactive_hours: ''\n",
        encoding="utf-8",
    )
    return path


def make_analyzer(tmp_path):
    return ReferenceAnalyzer({"sensitivity": 25, "gain": 5, "ignore_areas": []}, tmp_path / "ref")


def test_reference_without_photo_is_unknown(tmp_path):
    result = make_analyzer(tmp_path).analyze(room())
    assert result.score is None


def test_reference_tidy_vs_messy(tmp_path):
    analyzer = make_analyzer(tmp_path)
    analyzer.add_reference(room())
    tidy = analyzer.analyze(room())
    darker = analyzer.analyze(room(brightness=0.75))
    messy = analyzer.analyze(room(clutter=40))
    assert tidy.score >= 95
    assert darker.score >= 80, "Lichtänderung darf nicht als Unordnung zählen"
    assert messy.score < 60
    assert messy.score < darker.score


def test_reference_keeps_latest_five(tmp_path):
    analyzer = make_analyzer(tmp_path)
    for i in range(7):
        with mock.patch("time.time", return_value=1000 + i):
            analyzer.add_reference(room())
    assert len(analyzer.references()) == 5


def test_ignore_area(tmp_path):
    analyzer = ReferenceAnalyzer(
        {"sensitivity": 25, "gain": 5, "ignore_areas": [[0, 60, 100, 40]]}, tmp_path / "ref"
    )
    analyzer.add_reference(room())
    assert analyzer.analyze(room(clutter=40)).score >= 90


@pytest.mark.parametrize(
    "spec,hour,expected",
    [
        ("08:00-22:00", 12, True),
        ("08:00-22:00", 23, False),
        ("20:00-02:00", 1, True),
        ("20:00-02:00", 12, False),
        ("", 3, True),
    ],
)
def test_active_hours(spec, hour, expected):
    assert in_active_hours(spec, datetime(2026, 1, 1, hour, 0)) is expected


def test_runtime_settings_persist(cfg_file):
    cfg = Config(cfg_file)
    cfg.set_runtime("threshold", 75)
    assert Config(cfg_file)["threshold"] == 75


def published(client, topic):
    return [json.loads(c.args[1]) for c in client.publish.call_args_list if c.args[0] == topic]


def test_service_check_publishes_state(cfg_file, tmp_path):
    cfg = Config(cfg_file)
    service = Service(cfg)
    service.client = mock.MagicMock()

    room().save(tmp_path / "cam.jpg")
    service.save_reference()
    room(clutter=40).save(tmp_path / "cam.jpg")
    state = service.check("test")
    assert state["tidy"] is False and state["score"] < 60

    room().save(tmp_path / "cam.jpg")
    state = service.check("pc")
    assert state["tidy"] is True
    assert published(service.client, "werwardas/cam/state")[-1]["trigger"] == "pc"


def test_service_paused_is_tidy(cfg_file):
    cfg = Config(cfg_file)
    cfg.set_runtime("active", False)
    service = Service(cfg)
    service.client = mock.MagicMock()
    state = service.check("interval")
    assert state["tidy"] is True and state["paused"] is True


def test_camera_error_fails_open(cfg_file):
    service = Service(Config(cfg_file))  # cam.jpg existiert nicht
    service.client = mock.MagicMock()
    state = service.check("interval")
    assert state["error"] is True and state["tidy"] is None


def test_discovery(cfg_file):
    service = Service(Config(cfg_file))
    service.client = mock.MagicMock()
    service._publish_discovery()
    topics = [c.args[0] for c in service.client.publish.call_args_list]
    assert any(t.startswith("homeassistant/binary_sensor/") and t.endswith("/messy/config") for t in topics)
    assert any(t.startswith("homeassistant/camera/") for t in topics)


def test_ollama_parses_json():
    from werwardas.analyzers.ollama import OllamaAnalyzer

    response = mock.Mock()
    response.json.return_value = {"message": {"content": '{"score": 42, "reason": "Kleidung auf dem Boden."}'}}
    with mock.patch("requests.post", return_value=response) as post:
        result = OllamaAnalyzer({"url": "http://x:11434", "model": "m", "timeout_seconds": 5}, "").analyze(room())
    assert (result.score, result.reason) == (42, "Kleidung auf dem Boden.")
    assert post.call_args.kwargs["json"]["messages"][0]["images"]
