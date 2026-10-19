"""Consolidate the 55-line MEMORY.md and save both versions under reports/hw06.

Does not replace the root MEMORY.md, so /compact can still show the drop.
"""

import shutil
from datetime import datetime
from pathlib import Path

from backend_path import add_backend

add_backend()
from file_memory import MEMORY_PATH, consolidate_memory, content_line_count

ROOT = Path(__file__).resolve().parents[1]
HW06 = ROOT / "reports" / "hw06"
LOG = HW06 / "RUN_LOG.txt"


def main() -> None:
    original = MEMORY_PATH.read_text(encoding="utf-8")
    consolidated, before, after = consolidate_memory(original)
    HW06.mkdir(parents=True, exist_ok=True)
    (HW06 / "MEMORY_original.md").write_text(original, encoding="utf-8")
    (HW06 / "MEMORY_consolidated.md").write_text(consolidated, encoding="utf-8")
    file_lines = len(original.splitlines())
    print("Eric Zhao (SID4 1421)")
    print(f"MEMORY.md file lines: {file_lines}")
    print(f"content lines before: {before}")
    print(f"content lines after: {after}")
    print(f"saved {HW06 / 'MEMORY_original.md'}")
    print(f"saved {HW06 / 'MEMORY_consolidated.md'}")
    print("root MEMORY.md was left unchanged")
    wrong = [line for line in consolidated.splitlines() if line.startswith("- port_base:")]
    print("port_base line:", wrong[0] if wrong else "missing")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n[{stamp}] part 4 consolidation\n"
            f"file_lines={file_lines} content_before={before} content_after={after}\n"
            f"port_base kept: {wrong[0] if wrong else 'missing'}\n"
        )
    if file_lines != 55 or before <= 40 or after >= 40:
        raise SystemExit("consolidation counts were not in the required range")


if __name__ == "__main__":
    main()
