"""Offline, cross-platform release gates. Never publishes or calls a model.

Run installed smoke with ``python -I tools/release_check.py smoke ...`` so the
checkout cannot supply imports. Archive checking needs only the standard library.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import hashlib
from importlib import metadata
import importlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import pkgutil
import platform
import runpy
import re
import socket
import sqlite3
import subprocess
import sys
import tarfile
import time
import zipfile
from email.parser import BytesParser

# The release version comes from the checked source, never a hardcoded copy.
VERSION = re.search(r'^version = "([^"]+)"', (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def environment():
    packages = {}
    for name in ("sageql", "sqlglot", "python-dotenv", "openai", "pyodbc", "pytest", "build", "hatchling"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    return {"python": platform.python_version(), "implementation": platform.python_implementation(),
            "platform": platform.platform(), "sqlite": sqlite3.sqlite_version,
            "executable": sys.executable, "dependencies": packages}


def smoke(args):
    def reject_network(*unused, **options):
        raise AssertionError("Network forbidden in installed-package smoke")
    socket.socket.connect = reject_network
    socket.socket.connect_ex = reject_network
    socket.create_connection = reject_network
    import sageql
    origin = Path(sageql.__file__).resolve()
    if args.editable:
        assert origin.is_relative_to(args.source.resolve() / "src"), origin
    else:
        assert origin.is_relative_to(Path(sys.prefix).resolve()), origin
        assert not origin.is_relative_to(args.source.resolve() / "src"), origin
    modules = ["sageql", *(m.name for m in pkgutil.walk_packages(sageql.__path__, "sageql."))]
    for name in modules:
        importlib.import_module(name)
    if args.core_only:
        for name in ("openai", "pyodbc", "pytest", "build"):
            assert importlib.util.find_spec(name) is None, name
    if args.extras:
        import openai
        import pyodbc
        # Construct the real client without dispatching a request. No host keys,
        # endpoint configuration, ODBC connection or driver assumption is used.
        client = openai.OpenAI(api_key="synthetic-unused", base_url="https://example.invalid/v1",
                               max_retries=0, timeout=1)
        client.close()
        assert callable(pyodbc.connect)
    digest = hashlib.sha256()
    for file in sorted(origin.parent.rglob("*.py")):
        digest.update(file.relative_to(origin.parent).as_posix().encode())
        digest.update(file.read_bytes())
    results = []
    for name in ("multi_domain.py", "value_vocabulary.py"):
        with (args.output.parent / (name + ".log")).open("w", encoding="utf-8") as log:
            with redirect_stdout(log):
                runpy.run_path(str(args.source / "examples" / name), run_name="__main__")
        results.append(name)
    result = {"schema_version": 1, "environment": environment(), "import_origin": str(origin),
              "installed_source_sha256": digest.hexdigest(), "module_count": len(modules),
              "modules": modules, "examples": results, "network": "blocked",
              "core_only": args.core_only, "editable": args.editable,
              "optional_client_construction": args.extras, "outcome": "passed"}
    write(args.output, result)
    print(json.dumps({k: result[k] for k in ("module_count", "core_only", "editable", "outcome")}))


def unsafe_member(name):
    parts = PurePosixPath(name).parts
    return (name.startswith("/") or ".." in parts or "\\" in name or
            any(p in {".git", ".venv", "dist", "__pycache__", ".pytest_cache", "local_config.py"}
                or (p.startswith(".env") and p != ".env.example") for p in parts) or
            "/sageql_rahtal/reports/" in name or name.endswith((".sqlite", ".sqlite3", ".db", ".pyc")))


def archives(args):
    with zipfile.ZipFile(args.wheel) as z:
        wheel = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
    with tarfile.open(args.sdist) as z:
        assert all(m.isfile() or m.isdir() for m in z.getmembers()), "Unexpected archive link"
        sdist = {m.name: z.extractfile(m).read() for m in z.getmembers() if m.isfile()}
    assert not [n for n in (*wheel, *sdist) if unsafe_member(n)]
    meta_name = next(n for n in wheel if n.endswith(".dist-info/METADATA"))
    meta = BytesParser().parsebytes(wheel[meta_name])
    assert meta["Name"] == "sageql" and meta["Version"] == VERSION
    assert meta["Requires-Python"] == ">=3.10"
    assert set(meta.get_all("Provides-Extra")) == {"dev", "odbc", "openai"}
    requirements = {re.sub(r"\s+", "", r).replace("'", '"')
                    for r in meta.get_all("Requires-Dist", [])}
    assert requirements == {
        'python-dotenv<2,>=1.2', 'sqlglot<31,>=26',
        'build<2,>=1;extra=="dev"', 'pytest<10,>=8;extra=="dev"',
        'pyodbc<6,>=5.2;extra=="odbc"', 'openai<3,>=1.99;extra=="openai"',
    }, requirements
    assert wheel[f'sageql-{VERSION}.dist-info/entry_points.txt'].decode().strip() == '[console_scripts]\nsageql = sageql.cli:main'
    prefix = "sageql-" + meta["Version"] + "/"
    source_roots = {".env.example", ".github", ".gitignore", "AGENTS.md", "CHANGELOG.md", "LICENSE",
                    "README.md", "agent-rules", "docs", "evaluations", "examples",
                    "main.py", "pyproject.toml", "schema.example.json",
                    "src", "tests", "tools", "PKG-INFO"}
    assert all(n.startswith(prefix) and PurePosixPath(n).parts[1] in source_roots for n in sdist), "Unexpected source archive root"
    expected = {"sageql/" + p.relative_to(args.source / "src/sageql").as_posix(): p.read_bytes()
                for p in (args.source / "src/sageql").rglob("*.py")}
    assert {n: b for n, b in wheel.items() if n.startswith("sageql/")} == expected
    assert all(n.startswith(("sageql/", f"sageql-{VERSION}.dist-info/")) for n in wheel)
    for name, content in expected.items():
        assert sdist[prefix + "src/" + name] == content
    for name in ("LICENSE", "README.md", "pyproject.toml", "examples/multi_domain.py",
                 "examples/value_vocabulary.py", "evaluations/phase08/cases.v1.json",
                 "evaluations/phase08/cases.v2.json", "evaluations/phase09/freeze.v2.json",
                 "tests/test_sdk_sessions.py", "tools/release_check.py"):
        assert sdist[prefix + name] == (args.source / name).read_bytes(), name
    assert any(n.endswith("/licenses/LICENSE") for n in wheel)
    result = {"schema_version": 1, "outcome": "passed", "metadata": dict(meta.items()),
              "requires_dist": meta.get_all("Requires-Dist"), "runtime_files": len(expected),
              "inventory": {"wheel": sorted(wheel), "sdist": sorted(sdist)}, "artifacts": {}}
    for kind, path in (("wheel", args.wheel), ("sdist", args.sdist)):
        result["artifacts"][kind] = {"name": path.name, "bytes": path.stat().st_size,
                                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    write(args.output, result)
    print(json.dumps({"outcome": "passed", "wheel_files": len(wheel), "sdist_files": len(sdist)}))


def offline(args):
    # No integration opt-in may be inherited by the default release gate.
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("SAGEQL_SQLSERVER_TEST_", "SAGEQL_EVAL_")) or key in {"PYTHONPATH", "PYTHONHOME"}:
            del env[key]
    env["PYTHONUTF8"] = "1"
    commands = [] if args.gate == "evaluations" else [
        ("pytest", ["-m", "pytest", "-q", "-o", "pythonpath="], 0),
        ("pip-check", ["-I", "-m", "pip", "check"], 0),
        ("read-consistency", ["-I", str(args.source / "tools/probe_read_consistency.py"), "--output",
                              str(args.output.parent / "read-consistency.json")], 0)]
    for suite in ("regression", "holdout", "phase03", "phase04", "phase05"):
        commands.append((suite, ["-m", "evaluations", "--suite", suite, "--strict", "--output",
                                 str(args.output.parent / (suite + ".json"))], 1 if suite == "phase03" else 0))
    for phase in ("phase06", "phase07", "phase08", "phase09"):
        commands.append((phase, ["-m", "evaluations." + phase, "--cohort", "all", "--output",
                                 str(args.output.parent / phase)], 0))
    records = []
    for name, command, expected in commands:
        start = time.monotonic()
        with (args.output.parent / (name + ".log")).open("w", encoding="utf-8") as log:
            result = subprocess.run([sys.executable, *command], cwd=args.source, env=env,
                                    stdout=log, stderr=subprocess.STDOUT)
        record = {"name": name, "command": [sys.executable, *command], "exit_code": result.returncode,
                  "expected_exit_code": expected, "seconds": round(time.monotonic() - start, 3)}
        records.append(record)
        write(args.output, {"schema_version": 1, "environment": environment(), "commands": records,
                            "outcome": "running"})
        assert result.returncode == expected, record
        if name == "phase03":
            value = json.loads((args.output.parent / "phase03.json").read_text(encoding="utf-8"))
            failures = [r["id"] for r in value["results"] if not r["correct"]]
            assert sorted(failures) == ["D02", "D03"], failures
    write(args.output, {"schema_version": 1, "environment": environment(), "commands": records,
                        "outcome": "passed", "historical_phase03_failures": ["D02", "D03"]})
    print("Offline release gates passed; Phase 03 retains expected exit 1 for D02/D03")


def main():
    if not __debug__:
        raise RuntimeError("Release gates require assertions enabled")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="gate", required=True)
    for name in ("smoke", "archives", "offline", "evaluations"):
        p = sub.add_parser(name)
        p.add_argument("--source", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True)
        if name == "smoke":
            p.add_argument("--core-only", action="store_true")
            p.add_argument("--editable", action="store_true")
            p.add_argument("--extras", action="store_true")
        if name == "archives":
            p.add_argument("--wheel", type=Path, required=True)
            p.add_argument("--sdist", type=Path, required=True)
    args = parser.parse_args()
    args.source = args.source.resolve()
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error("Output already exists; choose a fresh path to preserve first-attempt evidence")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    (offline if args.gate == "evaluations" else globals()[args.gate])(args)


if __name__ == "__main__":
    main()
