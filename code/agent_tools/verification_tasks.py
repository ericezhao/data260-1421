"""Fixed prompts used by the Part 2 and Part 3 agent runs."""

TASKS = [
    {
        "id": "A",
        "title": "Search then detail the first result",
        "prompt": (
            "Search inspections for restaurants with Sushi in the name (limit 5). "
            "Then call get_inspection on the first inspection_code from that search "
            "and report the restaurant name, score, and violation count."
        ),
        "min_tool_calls": 2,
        "required_tools": ["search_inspections", "get_inspection"],
    },
    {
        "id": "B",
        "title": "Aggregate then one supporting example",
        "prompt": (
            "Which cuisine has the lowest average inspection score? "
            "Use score_summary grouped by cuisine with top 3, then search for one "
            "restaurant in that cuisine and report its inspection_code and score."
        ),
        "min_tool_calls": 2,
        "required_tools": ["score_summary", "search_inspections"],
    },
    {
        "id": "C",
        "title": "Compare two entities",
        "prompt": (
            "Search for restaurants with Sushi in the name (limit 5). "
            "Then get_inspection for the first and second inspection_code in that "
            "list and say which of the two has the lower score."
        ),
        "min_tool_calls": 3,
        "required_tools": ["search_inspections", "get_inspection"],
    },
]

ERROR_RECOVERY = {
    "id": "E",
    "title": "Nonexistent inspection code",
    "prompt": (
        "Get details for inspection INS-99999 and tell me what happened. "
        "Do not invent a restaurant."
    ),
}
