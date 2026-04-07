"""
scc/mcp/__init__.py — MCP 服务器加载入口
=========================================
对应 Claude Code 源码:
  src/services/mcp/ → MCPServerManager / assembleToolPool MCP 部分

load_mcp_servers(cwd) 读取 mcp.json，启动所有配置的服务器，
返回 (tools, clients) 供 QueryEngine 和 CLI 使用。
"""

from __future__ import annotations
import json
import os

from .client import MCPClient, MCPError
from .tool import MCPTool


def load_mcp_servers(cwd: str) -> tuple[list[MCPTool], list[MCPClient]]:
    """
    读取 <cwd>/mcp.json，为每个服务器启动子进程并发现工具。

    返回 (mcp_tools, mcp_clients):
      - mcp_tools:   所有成功加载的 MCPTool 实例（传给 QueryEngine）
      - mcp_clients: 所有活跃的 MCPClient 实例（程序退出时调用 close()）

    如果 mcp.json 不存在，静默返回 ([], [])。
    服务器启动失败时打印警告并跳过，不影响其他服务器。
    """
    config_path = os.path.join(cwd, "mcp.json")
    if not os.path.exists(config_path):
        return [], []

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  WARNING: Cannot read mcp.json: {e}")
        return [], []

    if not isinstance(config, dict):
        print("  WARNING: mcp.json root is not a JSON object, skipping.")
        return [], []

    servers: dict[str, dict] = config.get("mcpServers", {})
    if not servers:
        return [], []

    all_tools: list[MCPTool] = []
    all_clients: list[MCPClient] = []

    for server_name, server_cfg in servers.items():
        if not isinstance(server_cfg, dict):
            print(f"  WARNING: MCP server '{server_name}' config is not a dict, skipping.")
            continue
        command: str = server_cfg.get("command", "")
        args: list[str] = server_cfg.get("args", [])
        env: dict[str, str] = server_cfg.get("env", {})

        if not command:
            print(f"  WARNING: MCP server '{server_name}' has no 'command', skipping.")
            continue

        client = MCPClient(server_name=server_name, command=command, args=args, env=env)
        try:
            client.connect()
            raw_tools = client.list_tools()
            server_tools = [
                MCPTool(client=client, server_name=server_name, tool_def=td)
                for td in raw_tools
            ]
            all_tools.extend(server_tools)
            all_clients.append(client)
            print(f"  MCP '{server_name}': {len(server_tools)} tool(s) loaded")
        except Exception as e:
            print(f"  WARNING: MCP server '{server_name}' failed: {e}")
            try:
                client.close()
            except Exception:
                pass

    return all_tools, all_clients


__all__ = ["load_mcp_servers", "MCPClient", "MCPTool", "MCPError"]
