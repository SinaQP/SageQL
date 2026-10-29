"""The public offline probe executes both modes and leaves durable safe evidence."""
import json
from pathlib import Path
import subprocess
import sys


def test_offline_probe_records_actual_schedules_and_cleanup(tmp_path):
    output=tmp_path/"results.json"
    result=subprocess.run([sys.executable,"-I",str(Path(__file__).parents[1]/"tools/probe_read_consistency.py"),
                           "--output",str(output)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    record=json.loads(output.read_text())
    assert record["passed"] and len(record["cases"])==14
    assert record["sql_server"]["execution_status"]=="not executed"
    assert all(c["cleanup"] and c["execution_status"]=="executed" for c in record["cases"])
    assert all(c["transaction_boundaries"]["connections"]==1 for c in record["cases"] if c["isolation_mode"]=="snapshot")
    assert any(c["classification"]=="demonstrated compatibility read skew" for c in record["cases"])
    assert list(tmp_path.iterdir())==[output]
