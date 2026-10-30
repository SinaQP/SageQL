"""The showcase site data must be exactly what the current SDK produces offline."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHOWCASE = ROOT / "examples" / "showcase"


def _builder():
    spec = importlib.util.spec_from_file_location("sageql_showcase_build", SHOWCASE / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_showcase_matches_an_offline_rebuild(tmp_path):
    output = tmp_path / "showcase.json"
    _builder().build(output=output)
    committed = json.loads((SHOWCASE / "site" / "showcase.json").read_text(encoding="utf-8"))
    rebuilt = json.loads(output.read_text(encoding="utf-8"))
    rebuilt["sageql_version"] = committed["sageql_version"]  # Editable installs report their own version.
    assert rebuilt == committed, "Run python examples/showcase/build.py and commit the result"


def test_showcase_examples_keep_their_guarantees(tmp_path):
    data = _builder().build(output=tmp_path / "showcase.json")
    examples = {item["id"]: item for item in data["examples"]}
    calls = [call for item in data["examples"] for turn in item["turns"] for call in turn["model_calls"]]
    assert calls and all(call["leaked"] == [] for call in calls)
    for item in data["examples"]:
        for turn in item["turns"]:
            for query in turn["queries"]:
                if query["dataset"] == "sales":
                    assert "store_code" in query["sqlite"] and "voided" in query["sqlite"]
                    assert "north" in query["parameters"] and "south" not in query["parameters"]
    saved = examples["top-products-saved"]["turns"][-1]
    assert saved["saved_report"] and saved["model_calls"] == [] and saved["reply"]["status"] == "report_ready"
    invented = examples["simulated-unregistered-column"]["turns"][0]
    assert invented["queries"] == [] and invented["reply"]["status"] != "report_ready"
    injected = examples["simulated-injected-value"]["turns"][0]
    assert "Books' OR '1'='1" in injected["queries"][0]["parameters"]
    assert "OR '1'='1" not in injected["queries"][0]["sqlite"]
