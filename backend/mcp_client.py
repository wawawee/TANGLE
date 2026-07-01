"""MCP (Model Context Protocol) tool adapter for TANGLE.

Allows dynamic attachment of any MCP-compatible tool server without
modifying core code. Supports stdio and HTTP transports.

Usage:
    client = McpClient()
    await client.connect_stdio("npx", ["-y", "@modelcontextprotocol/server-filesystem", "."])
    tools = await client.list_tools()
    result = await client.call_tool("read_file", {"path": "/tmp/test.txt"})
    await client.disconnect()
"""

import os
import sys
import json
import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field

logger = logging.getLogger("tangle.mcp")


# ── Data types ──────────────────────────────────────────────────

@dataclass
class McpToolDef:
    """Schema for an MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class McpServerConfig:
    """Configuration for an MCP server connection."""
    name: str
    transport: str  # "stdio" or "http"
    command: str = ""
    args: List[str] = field(default_factory=list)
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)


# ── MCP Client ──────────────────────────────────────────────────

class McpClient:
    """Lightweight MCP client for TANGLE.

    Manages connections to MCP servers over stdio or HTTP transport.
    Provides list_tools and call_tool for each connected server.
    Supports multiple concurrent server connections.
    """

    def __init__(self):
        self._servers: Dict[str, Dict[str, Any]] = {}
        self._tool_registry: Dict[str, Tuple[str, McpToolDef]] = {}
        self._request_id = 0

    # ── Connection Management ──────────────────────────────────

    async def connect_stdio(self, name: str, command: str, args: List[str],
                            env: Optional[Dict[str, str]] = None) -> bool:
        """Connect to an MCP server via stdio transport.

        Args:
            name: Unique server identifier (e.g. "filesystem", "playwright").
            command: Executable path (e.g. "npx", "uvx", "python").
            args: Command arguments.
            env: Optional environment overrides.

        Returns True if connection succeeded.
        """
        if name in self._servers:
            logger.warning(f"MCP server '{name}' already connected")
            return False

        full_env = {**os.environ, **(env or {})}
        try:
            proc = await asyncio.create_subprocess_exec(
                command, *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env,
            )
        except FileNotFoundError:
            logger.error(f"MCP server '{name}': command '{command}' not found")
            return False
        except Exception as e:
            logger.error(f"MCP server '{name}' failed to start: {e}")
            return False

        self._servers[name] = {
            "transport": "stdio",
            "proc": proc,
            "config": McpServerConfig(name=name, transport="stdio", command=command, args=args),
        }

        # Initialize: send initialize request
        init_ok = await self._send_request(name, "initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "tangle-mcp", "version": "1.0.0"},
        })
        if not init_ok:
            logger.error(f"MCP server '{name}' initialize failed")
            await self.disconnect(name)
            return False

        # Notify initialized
        await self._send_notification(name, "notifications/initialized", {})

        # Discover tools
        await self._discover_tools(name)
        logger.info(f"MCP server '{name}' connected with stdio transport")
        return True

    async def connect_http(self, name: str, url: str,
                           headers: Optional[Dict[str, str]] = None) -> bool:
        """Connect to an MCP server via HTTP (Streamable HTTP) transport.

        Args:
            name: Unique server identifier.
            url: Server endpoint URL.
            headers: Optional HTTP headers.
        """
        if name in self._servers:
            logger.warning(f"MCP server '{name}' already connected")
            return False

        import httpx
        self._servers[name] = {
            "transport": "http",
            "http_url": url,
            "http_headers": headers or {},
            "http_client": httpx.AsyncClient(timeout=30),
            "config": McpServerConfig(name=name, transport="http", url=url, headers=headers or {}),
        }

        init_ok = await self._send_request(name, "initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "tangle-mcp", "version": "1.0.0"},
        })
        if not init_ok:
            logger.error(f"MCP HTTP server '{name}' initialize failed")
            await self.disconnect(name)
            return False

        await self._send_notification(name, "notifications/initialized", {})
        await self._discover_tools(name)
        logger.info(f"MCP server '{name}' connected via HTTP ({url})")
        return True

    async def disconnect(self, name: Optional[str] = None):
        """Disconnect a specific server or all servers."""
        targets = [name] if name else list(self._servers.keys())
        for srv in targets:
            server = self._servers.pop(srv, None)
            if server is None:
                continue
            if server["transport"] == "stdio" and server.get("proc"):
                proc = server["proc"]
                if proc.returncode is None:
                    try:
                        proc.terminate()
                        await asyncio.wait_for(proc.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        proc.kill()
                    except Exception:
                        pass
            elif server["transport"] == "http" and server.get("http_client"):
                await server["http_client"].aclose()

            # Remove tools from registry
            keys_to_remove = [k for k, v in self._tool_registry.items() if v[0] == srv]
            for k in keys_to_remove:
                del self._tool_registry[k]

        logger.info(f"Disconnected MCP servers: {targets}")

    def is_connected(self, name: str) -> bool:
        return name in self._servers

    @property
    def connected_servers(self) -> List[str]:
        return list(self._servers.keys())

    # ── Tool Discovery ─────────────────────────────────────────

    async def _discover_tools(self, server_name: str):
        """Fetch tool list from a server and register them."""
        result = await self._send_request(server_name, "tools/list", {})
        if not result:
            logger.warning(f"Failed to discover tools from '{server_name}'")
            return

        tools = result.get("tools", []) if isinstance(result, dict) else []
        count = 0
        for t in tools:
            name = t.get("name", "")
            desc = t.get("description", "")
            schema = t.get("inputSchema", {})
            if name:
                prefixed = f"{server_name}:{name}"
                self._tool_registry[prefixed] = (server_name, McpToolDef(name, desc, schema))
                count += 1

        logger.info(f"Discovered {count} tools from MCP server '{server_name}'")

    def list_tools(self, server_name: Optional[str] = None) -> List[McpToolDef]:
        """List available tools, optionally filtered by server."""
        if server_name:
            return [t for s, t in self._tool_registry.values() if s == server_name]
        return [t for _, t in self._tool_registry.values()]

    def get_tool_by_name(self, name: str) -> Optional[McpToolDef]:
        """Look up a tool by its prefixed name (server:tool)."""
        entry = self._tool_registry.get(name)
        return entry[1] if entry else None

    # ── Tool Execution ─────────────────────────────────────────

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool by its prefixed name (server:tool).

        Returns dict with 'content' (list of text/image resources) and 'isError'.
        """
        entry = self._tool_registry.get(tool_name)
        if not entry:
            return {"content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}], "isError": True}
        server_name, tool_def = entry
        return await self._call_server_tool(server_name, tool_def.name, arguments)

    # ── Internal MCP Protocol ──────────────────────────────────

    async def _send_request(self, server_name: str, method: str,
                            params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a JSON-RPC request and wait for response."""
        server = self._servers.get(server_name)
        if not server:
            return None

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

        if server["transport"] == "stdio":
            return await self._send_stdio_request(server, request)
        elif server["transport"] == "http":
            return await self._send_http_request(server, request)
        return None

    async def _send_notification(self, server_name: str, method: str,
                                 params: Dict[str, Any]):
        """Send a JSON-RPC notification (no response expected)."""
        server = self._servers.get(server_name)
        if not server:
            return

        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }

        if server["transport"] == "stdio":
            await self._write_stdio(server, request)
        elif server["transport"] == "http":
            try:
                await server["http_client"].post(
                    server["http_url"],
                    json=request,
                    headers={**server["http_headers"], "Content-Type": "application/json"},
                )
            except Exception as e:
                logger.warning(f"MCP notification failed for '{server_name}': {e}")

    async def _send_stdio_request(self, server: Dict, request: Dict) -> Optional[Dict]:
        """Send request over stdio and parse response."""
        await self._write_stdio(server, request)
        return await self._read_stdio_response(server, request["id"])

    async def _write_stdio(self, server: Dict, data: Dict):
        """Write JSON-RPC message to stdio with length header."""
        proc = server.get("proc")
        if not proc or not proc.stdin:
            return
        payload = json.dumps(data)
        header = f"Content-Length: {len(payload)}\r\n\r\n"
        proc.stdin.write((header + payload).encode())
        await proc.stdin.drain()

    async def _read_stdio_response(self, server: Dict, request_id: int) -> Optional[Dict]:
        """Read JSON-RPC response from stdio, matching by request_id."""
        proc = server.get("proc")
        if not proc or not proc.stdout:
            return None

        buffer = b""
        while True:
            try:
                chunk = await asyncio.wait_for(proc.stdout.read(4096), timeout=30)
            except asyncio.TimeoutError:
                logger.warning(f"MCP stdio read timeout (request {request_id})")
                return None

            if not chunk:
                return None

            buffer += chunk

            # Try to extract JSON-RPC response
            try:
                text = buffer.decode()
                # MCP uses headers like "Content-Length: N\r\n\r\n{json}"
                if "\r\n\r\n" in text:
                    _, body = text.split("\r\n\r\n", 1)
                    body = body.strip()
                    response = json.loads(body)
                    if response.get("id") == request_id:
                        return response.get("result")
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue

    async def _send_http_request(self, server: Dict, request: Dict) -> Optional[Dict]:
        """Send JSON-RPC over HTTP (Streamable HTTP)."""
        client = server.get("http_client")
        if not client:
            return None
        try:
            resp = await client.post(
                server["http_url"],
                json=request,
                headers={**server["http_headers"], "Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result")
            else:
                logger.warning(f"MCP HTTP error {resp.status_code} for '{request['method']}'")
                return None
        except Exception as e:
            logger.warning(f"MCP HTTP request failed: {e}")
            return None

    async def _call_server_tool(self, server_name: str, tool_name: str,
                                arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on a specific MCP server."""
        result = await self._send_request(server_name, "tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        if result is None:
            return {"content": [{"type": "text", "text": f"MCP call failed: {server_name}/{tool_name}"}], "isError": True}
        return result


# ── Global singleton ─────────────────────────────────────────────

_mcp_client: Optional[McpClient] = None


def get_mcp_client() -> McpClient:
    """Get or create the global MCP client singleton."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = McpClient()
    return _mcp_client


async def shutdown_mcp():
    """Disconnect all MCP servers (call on app shutdown)."""
    global _mcp_client
    if _mcp_client:
        await _mcp_client.disconnect()
        _mcp_client = None


# ── MCP Skill Adapter ────────────────────────────────────────────

MCP_SKILL_MAP: Dict[str, str] = {
    "filesystem": "filesystem",          # general skill
    "playwright": "playwright",          # browser automation
    "github": "github",                  # code/search
    "fetch": "fetch",                    # web fetch
    "sequentialthinking": "reasoning",   # structured reasoning
}


async def auto_connect_skill_mcps(mcp_client: McpClient):
    """Auto-connect MCP servers based on available executables and env config.

    Scans for common MCP servers and connects those with available commands.
    Reads MCP_SERVER_CONFIGS env var for custom server definitions.
    """
    config_json = os.getenv("TANGLE_MCP_SERVERS", "[]")
    try:
        configs = json.loads(config_json)
    except json.JSONDecodeError:
        configs = []

    for cfg in configs:
        name = cfg.get("name", "")
        transport = cfg.get("transport", "stdio")
        if not name:
            continue
        try:
            if transport == "stdio":
                await mcp_client.connect_stdio(
                    name=name,
                    command=cfg["command"],
                    args=cfg.get("args", []),
                    env=cfg.get("env"),
                )
            elif transport == "http":
                await mcp_client.connect_http(
                    name=name,
                    url=cfg["url"],
                    headers=cfg.get("headers"),
                )
        except Exception as e:
            logger.warning(f"Failed to auto-connect MCP server '{name}': {e}")

    logger.info(f"MCP auto-connect complete. Connected: {mcp_client.connected_servers}")
