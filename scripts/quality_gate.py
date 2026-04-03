from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAGES_DIR = PROJECT_ROOT / "client" / "pages"
REPOSITORIES_DIR = PROJECT_ROOT / "server" / "app" / "repositories"
SERVICES_DIR = PROJECT_ROOT / "server" / "app" / "services"

MAX_REPOSITORY_FUNCTION_LENGTH = 120
MAX_SERVICE_FILE_LENGTH = 700


def _iter_python_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*.py") if path.is_file())


def _function_length(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    end_lineno = getattr(node, "end_lineno", None)
    if end_lineno is None:
        return 0
    return int(end_lineno) - int(node.lineno) + 1


def _check_no_direct_queries_in_pages() -> list[str]:
    violations: list[str] = []
    patterns = ("db.query(", "read_sql_query(")
    for path in _iter_python_files(PAGES_DIR):
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            if pattern in text:
                violations.append(
                    f"{path.relative_to(PROJECT_ROOT)} contains forbidden page-level query pattern: {pattern}"
                )
    return violations


def _check_repository_boundaries() -> list[str]:
    violations: list[str] = []
    for path in _iter_python_files(REPOSITORIES_DIR):
        source = path.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(path))
        for node in module.body:
            if not isinstance(node, ast.ImportFrom):
                continue
            module_name = node.module or ""
            if module_name.startswith("server.app.services"):
                violations.append(
                    f"{path.relative_to(PROJECT_ROOT)} imports service layer ({module_name})."
                )
        for node in ast.walk(module):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                length = _function_length(node)
                if length > MAX_REPOSITORY_FUNCTION_LENGTH:
                    violations.append(
                        f"{path.relative_to(PROJECT_ROOT)}::{node.name} is too long ({length} lines)."
                    )
    return violations


def _check_service_file_lengths() -> list[str]:
    violations: list[str] = []
    for path in _iter_python_files(SERVICES_DIR):
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > MAX_SERVICE_FILE_LENGTH:
            violations.append(
                f"{path.relative_to(PROJECT_ROOT)} exceeds max service file length "
                f"({len(lines)} > {MAX_SERVICE_FILE_LENGTH})."
            )
    return violations


def run_quality_gate() -> list[str]:
    violations: list[str] = []
    violations.extend(_check_no_direct_queries_in_pages())
    violations.extend(_check_repository_boundaries())
    violations.extend(_check_service_file_lengths())
    return violations


def main() -> int:
    violations = run_quality_gate()
    if not violations:
        print("Quality gate passed.")
        return 0

    print("Quality gate failed:")
    for violation in violations:
        print(f"- {violation}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
