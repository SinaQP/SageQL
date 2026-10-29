"""Pure approval validation: never import/connect a real driver."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tools.sqlserver_synthetic import Runtime, load_approval, validate_approval


def approval():
    value=json.loads((Path(__file__).parents[1]/"evaluations/phase11/sqlserver-approval.example.json").read_text())
    value.update(authorized=True,authorization_id="UNIT_TEST_ONLY",network_exposure="unit test; no connections")
    return value


def test_disabled_template_and_missing_confirmation_cannot_read_private_files(monkeypatch):
    value=approval();value["authorized"]=False
    with pytest.raises(ValueError):validate_approval(value)
    monkeypatch.delenv("SAGEQL_SQLSERVER_TEST_CONFIRM_PHASE11",raising=False)
    monkeypatch.setattr(Path,"read_text",lambda *a,**k:pytest.fail("No file read without opt-in"))
    assert load_approval() is None


@pytest.mark.parametrize("key,value",[("version",True),("synthetic_only",False),("database","Production"),
    ("authentication","inferred"),("max_seconds",121),("query_timeout_seconds",float("inf")),
    ("allowed_operations",["select","alter_database"]),("cleanup_policy","none"),
    ("tables",{"facts":"unapproved"}),("schema","dbo];DROP TABLE x;--")])
def test_unreviewed_or_unbounded_target_is_rejected(key,value):
    config=approval();config[key]=value
    with pytest.raises(ValueError):validate_approval(config)


def test_host_seeded_read_only_and_catalog_are_constructed_without_network():
    value=approval();value.update(fixture_policy="host_seeded",cleanup_policy="leave_host_seeded_unchanged",
        tables={"facts":"sageql_phase11_seeded_facts","people":"sageql_phase11_seeded_people"},allowed_operations=["select"])
    runtime=Runtime(value)
    assert runtime.allowed("select") and not runtime.allowed("update_fixture")
    from sageql.sdk.semantics import validate_catalog
    validate_catalog(runtime.catalog())
    assert not runtime.connections


def test_creation_needs_explicit_seeding_and_cleanup():
    value=approval();value["allowed_operations"]=["select","create_fixture"]
    with pytest.raises(ValueError):validate_approval(value)
