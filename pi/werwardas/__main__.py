"""Kommandozeile:  python -m werwardas [-c config.yaml] [--test-camera DATEI | --once]"""

from __future__ import annotations

import argparse
import logging
import signal
import sys

from . import __version__, analyzers
from .camera import Camera, CameraError
from .config import Config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="werwardas", description="Aufräum-Wächter")
    parser.add_argument("-c", "--config", default="/etc/werwardas/config.yaml")
    parser.add_argument("--test-camera", metavar="DATEI", help="Ein Foto aufnehmen, speichern und beenden")
    parser.add_argument("--once", action="store_true", help="Einmal Foto + Bewertung ausgeben (ohne MQTT)")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    cfg = Config(args.config)

    if args.test_camera:
        try:
            Camera(cfg["camera"]).capture().save(args.test_camera, quality=90)
        except CameraError as exc:
            print(f"FEHLER: {exc}", file=sys.stderr)
            return 1
        print(f"Foto gespeichert: {args.test_camera}")
        return 0

    if args.once:
        try:
            img = Camera(cfg["camera"]).capture()
            result = analyzers.create(cfg["analyzer"], cfg.data, cfg.storage_dir).analyze(img)
        except (CameraError, analyzers.AnalyzerError) as exc:
            print(f"FEHLER: {exc}", file=sys.stderr)
            return 1
        print(f"Bewertung ({result.analyzer}): {result.score} – {result.reason}")
        return 0

    from .service import Service

    service = Service(cfg)
    signal.signal(signal.SIGTERM, lambda *_: service.stop())
    signal.signal(signal.SIGINT, lambda *_: service.stop())
    service.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
