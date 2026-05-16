"""Bring the local Docker stack (OSRM + tiles + VROOM) up from inside the
Streamlit app.

The legacy workflow asked operators to drop to PowerShell and run
``scripts\\offline_up.ps1`` before launching the UI. That worked but was
error-prone. This service wraps the same idea in a single function so the
manager dashboard can recover from "OSRM DOWN" without leaving the page.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = PROJECT_ROOT / "infra" / "offline" / "docker-compose.offline.yml"
OSRM_GRAPH = PROJECT_ROOT / "offline" / "osrm" / "data" / "tehran-latest.osrm"
TILE_DIR = PROJECT_ROOT / "offline" / "tiles" / "data"


def is_docker_available() -> bool:
    """Return True only if the docker CLI is present on PATH."""
    return shutil.which("docker") is not None


def describe_prerequisites() -> dict:
    """Inspect filesystem prerequisites without running any commands."""
    mb_files = sorted(TILE_DIR.glob("*.mbtiles")) if TILE_DIR.exists() else []
    return {
        "docker_available": is_docker_available(),
        "compose_file_exists": COMPOSE_FILE.exists(),
        "osrm_graph_ready": OSRM_GRAPH.exists(),
        "mbtiles_count": len(mb_files),
        "mbtiles_first": mb_files[0].name if mb_files else None,
    }


def bring_up_offline_stack(timeout_seconds: float = 90.0) -> dict:
    """Run ``docker compose up -d`` for the offline stack.

    Returns a structured result that the UI can render. Never raises; on any
    failure the operator gets a status string they can act on.
    """
    info = describe_prerequisites()
    if not info["docker_available"]:
        return {
            "ok": False,
            "stage": "preflight",
            "reason": "docker_cli_missing",
            "message": (
                "Docker CLI پیدا نشد. Docker Desktop را نصب و آن را اجرا کنید."
            ),
        }
    if not info["compose_file_exists"]:
        return {
            "ok": False,
            "stage": "preflight",
            "reason": "compose_file_missing",
            "message": f"فایل compose پیدا نشد: {COMPOSE_FILE}",
        }
    if not info["osrm_graph_ready"]:
        return {
            "ok": False,
            "stage": "preflight",
            "reason": "osrm_graph_missing",
            "message": (
                "گراف OSRM آماده نیست. ابتدا اسکریپت "
                "scripts/offline_prepare_osrm_tehran.ps1 را اجرا کنید."
            ),
        }

    env = os.environ.copy()
    if info["mbtiles_first"]:
        env["TILE_MB_FILE"] = info["mbtiles_first"]

    try:
        completed = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return {
            "ok": False,
            "stage": "compose_up",
            "reason": "docker_not_callable",
            "message": "اجرای docker compose ممکن نشد.",
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "stage": "compose_up",
            "reason": "compose_up_timeout",
            "message": (
                f"docker compose up در {int(timeout_seconds)} ثانیه پاسخ نداد."
            ),
        }

    if completed.returncode != 0:
        return {
            "ok": False,
            "stage": "compose_up",
            "reason": "compose_up_failed",
            "message": (
                completed.stderr.strip()
                or completed.stdout.strip()
                or "docker compose up با خطا برگشت."
            ),
        }

    return {
        "ok": True,
        "stage": "compose_up",
        "reason": None,
        "message": "سرویس‌های آفلاین در حال راه‌اندازی هستند. "
                   "چند ثانیه صبر کنید تا health-check سبز شود.",
        "tile_mb_file": info["mbtiles_first"],
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def _probe(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return int(getattr(response, "status", 200)) < 400
    except (urllib.error.URLError, OSError, ValueError):
        return False


def wait_for_services(max_seconds: int = 30) -> dict:
    """Poll OSRM and tile endpoints until both are healthy or timeout.

    Returns the final status plus how long it actually took. Useful as the
    follow-up of bring_up_offline_stack so the operator knows whether the
    services finished starting before any further action is taken.
    """
    osrm_url = "http://127.0.0.1:5000/nearest/v1/driving/51.4,35.7"
    tile_url = "http://127.0.0.1:8080/styles.json"
    started_at = time.monotonic()
    deadline = started_at + max_seconds
    osrm_up = False
    tiles_up = False
    while time.monotonic() < deadline:
        if not osrm_up:
            osrm_up = _probe(osrm_url)
        if not tiles_up:
            tiles_up = _probe(tile_url)
        if osrm_up and tiles_up:
            break
        time.sleep(1)
    return {
        "osrm_up": osrm_up,
        "tiles_up": tiles_up,
        "elapsed_seconds": round(time.monotonic() - started_at, 1),
        "timeout_seconds": max_seconds,
    }


def docker_ps_summary() -> str:
    """Best-effort `docker ps` output for the bexlogix containers. Used by
    the UI to show the operator which containers are actually running."""
    if not is_docker_available():
        return ""
    try:
        completed = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "name=bexlogix-",
                "--format",
                "{{.Names}}\t{{.Status}}\t{{.Ports}}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return ""
    return (completed.stdout or "").strip()
