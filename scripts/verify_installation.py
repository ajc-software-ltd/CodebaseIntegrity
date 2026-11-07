#!/usr/bin/env python3
"""Verify a CII installation end-to-end (PLAN.md §21 M12).

Exercises the installed package exactly as a new user would: version, init,
scan, search, validate, export — in a temporary project. Exit code 0 means the
installation is operational.

Usage:
    python scripts/verify_installation.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
        if not ok:
            failures.append(name)

    # 1. package importable with the expected version
    import cii

    check("package import", True, f"cii {cii.__version__}")

    with tempfile.TemporaryDirectory(prefix="cii-verify-") as tmp:
        root = Path(tmp)
        (root / "sample.py").write_text("class Sample:\n    def run(self):\n        pass\n")

        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, "-m", "cii", *args, "--root", str(root)],
                capture_output=True, text=True, timeout=120,
            )

        init = run("init")
        check("cii init", init.returncode == 0 and (root / ".cii" / "cii.db").is_file())

        scan = run("scan", "--json")
        payload = json.loads(scan.stdout) if scan.returncode == 0 else {}
        check("cii scan", scan.returncode == 0 and payload.get("files_indexed") == 1)

        search = run("search", "run", "--json")
        found = json.loads(search.stdout) if search.returncode == 0 else {}
        check("cii search", found.get("total") == 1)

        validate = run("validate", "--json")
        verdict = json.loads(validate.stdout) if validate.returncode == 0 else {}
        check("cii validate", verdict.get("status") == "healthy")

        export = root / ".cii" / "CODEBASE_INDEX.md"
        check("cii export (via scan)", export.is_file())

        status = run("status", "--json")
        state = json.loads(status.stdout) if status.returncode == 0 else {}
        check("cii status", state.get("database_healthy") is True)

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("All installation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
