from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_quality_gate() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "scripts" / "quality_gate.py"
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise AssertionError(
            "Quality gate failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
