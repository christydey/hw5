"""Connects the agent team to the campus-customs MCP server.

This is an MCP *client*, not a data layer: it never opens the database.
It starts the server exactly as .mcp.json defines it (the same definition
Claude Code uses), keeps one stdio connection for the whole team, and gives
each agent a toolset limited to the MCP tools on its allow-list.

(pydantic_ai.mcp is not usable in this venv because it imports `httpx`,
while the installed mcp/openai stack ships `httpx2`; fastmcp.Client speaks
the same MCP protocol and imports cleanly.)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic import TypeAdapter
from pydantic_ai import RunContext
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool

from .config import MCP_CALL_TIMEOUT_SECONDS, MCP_CONFIG_FILE, MCP_SERVER_NAME, PROJECT_ROOT
from .models import TeamDeps, ToolCallRecord

_ARGS_VALIDATOR = TypeAdapter(dict[str, Any]).validator  # the MCP server validates the real schema
# Tools that change the database. No agent may ever be given these; only the
# backend's human-approval, resolve and reset routes call them, via admin_call().
WRITE_TOOLS = frozenset({"execute_approved_payment", "resolve_ticket", "reset_working_database"})
ADMIN_SECRET_ENV = "CAMPUS_CUSTOMS_ADMIN_SECRET"  # must match mcp_server/server.py
_EXCERPT_CHARS = 600


class ShopMCPError(RuntimeError):
    pass


def _server_command() -> tuple[str, list[str]]:
    try:
        cfg = json.loads(MCP_CONFIG_FILE.read_text(encoding="utf-8"))["mcpServers"][MCP_SERVER_NAME]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ShopMCPError(f"Could not read the {MCP_SERVER_NAME!r} server from {MCP_CONFIG_FILE}: {exc}") from exc
    command, args = cfg["command"], list(cfg.get("args", []))
    # .mcp.json may hold machine-specific absolute paths (it is also what Claude Code
    # uses). On another machine, fall back to this Python and the repo's own server.
    if not (Path(command).exists() or shutil.which(command)):
        command = sys.executable
    args = [
        a if not a.endswith("server.py") or Path(a).exists() else str(PROJECT_ROOT / "mcp_server" / "server.py")
        for a in args
    ]
    return command, args


class ShopMCP:
    """One MCP connection shared by every agent in a run. Use as `async with`."""

    def __init__(self, admin_secret: str | None = None) -> None:
        """admin_secret: only the FastAPI backend passes one. It enables the
        server's write tools for this connection alone and is used to sign
        each write call. Agent-only runs (CLI) leave it unset, so the server
        they start cannot write at all."""
        command, args = _server_command()
        # A minimal environment: the server gets no API keys.
        env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG") if k in os.environ}
        env["FASTMCP_SHOW_SERVER_BANNER"] = "false"
        if admin_secret:
            env[ADMIN_SECRET_ENV] = admin_secret
        self._admin_secret = admin_secret
        self._client = Client(StdioTransport(command=command, args=args, env=env))
        self.tools: dict[str, Any] = {}

    async def __aenter__(self) -> ShopMCP:
        await self._client.__aenter__()
        self.tools = {t.name: t for t in await self._client.list_tools()}
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._client.__aexit__(*exc)

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Call a tool and return its structured result. Tool-side failures
        (bad arguments, missing rows) come back as {"error": ...} so the
        calling agent can adapt instead of crashing the run."""
        if name not in self.tools:
            return {"error": f"Unknown MCP tool {name!r}."}
        try:
            result = await self._client.call_tool(
                name, args, raise_on_error=False, timeout=MCP_CALL_TIMEOUT_SECONDS
            )
        except Exception as exc:  # transport/timeout failure
            return {"error": f"MCP call to {name} failed: {type(exc).__name__}: {exc}"}
        if result.is_error:
            text = " ".join(getattr(c, "text", "") for c in result.content).strip()
            return {"error": text or f"{name} returned an error."}
        return result.structured_content or {"result": [getattr(c, "text", "") for c in result.content]}

    async def admin_call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Call a write tool, signed with this connection's secret. Only the
        backend's human-facing routes use this; agents never reach it."""
        if name not in WRITE_TOOLS:
            raise ShopMCPError(f"{name} is not a write tool.")
        if not self._admin_secret:
            raise ShopMCPError("This MCP connection was opened without an admin secret.")
        signed = {k: v for k, v in args.items() if v is not None}
        payload = name + ":" + json.dumps(signed, sort_keys=True, separators=(",", ":"))
        signature = hmac.new(self._admin_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return await self.call(name, {**signed, "authorization": signature})

    def toolset_for(self, agent: str, allowed: tuple[str, ...]) -> AgentMCPToolset:
        if forbidden := sorted(WRITE_TOOLS.intersection(allowed)):
            raise ShopMCPError(f"{agent} may not be given write tools {forbidden}.")
        missing = [t for t in allowed if t not in self.tools]
        if missing:
            raise ShopMCPError(f"MCP server does not expose {missing} (needed by {agent}).")
        return AgentMCPToolset(self, agent, allowed)


class AgentMCPToolset(AbstractToolset[TeamDeps]):
    """The subset of MCP tools one agent may call, with caching and audit."""

    def __init__(self, shop: ShopMCP, agent: str, allowed: tuple[str, ...]):
        self._shop = shop
        self._agent = agent
        self._allowed = allowed

    @property
    def id(self) -> str:
        return f"{MCP_SERVER_NAME}:{self._agent}"

    async def get_tools(self, ctx: RunContext[TeamDeps]) -> dict[str, ToolsetTool[TeamDeps]]:
        tools = {}
        for name in self._allowed:
            mcp_tool = self._shop.tools[name]
            tools[name] = ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name=name,
                    description=mcp_tool.description,
                    parameters_json_schema=mcp_tool.input_schema,
                ),
                max_retries=1,
                args_validator=_ARGS_VALIDATOR,
            )
        return tools

    async def call_tool(
        self, name: str, tool_args: dict[str, Any], ctx: RunContext[TeamDeps], tool: ToolsetTool[TeamDeps]
    ) -> Any:
        deps = ctx.deps
        if name not in self._allowed or name in WRITE_TOOLS:  # defence in depth; get_tools already limits this
            return {"error": f"{self._agent} is not allowed to call {name}."}

        key = f"{name}:{json.dumps(tool_args, sort_keys=True)}"
        cached = key in deps.budget.mcp_cache
        result = deps.budget.mcp_cache[key] if cached else await self._shop.call(name, tool_args)
        ok = "error" not in result
        if ok and not cached:
            deps.budget.mcp_cache[key] = result
        if ok:
            deps.tools_called.add(name)

        deps.audit.append(
            event="mcp_tool_call",
            ticket_id=deps.ticket_id,
            agent=deps.agent,
            depth=deps.depth,
            tool_calls=[
                ToolCallRecord(
                    tool=name,
                    args=tool_args,
                    ok=ok,
                    cached=cached,
                    result_excerpt=json.dumps(result, default=str)[:_EXCERPT_CHARS],
                )
            ],
            error=None if ok else result["error"],
        )
        return result
