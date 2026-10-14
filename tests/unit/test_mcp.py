"""`ds serve-mcp` over stdio with a real MCP client, and `ds agent config`."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typer.testing import CliRunner

from conftest import write_canon, write_repo


def _payload(res):
    """Tool results: a dict comes back as structured content; a list is wrapped under "result"
    or spread over one text block per item, depending on the SDK version."""
    sc = getattr(res, "structuredContent", None)
    if isinstance(sc, dict) and "result" in sc and len(sc) == 1:
        return sc["result"]
    if sc:
        return sc
    texts = [c.text for c in res.content if getattr(c, "text", None)]
    if len(texts) == 1:
        return json.loads(texts[0])
    return [json.loads(t) for t in texts]


async def _session(repo: Path, canon: Path, fn):
    params = StdioServerParameters(command=sys.executable,
                                   args=["-m", "ds_cli.main", "serve-mcp", "--repo", str(repo), "--canon", str(canon)])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return await fn(s)


def test_server_answers_over_stdio(tmp_path):
    canon = write_canon(tmp_path)
    repo = write_repo(tmp_path)

    async def go(s: ClientSession):
        tools = {t.name for t in (await s.list_tools()).tools}
        std = await s.call_tool("read_standard", {"id": "adr-000"})
        status = _payload(await s.call_tool("manifest_status", {}))
        lst = _payload(await s.call_tool("canon_list", {}))
        syms = _payload(await s.call_tool("graph_symbols", {"path": "src/"}))
        return tools, std.content[0].text, status, lst, syms

    tools, text, status, lst, syms = anyio.run(_session, repo, canon, go)
    assert tools == {"read_standard", "manifest_status", "canon_list", "graph_symbols"}
    assert text.startswith("Repo knowledge system (adr-000 v1)") and "Every fact exists once." in text
    assert [a["id"] for a in status["adopted"]] == ["adr-000", "adr-014", "layout"] and status["pending"] == [] and status["errors"] == []
    assert [x["id"] for x in lst] == ["adr-000", "adr-014", "layout"]
    assert syms == {"src/pkg/mod.py": ["load_claims"]}


def test_server_reports_pending_and_declines(tmp_path):
    from ds_cli.canon import reconcile
    from ds_cli.canon.client import Canon
    canon_dir = write_canon(tmp_path, {"adr-014": 2, "layout": 2})
    repo = write_repo(tmp_path)
    reconcile.decline(repo, Canon(canon_dir), "layout", by="ck", reason="monorepo layout", revisit="2027-01-01")

    async def go(s: ClientSession):
        return _payload(await s.call_tool("manifest_status", {}))

    status = anyio.run(_session, repo, canon_dir, go)
    assert [p["id"] for p in status["pending"]] == ["adr-014"]
    assert status["declined"][0]["id"] == "layout" and status["declined"][0]["reason"] == "monorepo layout"


def test_agent_config_writes_known_registrations(tmp_path):
    from ds_cli.main import app
    repo = write_repo(tmp_path)
    (repo / ".mcp.json").write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    r = CliRunner().invoke(app, ["agent", "config", str(repo)])
    assert r.exit_code == 0, r.output
    data = json.loads((repo / ".mcp.json").read_text())
    assert data["mcpServers"]["other"] == {"command": "x"} and data["mcpServers"]["ds"]["args"] == ["serve-mcp"]
    coco = json.loads((repo / ".ds/coco-settings.json").read_text())
    assert "_unverified" in coco and coco["mcpServers"]["ds"]["command"] == "ds"
    assert (repo / ".ds/agent.toml").exists()
    r = CliRunner().invoke(app, ["agent", "config", str(repo)])
    assert "already configured" in r.output


def test_new_writes_mcp_json(tmp_path):
    from ds_cli.main import app
    canon_dir = write_canon(tmp_path)
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "answers.toml"
    r = CliRunner().invoke(app, ["new", "demo", "--dir", str(tmp_path / "demo"), "--answers", str(fixture), "--canon", str(canon_dir)])
    assert r.exit_code == 0, r.output
    assert json.loads((tmp_path / "demo/.mcp.json").read_text())["mcpServers"]["ds"]["command"] == "ds"
