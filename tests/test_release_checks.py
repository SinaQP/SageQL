"""Release gates reject missing, altered and private archive members."""
import importlib.util
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import tarfile
import zipfile

import pytest


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("sageql_release_checks", ROOT / "tools/release_check.py")
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


def artifacts(tmp_path, mutation=None):
    files = {"sageql/" + p.relative_to(ROOT / "src/sageql").as_posix(): p.read_bytes()
             for p in (ROOT / "src/sageql").rglob("*.py")}
    wheel = dict(files)
    info = f"sageql-{checks.VERSION}.dist-info/"
    wheel[info + "METADATA"] = f'''Metadata-Version: 2.4
Name: sageql
Version: {checks.VERSION}
Requires-Python: >=3.10
Provides-Extra: dev
Provides-Extra: odbc
Provides-Extra: openai
Requires-Dist: python-dotenv<2,>=1.2
Requires-Dist: sqlglot<31,>=26
Requires-Dist: build<2,>=1; extra == "dev"
Requires-Dist: pytest<10,>=8; extra == "dev"
Requires-Dist: pyodbc<6,>=5.2; extra == "odbc"
Requires-Dist: openai<3,>=1.99; extra == "openai"
'''.encode()
    wheel[info + "licenses/LICENSE"] = (ROOT / "LICENSE").read_bytes()
    wheel[info + "entry_points.txt"] = b"[console_scripts]\nsageql = sageql.cli:main\n"
    if mutation == "private":
        wheel["sageql/.env"] = b"SYNTHETIC=1"
    elif mutation == "missing":
        del wheel["sageql/sdk/sessions.py"]
    elif mutation == "altered":
        wheel["sageql/sdk/sessions.py"] += b"\n# changed\n"
    elif mutation == "requirements":
        wheel[info + "METADATA"] = wheel[info + "METADATA"].replace(b"sqlglot<31,>=26", b"sqlglot>=1")
    elif mutation == "single-quotes":
        wheel[info + "METADATA"] = wheel[info + "METADATA"].replace(b'"', b"'")
    wp = tmp_path / "test.whl"
    with zipfile.ZipFile(wp, "w") as z:
        for n, b in wheel.items():
            z.writestr(n, b)
    sp = tmp_path / "test.tar.gz"
    source = {"src/" + n: b for n, b in files.items()}
    if mutation == "stray-root":
        source["=8,"] = b""
    for name in ("LICENSE", "README.md", "pyproject.toml", "examples/multi_domain.py",
                 "examples/value_vocabulary.py", "evaluations/phase08/cases.v1.json",
                 "evaluations/phase08/cases.v2.json", "evaluations/phase09/freeze.v2.json",
                 "tests/test_sdk_sessions.py", "tools/release_check.py"):
        source[name] = (ROOT / name).read_bytes()
    with tarfile.open(sp, "w:gz") as z:
        for n, b in source.items():
            entry = tarfile.TarInfo(f"sageql-{checks.VERSION}/" + n)
            entry.size = len(b)
            z.addfile(entry, BytesIO(b))
        if mutation == "link":
            entry = tarfile.TarInfo(f"sageql-{checks.VERSION}/linked")
            entry.type = tarfile.SYMTYPE
            entry.linkname = "../../outside"
            z.addfile(entry)
    return SimpleNamespace(wheel=wp, sdist=sp, source=ROOT, output=tmp_path / "inventory.json")


def test_archive_gate_binds_runtime_bytes_and_metadata(tmp_path):
    args = artifacts(tmp_path)
    checks.archives(args)
    assert args.output.exists()


def test_archive_gate_accepts_equivalent_older_backend_marker_quotes(tmp_path):
    checks.archives(artifacts(tmp_path, "single-quotes"))


@pytest.mark.parametrize("mutation", ["private", "missing", "altered", "requirements", "link", "stray-root"])
def test_archive_gate_fails_closed(tmp_path, mutation):
    args = artifacts(tmp_path, mutation)
    with pytest.raises(AssertionError):
        checks.archives(args)
    assert not args.output.exists()


def test_offline_gate_covers_all_cases_and_clears_external_opt_ins(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setenv("SAGEQL_SQLSERVER_TEST_CONFIRM_SYNTHETIC", "1")
    monkeypatch.setenv("SAGEQL_EVAL_API_KEY", "synthetic-unused")

    def run(command, **options):
        calls.append(command)
        assert not any(k.startswith(("SAGEQL_SQLSERVER_TEST_", "SAGEQL_EVAL_")) for k in options["env"])
        if "phase03" in command:
            target = Path(command[command.index("--output") + 1])
            target.write_text(json.dumps({"results": [{"id": k, "correct": False} for k in ("D02", "D03")]}))
            return SimpleNamespace(returncode=1)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(checks, "subprocess", SimpleNamespace(run=run, STDOUT=checks.subprocess.STDOUT))
    checks.offline(SimpleNamespace(source=ROOT, output=tmp_path / "gates.json", gate="evaluations"))
    phase06 = next(c for c in calls if "evaluations.phase06" in c)
    assert phase06[phase06.index("--cohort") + 1] == "all"
    assert json.loads((tmp_path / "gates.json").read_text())["historical_phase03_failures"] == ["D02", "D03"]
