"""Call every tool on both MCP servers over STDIO and save the raw results to reports/hw05/raw/."""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
RAW = HERE.parents[1] / "reports" / "hw05" / "raw"

CALLS = {
    "meals_server.py": [
        ("search_meals_by_name", {"query": "Arrabiata", "limit": 5}),
        ("search_meals_by_name", {"query": "zzzz"}),
        ("meals_by_ingredient", {"ingredient": "chicken", "limit": 5}),
        ("random_meal", {}),
        ("meal_details", {"id": "52771"}),
        ("meal_details", {"id": "1"}),
    ],
    "domain_server.py": [
        ("search_inspections", {"query": "Sushi", "cuisine": "Japanese", "limit": 3}),
        ("search_inspections", {"query": "S", "limit": 100}),
        ("get_inspection", {"inspection_code": "INS-00042"}),
        ("get_inspection", {"inspection_code": "42"}),
        ("score_summary", {"group_by": "cuisine", "top": 3}),
        ("score_summary", {"group_by": "city", "top": 3}),
    ],
}


def _parse(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return text


async def call_all(server: str, calls: list) -> list[dict]:
    params = StdioServerParameters(command=sys.executable, args=[str(HERE / server)])
    records = []
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for name, args in calls:
                result = await session.call_tool(name, args)
                structured = result.structuredContent
                if isinstance(structured, dict) and set(structured) == {"result"}:
                    output = structured["result"]
                elif structured is not None:
                    output = structured
                else:
                    output = [_parse(c.text) for c in result.content if hasattr(c, "text")]
                    if len(output) == 1:
                        output = output[0]
                records.append({"tool": name, "input": args, "isError": result.isError, "output": output})
                print(f"{server:18} {name:22} {json.dumps(args):60} isError={result.isError}")
    return records


async def main():
    RAW.mkdir(parents=True, exist_ok=True)
    for server, calls in CALLS.items():
        records = await call_all(server, calls)
        out = RAW / f"mcp_{server.replace('_server.py', '')}_outputs.json"
        out.write_text(json.dumps({"recordedAt": datetime.now().isoformat(timespec="seconds"),
                                   "server": server, "calls": records}, indent=2))
        print(f"saved {out.relative_to(HERE.parents[1])}")


if __name__ == "__main__":
    asyncio.run(main())
