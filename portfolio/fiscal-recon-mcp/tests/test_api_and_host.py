import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from fiscal_recon.api import app, get_service
from tests.conftest import DATES

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host"))
import host  # noqa: E402


def client_for(service):
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


def test_api_summary(service):
    r = client_for(service).post("/reconciliation/summary", json={"reference_date": DATES[0].isoformat()})
    assert r.status_code == 200 and r.json()["total_records"] == 300


def test_api_rejects_bad_date_with_400(service):
    r = client_for(service).post("/reconciliation/summary", json={"reference_date": "yesterday"})
    assert r.status_code == 400


def test_api_branches(service):
    r = client_for(service).post("/reconciliation/branches", json={"reference_date": DATES[0].isoformat()})
    assert r.status_code == 200 and r.json()["divergences"]


def test_host_tool_conversion():
    tool = SimpleNamespace(name="t", description=None, inputSchema={"type": "object"})
    [converted] = host.mcp_tools_to_ollama([tool])
    assert converted["function"] == {"name": "t", "description": "", "parameters": {"type": "object"}}


def test_host_parses_string_arguments():
    assert host.parse_arguments('{"a": 1}') == {"a": 1}
    assert host.parse_arguments("not json") == {}
    assert host.parse_arguments(None) == {}


def test_host_flattens_error_results():
    result = SimpleNamespace(content=[SimpleNamespace(text="boom")], isError=True)
    assert host.tool_result_to_text(result) == "ERROR: boom"
