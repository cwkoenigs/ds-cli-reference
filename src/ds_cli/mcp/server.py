"""The ds MCP server: read_standard, manifest_status, canon_list, graph_symbols.

Graph tools are a stand-in backed by the AST walker in ``canon.derived``. When a code-graph MCP
(for example codebase-memory-mcp) is installed and registered, agents should prefer it for
callers and blast radius; this server answers "what is public, where" without one.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from mcp.server.mcpserver import MCPServer

from ..canon import derived, manifest as manifest_mod, reconcile
from ..canon.client import Canon, CanonError
from ..docs.render import label

INSTRUCTIONS = ("Call manifest_status first: it says which standards apply to this repository and whether each is "
                "adopted, declined (with the reason), or pending. Read a standard's text with read_standard before "
                "applying it. Use graph_symbols to find public symbols before reading files.")


def build_server(repo: Path, canon: Canon) -> MCPServer:
    repo = Path(repo).resolve()
    server = MCPServer("ds", instructions=INSTRUCTIONS, version="0.1")

    @server.tool(description="Text of a standard from the canon, by id; optionally pinned to a version.")
    def read_standard(id: str, version: Optional[int] = None) -> str:
        try:
            res = canon.resolve(id, version)
        except CanonError as e:
            return f"error: {e}"
        note = " (pinned below the current version; text shown is current)" if res.stale else ""
        return f"{label(res.standard, version)}{note}\napplies_to: {list(res.standard.applies_to)}  owner: {res.standard.owner}\n\n{res.text}"

    @server.tool(description="This repository's standing against the canon: adopted, declined (with reasons), pending, and any errors.")
    def manifest_status() -> dict[str, Any]:
        r = reconcile.check(repo, canon, regen=False)
        try:
            m = manifest_mod.for_repo(repo, canon)
        except manifest_mod.ManifestError as e:
            return {"repo": repo.name, "errors": [str(e)], "adopted": [], "declined": [], "pending": []}
        pending_ids = {f.where.split("@")[0] for f in r.pending}
        adopted, declined = [], []
        for std in canon.applicable(m.tags):
            e = m.entries.get(std.id)
            if std.id in pending_ids or e is None:
                continue
            if e.status == "adopted":
                adopted.append({"id": std.id, "version": e.version, "title": std.title})
            elif e.status == "declined":
                declined.append({"id": std.id, "version": e.version, "title": std.title, "reason": e.reason, "revisit": e.revisit, "by": e.by})
        pending = [{"id": f.where.split("@")[0], "version": int(f.where.split("@")[1]), "why": f.message} for f in r.pending]
        return {"repo": m.name, "tags": m.tags, "adopted": adopted, "declined": declined, "pending": pending,
                "errors": [f"{f.where}: {f.message}" for f in r.errors]}

    @server.tool(description="Every standard in the canon that applies to this repository, with title and version.")
    def canon_list() -> list[dict[str, Any]]:
        try:
            m = manifest_mod.for_repo(repo)
            tags = m.tags
        except manifest_mod.ManifestError:
            tags = ["*"]
        return [{"id": s.id, "version": s.version, "title": s.title, "applies_to": list(s.applies_to), "owner": s.owner}
                for s in canon.applicable(tags)]

    @server.tool(description="Public symbols per module (functions and classes under src/, dbt models), optionally filtered by a path prefix.")
    def graph_symbols(path: str = "") -> dict[str, list[str]]:
        symbols = derived.public_symbols(repo)
        return {mod: names for mod, names in symbols.items() if mod.startswith(path)} if path else symbols

    return server


def serve(repo: Path, canon: Canon) -> None:
    build_server(repo, canon).run(transport="stdio")
