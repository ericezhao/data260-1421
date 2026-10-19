import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_PATH = ROOT / "AGENT.md"
MEMORY_PATH = ROOT / "MEMORY.md"

KEY_RE = re.compile(r"^- ([a-z0-9_]+): (.+)$")
STAMP_RE = re.compile(r"consolidated:\s*([0-9T:\-+Z]+)")


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def content_lines(text: str) -> list[str]:
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("<!--") or stripped.startswith(">"):
            continue
        kept.append(line.rstrip())
    return kept


def content_line_count(text: str) -> int:
    return len(content_lines(text))


def last_consolidated_at(text: str) -> datetime | None:
    match = STAMP_RE.search(text)
    if not match:
        return None
    raw = match.group(1).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def consolidation_due(text: str, now: datetime | None = None) -> bool:
    if content_line_count(text) > 40:
        return True
    stamped = last_consolidated_at(text)
    if stamped is None:
        return True
    current = now or datetime.now(timezone.utc)
    return current - stamped > timedelta(hours=24)


def consolidate_memory(text: str, now: datetime | None = None) -> tuple[str, int, int]:
    """Merge duplicate facts and write an explicit line for every conflict."""
    before = content_line_count(text)
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    extras: list[str] = []
    for line in content_lines(text):
        if line.startswith("#") or line.startswith("- resolved "):
            continue
        match = KEY_RE.match(line)
        if not match:
            extras.append(line)
            continue
        key, value = match.group(1), match.group(2).strip()
        if key not in grouped:
            order.append(key)
            grouped[key] = []
        if value not in grouped[key]:
            grouped[key].append(value)

    current = now or datetime.now(timezone.utc)
    out = [f"<!-- consolidated: {_stamp(current)} -->", "# Durable facts"]
    resolutions = []
    for key in order:
        values = grouped[key]
        kept = values[-1]
        out.append(f"- {key}: {kept}")
        if len(values) > 1:
            dropped = ", ".join(f'"{item}"' for item in values[:-1])
            resolutions.append(f'- resolved {key}: kept "{kept}" and dropped {dropped}.')
    out.extend(resolutions)
    out.extend(extras)
    rendered = "\n".join(out) + "\n"
    return rendered, before, content_line_count(rendered)


def load_file_memory() -> str:
    agent = AGENT_PATH.read_text(encoding="utf-8").strip() if AGENT_PATH.exists() else ""
    memory = MEMORY_PATH.read_text(encoding="utf-8").strip() if MEMORY_PATH.exists() else ""
    return f"AGENT.md\n{agent}\n\nMEMORY.md\n{memory}"


def memory_text() -> str:
    if not MEMORY_PATH.exists():
        return ""
    return MEMORY_PATH.read_text(encoding="utf-8")


def write_memory(text: str) -> None:
    MEMORY_PATH.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def compact_memory() -> tuple[int, int]:
    text = memory_text()
    updated, before, after = consolidate_memory(text)
    write_memory(updated)
    return before, after


def append_learned(facts: list[str]) -> int:
    text = memory_text().rstrip()
    fresh = []
    for fact in facts:
        line = f"- Learned fact: {fact.strip()}"
        if fact.strip() and line not in text:
            fresh.append(line)
    if not fresh:
        return 0
    write_memory(text + "\n" + "\n".join(fresh) + "\n")
    return len(fresh)


def help_text() -> str:
    return "\n".join([
        "/memory shows AGENT.md and MEMORY.md.",
        "/compact merges duplicate facts in MEMORY.md and reports the content-line count before and after.",
        "/dream adds useful facts from recent episodic memory into MEMORY.md.",
        "/help lists these commands.",
    ])
