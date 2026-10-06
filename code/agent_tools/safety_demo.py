"""Part 5 safety rule demo: one allowed call and one blocked call through execute_tool."""

import json
import logging
import sys

from executor import execute_tool

logging.basicConfig(stream=sys.stderr, level=logging.CRITICAL)

CALLS = [
    ("allowed", "search_inspections", {"query": "Taqueria", "cuisine": "Mexican", "limit": 2}),
    ("blocked", "search_inspections", {"query": "kevin.brooks@example.com"}),
    ("blocked", "search_inspections", {"query": "408-586-5719"}),
]


def main():
    print("Eric Zhao (SID4 1421) - safety rule: no owner emails or phone numbers in tool inputs\n")
    for label, tool, inputs in CALLS:
        print(f"[{label}] execute_tool({tool!r}, {json.dumps(inputs)})")
        print("   ->", execute_tool(tool, inputs), "\n")


if __name__ == "__main__":
    main()
