import json


async def rpc(client, method, params=None, id_=1):
    return await client.post("/mcp", content=json.dumps({"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}),
                             headers={"content-type": "application/json"})


async def test_initialize_and_list_expose_only_read_only_tools(client):
    r = (await rpc(client, "initialize", {"protocolVersion": "2025-06-18"})).json()["result"]
    assert r["serverInfo"]["name"] == "pramaan" and r["capabilities"] == {"tools": {"listChanged": False}}
    tools = (await rpc(client, "tools/list")).json()["result"]["tools"]
    assert {t["name"] for t in tools} == {"verify_certificate", "search_people"}
    assert all(t["annotations"]["readOnlyHint"] for t in tools)


async def test_notifications_get_no_reply_and_bad_input_is_an_error_not_a_crash(client):
    n = await client.post("/mcp", content=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}))
    assert n.status_code == 202 and n.content == b""
    assert (await client.post("/mcp", content="{not json")).status_code == 400
    assert (await rpc(client, "nope")).json()["error"]["code"] == -32601
    assert (await rpc(client, "tools/call", {"name": "delete_everything"})).json()["error"]["code"] == -32602


async def test_verify_tool_says_not_found_for_an_unknown_code(client):
    r = (await rpc(client, "tools/call", {"name": "verify_certificate", "arguments": {"code": "PRM-DOESNOTEXIST"}})).json()["result"]
    body = json.loads(r["content"][0]["text"])
    assert "valid" in body or "detail" in body


async def test_search_tool_returns_only_public_fields(client):
    r = (await rpc(client, "tools/call", {"name": "search_people", "arguments": {"query": "physicist in Kerala", "limit": 3}})).json()["result"]
    body = json.loads(r["content"][0]["text"])
    assert isinstance(body["results"], list)
    for h in body["results"]:
        assert set(h) == {"name", "slug", "headline", "sector", "state", "why", "verified_claims"}
