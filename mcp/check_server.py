"""Start the MCP server as a real subprocess over stdio and use it like an MCP client would.

Usage: python mcp/check_server.py [certificate_code]
"""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = str(Path(__file__).with_name("server.py"))


def show(label, result):
    text = "".join(getattr(c, "text", "") for c in result.content)
    try:
        data = json.loads(text)
    except ValueError:
        data = text
    print(f"\n== {label}\n{json.dumps(data, indent=1, ensure_ascii=False)[:900]}")
    return data


async def main(code: str | None):
    params = StdioServerParameters(command=sys.executable, args=[SERVER])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            print("tools:", [t.name for t in tools])
            assert {"search_registry", "get_profile", "verify_certificate", "check_document_content", "registry_overview"} <= {t.name for t in tools}

            data = show("search_registry", await s.call_tool("search_registry", {"query": "river pollution journalist", "limit": 2}))
            assert data["results"], "expected results"
            slug = data["results"][0]["slug"]
            show("get_profile", await s.call_tool("get_profile", {"slug": slug}))
            show("registry_overview", await s.call_tool("registry_overview", {}))
            if code:
                v = show("verify_certificate", await s.call_tool("verify_certificate", {"code": code}))
                assert v["valid"] is True
                real = v["holder"]
                good = show("check_document_content (true name)", await s.call_tool("check_document_content", {"code": code, "full_name": real}))
                bad = show("check_document_content (forged name)", await s.call_tool("check_document_content", {"code": code, "full_name": "Someone Else"}))
                assert good["matches"] is True and bad["matches"] is False and "full_name" in bad["differences"]
            err = show("unknown profile", await s.call_tool("get_profile", {"slug": "no-such-person"}))
            assert err["status"] == 404
    print("\nMCP server OK")


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
