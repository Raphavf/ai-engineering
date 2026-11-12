"""End-to-end tests through a real MCP client session (in-memory transport)."""

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from fiscal_recon.mcp_server import build_server
from tests.conftest import DATES

pytestmark = pytest.mark.anyio

DATE = DATES[0].isoformat()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def server(service):
    return build_server(service)


def _payload(result):
    """Structured output when available, else parse the text blocks."""
    if result.structuredContent is not None:
        sc = result.structuredContent
        return sc.get("result", sc) if isinstance(sc, dict) and set(sc) == {"result"} else sc
    texts = [b.text for b in result.content]
    return json.loads(texts[0]) if len(texts) == 1 else [json.loads(t) for t in texts]


async def test_lists_expected_tools(server):
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        names = {t.name for t in (await client.list_tools()).tools}
    assert names == {
        "get_reconciliation_summary",
        "list_divergent_records",
        "get_record_detail",
        "get_branch_divergences",
        "explain_reconciliation_rules",
    }


async def test_summary_tool(server, service):
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        result = await client.call_tool("get_reconciliation_summary", {"reference_date": DATE})
    assert not result.isError
    assert _payload(result) == service.summary(DATE).model_dump(mode="json")


async def test_agent_flow_list_then_detail(server):
    """What an agent actually does: list divergences, then drill into one."""
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        listed = _payload(await client.call_tool("list_divergent_records", {"reference_date": DATE, "limit": 5}))
        first = listed[0]
        detail = _payload(
            await client.call_tool(
                "get_record_detail",
                {
                    "reference_date": DATE,
                    "origin_branch": first["origin_branch"],
                    "destination_branch": first["destination_branch"],
                    "document_id": first["document_id"],
                    "series": first["series"],
                },
            )
        )
    assert len(listed) == 5
    assert detail == {"found": True, "record": first}


async def test_limit_is_clamped(server):
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        listed = _payload(await client.call_tool("list_divergent_records", {"reference_date": DATE, "limit": 0}))
    assert len(listed) == 1


async def test_invalid_date_returns_tool_error_not_crash(server):
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        result = await client.call_tool("get_reconciliation_summary", {"reference_date": "2026-13-45"})
    assert result.isError
    assert "YYYY-MM-DD" in result.content[0].text


async def test_branch_divergences_tool(server):
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        branches = _payload(await client.call_tool("get_branch_divergences", {"reference_date": DATE}))
    assert branches
    assert all({"branch_code", "divergence_percentage"} <= set(b) for b in branches)
