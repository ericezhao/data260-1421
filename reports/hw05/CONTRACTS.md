# HW5 Part 3 - Tool contracts

Server: `code/agent_tools/domain_server.py` (MCP name `inspections`). Validation lives in `code/agent_tools/domain_tools.py` (Pydantic models `SearchInput`, `DetailInput`, `SummaryInput`); the schemas below are generated from those models with `model_json_schema()`.

Every tool returns the same envelope: `{"ok": bool, "data": object | null, "error": string | null}`. On a rejected call `ok` is `false`, `data` is `null`, and `error` names each field that failed. Validation runs before any database access, so a rejected call never reaches MySQL.

The rejected calls are the Part 2B MCP Inspector examples; raw outputs are in `raw/mcp_domain_outputs.json`.

## 1. `search_inspections`

Expected input schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["query"],
  "properties": {
    "query":   {"type": "string", "minLength": 2, "maxLength": 100, "description": "Part of a restaurant name"},
    "cuisine": {"anyOf": [{"type": "string", "maxLength": 50}, {"type": "null"}], "default": null},
    "limit":   {"type": "integer", "minimum": 1, "maximum": 25, "default": 10}
  }
}
```

Rejected input:

```json
{"query": "S", "limit": 100}
```

Returned output:

```json
{"ok": false, "data": null, "error": "invalid input: query: String should have at least 2 characters; limit: Input should be less than or equal to 25"}
```

Why: two rules fail at once and both are reported. A one-character query matches almost every restaurant name, so `minLength: 2` stops accidental full-table scans. `limit` is capped at 25 so one call cannot dump thousands of rows into the agent's context.

## 2. `get_inspection`

Expected input schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["inspection_code"],
  "properties": {
    "inspection_code": {"type": "string", "pattern": "^INS-\\d{5}$", "description": "Unique code such as INS-00042"}
  }
}
```

Rejected input:

```json
{"inspection_code": "42"}
```

Returned output:

```json
{"ok": false, "data": null, "error": "invalid input: inspection_code: String should match pattern '^INS-\\d{5}$'"}
```

Why: the lookup key is the unique `inspection_code` column, not the numeric row id. `"42"` does not match the `INS-` + 5 digits format, so it is rejected before the query instead of silently returning "not found". A well-formed code that does not exist (for example `INS-99999`) passes validation and returns `{"ok": false, "error": "inspection INS-99999 not found"}` instead.

## 3. `score_summary`

Expected input schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["group_by"],
  "properties": {
    "group_by": {"type": "string", "enum": ["cuisine", "owner"]},
    "top":      {"type": "integer", "minimum": 1, "maximum": 20, "default": 5}
  }
}
```

Rejected input:

```json
{"group_by": "city", "top": 3}
```

Returned output:

```json
{"ok": false, "data": null, "error": "invalid input: group_by: Input should be 'cuisine' or 'owner'"}
```

Why: `group_by` is an enum because it picks a column to `GROUP BY`. The data has no `city` column, and accepting free text here would mean building SQL from user input. Only the two whitelisted groupings are allowed.

## Shared rules

- `additionalProperties: false`: unknown keys (for example `{"query": "Sushi", "drop": true}`) are rejected with `invalid input: drop: Extra inputs are not permitted`.
- Unknown tool names return `unknown tool '<name>'` with the list of available tools.
- Storage failures are retried (Part 3 policy) and, if every attempt fails, return `storage unavailable after 3 attempts: <last error>` instead of raising.
- `execute_tool` (Part 4) adds the Part 5 safety rule on top: inputs containing an email address or phone number return `blocked by safety rule: ...` without calling storage.
