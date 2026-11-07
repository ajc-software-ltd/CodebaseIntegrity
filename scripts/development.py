#!/usr/bin/env python3
"""Development helpers for CII (PLAN.md §4, §17).

Subcommands:
    benchmark   Generate a synthetic multi-language project and measure the
                PLAN.md §17.1 engineering targets (status, single-file lookup,
                symbol search, incremental scan, full scan, Markdown export).

Usage:
    python scripts/development.py benchmark [--files 1000]
"""

import argparse
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path


def _generate_project(root: Path, files: int) -> None:
    for index in range(files):
        if index % 3 == 0:
            path = root / f"pkg{index // 50}" / f"mod{index}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f"class C{index}:\n"
                f"    def __init__(self):\n        self.v = {index}\n"
                f"    def run{index}(self, x):\n        return x + {index}\n"
                f"    def stop{index}(self):\n        pass\n\n"
                f"def helper{index}(a, b):\n    return a + b\n"
            )
        elif index % 3 == 1:
            path = root / f"src{index // 50}" / f"class{index}.cpp"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f"namespace n{index} {{\n"
                f"class K{index} {{\npublic:\n"
                f"    K{index}();\n    ~K{index}();\n"
                f"    void init{index}();\n    void stop{index}();\n"
                f"private:\n    int v_;\n}};\n"
                f"int free{index}(int x);\n}}\n"
            )
        else:
            path = root / f"cs{index // 50}" / f"T{index}.cs"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f"namespace App.M{index // 50} {{\n"
                f"    public class T{index} {{\n"
                f"        public T{index}() {{}}\n"
                f"        public void Go{index}() {{}}\n"
                f"        public int P{index} {{ get; set; }}\n"
                f"    }}\n}}\n"
            )


def _timeit(fn, repeats: int = 3) -> float:  # type: ignore[no-untyped-def]
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def benchmark(files: int) -> int:
    from cii.application import Application
    from cii.core.configuration import CiiConfig
    from cii.database.database import Database
    from cii.database.repositories import ProjectRepository
    from cii.mcp import tools as tool_impl

    root = Path(tempfile.mkdtemp(prefix="cii-bench-"))
    try:
        print(f"generating synthetic project: {files} files in {root} …")
        _generate_project(root, files)

        config = CiiConfig.defaults()
        database = Database.open(root)
        ProjectRepository(database.connection).register(
            "benchmark", str(root), "1.0", "hash"
        )
        app = Application(root, config, database)

        full_scan_ms = _timeit(lambda: app.scan(full=True), repeats=1)
        incremental_ms = _timeit(lambda: app.scan())
        status_ms = _timeit(lambda: tool_impl.index_status(app))
        lookup_ms = _timeit(lambda: tool_impl.index_symbol(app, "K10"))
        search_ms = _timeit(lambda: tool_impl.index_search(app, "init"))
        export_ms = _timeit(lambda: app.export())
        validate_ms = _timeit(lambda: tool_impl.index_validate(app))

        stats = tool_impl.index_statistics(app)
        results = [
            ("full scan (first)", full_scan_ms, None),
            ("incremental scan (no changes)", incremental_ms, "proportional"),
            ("index_status", status_ms, 100),
            ("single-file symbol lookup", lookup_ms, 100),
            ("symbol search", search_ms, 250),
            ("Markdown export", export_ms, "proportional"),
            ("index_validate (quick)", validate_ms, None),
        ]
        print(f"\nproject: {stats.total_files} files, {stats.total_symbols} symbols")
        print(f"{'operation':32} {'median ms':>10}  {'target ms':>10}  verdict")
        for name, measured, target in results:
            if target is None or target == "proportional":
                verdict = "—"
            else:
                verdict = "within target" if measured <= target else "OVER TARGET"
            print(f"{name:32} {measured:10.1f}  {str(target):>10}  {verdict}")
        database.close()
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    bench = sub.add_parser("benchmark", help="run the synthetic-project benchmark")
    bench.add_argument("--files", type=int, default=1000)
    args = parser.parse_args()
    if args.command == "benchmark":
        return benchmark(args.files)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
