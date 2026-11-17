#!/usr/bin/env python3
"""
Agent Substrate (ate) MCP Server
Exposes GKE Agent Substrate sandbox execution and lifecycle controls as MCP tools.
"""

import json
import os
import socket
import subprocess
import time
from typing import Any, Dict

import httpx
try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

mcp = MCPServer("ate-sandbox")
mcp_tool = mcp.tool

ATE_ENDPOINT = os.getenv("ATE_ENDPOINT", "127.0.0.1:18443")
SANDBOX_URL = os.getenv("SANDBOX_URL", "http://127.0.0.1:18880")
DEFAULT_ACTOR = os.getenv("ATE_ACTOR", "agy-sandbox")
DEFAULT_TEMPLATE = os.getenv("ATE_TEMPLATE", "python-sandbox-template")
DEFAULT_ACCOUNT = os.getenv("ATE_ACCOUNT", "default")


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def _ensure_infra_ready() -> None:
    """Ensures ate-api port-forward and actor proxy are running if ports are closed."""
    # 1. Check ate-api port-forward on 18443
    if not _is_port_open("127.0.0.1", 18443):
        subprocess.Popen(
            ["kubectl", "port-forward", "-n", "ate-system", "svc/api", "18443:443"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(20):
            time.sleep(0.5)
            if _is_port_open("127.0.0.1", 18443):
                break

    # 2. Check actor proxy on 18880
    if not _is_port_open("127.0.0.1", 18880):
        # Ensure actor exists & is resumed
        subprocess.run(
            [
                "kubectl", "ate", "--endpoint", ATE_ENDPOINT,
                "resume", "actor", DEFAULT_ACTOR, "-a", DEFAULT_ACCOUNT
            ],
            capture_output=True,
            text=True,
        )
        # Start proxy
        subprocess.Popen(
            [
                "kubectl", "ate", "--endpoint", ATE_ENDPOINT,
                "proxy", "actor", DEFAULT_ACTOR, "18880:8080", "-a", DEFAULT_ACCOUNT
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(20):
            time.sleep(0.5)
            if _is_port_open("127.0.0.1", 18880):
                break


@mcp_tool()
async def execute_code(code: str) -> Dict[str, Any]:
    """
    Execute a Python code snippet inside the persistent MicroVM sandbox.
    Variables and state persist across calls.

    Args:
        code: The Python code snippet to execute.

    Returns:
        A dictionary containing stdout, stderr, and exit_code.
    """
    _ensure_infra_ready()
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{SANDBOX_URL}/execute",
                json={"code": code},
                timeout=60.0,
            )
            return resp.json()
        except httpx.ConnectError:
            # Retry once after re-checking infra
            _ensure_infra_ready()
            resp = await client.post(
                f"{SANDBOX_URL}/execute",
                json={"code": code},
                timeout=60.0,
            )
            return resp.json()


@mcp_tool()
async def get_sandbox_state() -> Dict[str, Any]:
    """
    Inspect the MicroVM sandbox status, hostname, python version,
    and active in-memory global variables.

    Returns:
        Dictionary with status, hostname, python_version, and active_variables list.
    """
    _ensure_infra_ready()
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{SANDBOX_URL}/", timeout=10.0)
        return resp.json()


@mcp_tool()
def suspend_sandbox(actor_name: str = DEFAULT_ACTOR) -> str:
    """
    Suspend the MicroVM sandbox to release compute resources while
    preserving its exact memory snapshot.

    Args:
        actor_name: Name of the actor to suspend (default: agy-sandbox).
    """
    res = subprocess.run(
        ["kubectl", "ate", "--endpoint", ATE_ENDPOINT, "suspend", "actor", actor_name, "-a", DEFAULT_ACCOUNT],
        capture_output=True,
        text=True,
    )
    return res.stdout.strip() if res.returncode == 0 else f"Error: {res.stderr.strip()}"


@mcp_tool()
def resume_sandbox(actor_name: str = DEFAULT_ACTOR) -> str:
    """
    Resume the MicroVM sandbox from its memory snapshot.

    Args:
        actor_name: Name of the actor to resume (default: agy-sandbox).
    """
    res = subprocess.run(
        ["kubectl", "ate", "--endpoint", ATE_ENDPOINT, "resume", "actor", actor_name, "-a", DEFAULT_ACCOUNT],
        capture_output=True,
        text=True,
    )
    # Ensure proxy is up
    if not _is_port_open("127.0.0.1", 18880):
        subprocess.Popen(
            [
                "kubectl", "ate", "--endpoint", ATE_ENDPOINT,
                "proxy", "actor", actor_name, "18880:8080", "-a", DEFAULT_ACCOUNT
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return res.stdout.strip() if res.returncode == 0 else f"Error: {res.stderr.strip()}"


@mcp_tool()
def revert_sandbox(actor_name: str = DEFAULT_ACTOR) -> str:
    """
    Revert the MicroVM sandbox back to its clean initial state.

    Args:
        actor_name: Name of the actor to revert (default: agy-sandbox).
    """
    res = subprocess.run(
        ["kubectl", "ate", "--endpoint", ATE_ENDPOINT, "revert", "actor", actor_name, "-a", DEFAULT_ACCOUNT],
        capture_output=True,
        text=True,
    )
    return res.stdout.strip() if res.returncode == 0 else f"Error: {res.stderr.strip()}"


if __name__ == "__main__":
    mcp.run()
