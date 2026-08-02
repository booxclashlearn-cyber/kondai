import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MCPToolResult:
    content: list[dict]
    is_error: bool = False


class MCPTransport(Protocol):
    async def request(self, method: str, params: dict, timeout: float) -> dict: ...


class MCPClient(ABC):
    @abstractmethod
    async def readiness(self) -> tuple[str, str]: ...

    @abstractmethod
    async def clickhouse_health(self) -> MCPToolResult: ...


class DisabledMCPClient(MCPClient):
    async def readiness(self) -> tuple[str, str]:
        return "not_configured", "CLICKHOUSE_MCP_COMMAND is not set"

    async def clickhouse_health(self) -> MCPToolResult:
        raise RuntimeError("ClickHouse MCP is not configured")


class ProcessTransport:
    """MCP stdio JSON-RPC transport; never accepts SQL from browser clients."""

    def __init__(self, command: str, args: list[str]):
        self.command, self.args = command, args

    async def request(self, method: str, params: dict, timeout: float) -> dict:
        process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        try:
            stdout, _ = await asyncio.wait_for(
                process.communicate((json.dumps(request) + "\n").encode()), timeout
            )
        except TimeoutError:
            process.kill()
            raise RuntimeError("MCP request timed out") from None
        if process.returncode != 0:
            raise RuntimeError("MCP server process failed")
        response = json.loads(stdout.decode().splitlines()[-1])
        if "error" in response:
            raise RuntimeError("MCP server returned an error")
        return response["result"]


class StdioMCPClient(MCPClient):
    def __init__(self, transport: MCPTransport, timeout: float = 10):
        self.transport, self.timeout = transport, timeout

    async def readiness(self) -> tuple[str, str]:
        try:
            result = await self.clickhouse_health()
            return (
                ("degraded", "Health tool returned an error")
                if result.is_error
                else ("ready", "MCP health tool available")
            )
        except Exception:
            return "unavailable", "MCP health probe failed"

    async def clickhouse_health(self) -> MCPToolResult:
        result = await self.transport.request(
            "tools/call", {"name": "echocut_clickhouse_health", "arguments": {}}, self.timeout
        )
        return MCPToolResult(
            content=result.get("content", []), is_error=result.get("isError", False)
        )
