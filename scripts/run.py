"""One-command launcher for the BexLogix offline stack + Streamlit app.

This script brings up the local Docker services (OSRM, VROOM, tiles) when
they are not already running, then launches the Streamlit UI. It is the
recommended entry point for both developers and operators so they do not
have to remember the multi-step PowerShell workflow.

Usage:
    python scripts/run.py [--no-docker] [--port 8501] [--host 127.0.0.1]

Options:
    --no-docker        Skip starting the Docker stack (use when Docker is
                       unavailable; the app falls back to NN routing).
    --port             Streamlit port (default: 8501).
    --host             Streamlit bind address (default: 127.0.0.1).
    --wait-seconds N   How long to wait for OSRM/tiles to become healthy
                       (default: 60).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = PROJECT_ROOT / "infra" / "offline" / "docker-compose.offline.yml"
OSRM_GRAPH = PROJECT_ROOT / "offline" / "osrm" / "data" / "tehran-latest.osrm"
TILE_DIR = PROJECT_ROOT / "offline" / "tiles" / "data"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-docker",
        action="store_true",
        help="Skip starting the offline Docker stack.",
    )
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--wait-seconds", type=int, default=60)
    return parser.parse_args()


def _print(label: str, message: str) -> None:
    print(f"[{label}] {message}", flush=True)


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _docker_compose_up() -> bool:
    if not COMPOSE_FILE.exists():
        _print("docker", f"compose file missing: {COMPOSE_FILE}")
        return False
    if not OSRM_GRAPH.exists():
        _print(
            "docker",
            "OSRM graph not found. Run scripts/offline_prepare_osrm_tehran.ps1 "
            f"to build it (expected at {OSRM_GRAPH}). Skipping OSRM startup.",
        )
        return False

    mb_files = sorted(TILE_DIR.glob("*.mbtiles")) if TILE_DIR.exists() else []
    if not mb_files:
        _print(
            "docker",
            f"No .mbtiles found under {TILE_DIR}; tile server will fail to "
            "render basemap.",
        )

    env = os.environ.copy()
    if mb_files:
        env["TILE_MB_FILE"] = mb_files[0].name
        _print("docker", f"Using MBTiles file: {mb_files[0].name}")

    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"]
    _print("docker", " ".join(cmd))
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        _print("docker", "docker compose up failed; continuing without it.")
        return False
    return True


def _probe_url(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return int(getattr(response, "status", 200)) < 400
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _wait_for_services(max_seconds: int) -> dict[str, bool]:
    """Poll OSRM and tile endpoints until both come up or timeout."""
    deadline = time.monotonic() + max_seconds
    last_status = {"osrm": False, "tiles": False}
    while time.monotonic() < deadline:
        last_status["osrm"] = _probe_url(
            "http://127.0.0.1:5000/nearest/v1/driving/51.4,35.7"
        )
        last_status["tiles"] = _probe_url("http://127.0.0.1:8080/styles.json")
        if all(last_status.values()):
            return last_status
        time.sleep(2)
    return last_status


def _launch_streamlit(host: str, port: int) -> int:
    streamlit_cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(PROJECT_ROOT / "client" / "streamlit_app.py"),
        "--server.address",
        host,
        "--server.port",
        str(port),
    ]
    _print("streamlit", " ".join(streamlit_cmd))
    process = subprocess.run(streamlit_cmd)
    return process.returncode


def main() -> int:
    args = _parse_args()
    if not args.no_docker and _docker_available():
        if _docker_compose_up():
            status = _wait_for_services(args.wait_seconds)
            _print(
                "health",
                f"osrm={'up' if status['osrm'] else 'down'}, "
                f"tiles={'up' if status['tiles'] else 'down'}",
            )
            if not status["osrm"]:
                _print(
                    "health",
                    "OSRM did not become ready; app will fall back to "
                    "nearest-neighbor routing.",
                )
    elif not args.no_docker:
        _print(
            "docker",
            "docker CLI not found; skipping offline stack. Install Docker "
            "Desktop or pass --no-docker to silence this message.",
        )
    return _launch_streamlit(host=args.host, port=args.port)


if __name__ == "__main__":
    raise SystemExit(main())
