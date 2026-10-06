"""MCP server "inspections": search, detail lookup and one aggregate over s1421_rel.

Run with the MCP Inspector:  mcp dev code/agent_tools/domain_server.py
Parameters are typed loosely on purpose so that out-of-range values reach the shared
validator and come back as {"ok": false, "data": null, "error": "..."} instead of a protocol error.
"""

import logging
import sys
from functools import lru_cache
from pathlib import Path

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent))
from domain_tools import MySQLRepository, run_tool  # noqa: E402

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

mcp = FastMCP("inspections")


@lru_cache(maxsize=1)
def repo() -> MySQLRepository:
    return MySQLRepository()


@mcp.tool()
def search_inspections(query: str, cuisine: str | None = None, limit: int = 10) -> dict:
    """Search inspections by part of the restaurant name (2-100 chars).
    Optional exact cuisine filter; limit 1-25 (default 10)."""
    inputs = {"query": query, "limit": limit}
    if cuisine is not None:
        inputs["cuisine"] = cuisine
    return run_tool("search_inspections", inputs, repo())


@mcp.tool()
def get_inspection(inspection_code: str) -> dict:
    """Full details of one inspection by its unique code (format INS-12345):
    restaurant, cuisine, score, owner and violations."""
    return run_tool("get_inspection", {"inspection_code": inspection_code}, repo())


@mcp.tool()
def score_summary(group_by: str, top: int = 5) -> dict:
    """Aggregate inspection scores grouped by "cuisine" or "owner".
    Returns the `top` (1-20, default 5) lowest-scoring groups with count, average and minimum score."""
    return run_tool("score_summary", {"group_by": group_by, "top": top}, repo())


if __name__ == "__main__":
    mcp.run(transport="stdio")
