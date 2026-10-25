"""File helpers that only touch a sandbox directory, plus a bash allow/deny gate."""

from __future__ import annotations

import difflib
import fnmatch
import re
import shutil
import subprocess
from pathlib import Path

SAFE_PREFIXES = (
    "ls",
    "pwd",
    "cat ",
    "head ",
    "tail ",
    "wc ",
    "echo ",
    "python ",
    "python3 ",
)

DESTRUCTIVE_PATTERNS = [
    (re.compile(r"\brm\s+(-[^\s]*r[^\s]*|--recursive)", re.I), "recursive deletion"),
    (re.compile(r"\bsudo\b|\bsu\b", re.I), "privilege escalation"),
    (re.compile(r"\bchmod\b|\bchown\b|\bchgrp\b", re.I), "permission/ownership change"),
    (re.compile(r"\bdd\b|\bmkfs\b|/dev/", re.I), "raw-device write"),
    (re.compile(r"\b(mkfs|fdisk|parted)\b", re.I), "filesystem creation"),
    (re.compile(r">\s*/(etc|usr|bin|sbin|boot|root)\b", re.I), "redirection to root path"),
]


class SandboxError(ValueError):
    pass


def _resolve(sandbox: Path, relative: str) -> Path:
    sandbox = sandbox.resolve()
    target = (sandbox / relative).resolve()
    if sandbox not in target.parents and target != sandbox:
        raise SandboxError(f"path escapes sandbox: {relative}")
    return target


def read_file(sandbox: Path, path: str, max_lines: int | None = None) -> dict:
    target = _resolve(sandbox, path)
    lines = target.read_text(encoding="utf-8").splitlines()
    if max_lines is not None:
        lines = lines[: max(0, max_lines)]
    return {"path": path, "lines": lines, "line_count": len(lines)}


def write_file(sandbox: Path, path: str, content: str) -> dict:
    target = _resolve(sandbox, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": path, "bytes": len(content.encode("utf-8"))}


def edit_file(sandbox: Path, path: str, old: str, new: str) -> dict:
    target = _resolve(sandbox, path)
    before = target.read_text(encoding="utf-8")
    if old not in before:
        raise SandboxError("old text not found")
    after = before.replace(old, new, 1)
    target.write_text(after, encoding="utf-8")
    diff = "".join(
        difflib.unified_diff(
            before.splitlines(True),
            after.splitlines(True),
            fromfile=path,
            tofile=path,
            n=2,
        )
    )
    return {"path": path, "diff": diff}


def glob_files(sandbox: Path, pattern: str = "**/*") -> dict:
    sandbox = sandbox.resolve()
    matches = sorted(
        str(path.relative_to(sandbox)) for path in sandbox.glob(pattern) if path.is_file()
    )
    return {"pattern": pattern, "files": matches}


def search_in_files(
    sandbox: Path,
    query: str,
    file_pattern: str = "**/*",
) -> dict:
    sandbox = sandbox.resolve()
    hits = []
    for path in sandbox.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(sandbox))
        if not fnmatch.fnmatch(rel, file_pattern) and not path.match(file_pattern):
            # also allow simple suffix patterns like *.py
            if not fnmatch.fnmatch(path.name, file_pattern):
                continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if query in line:
                hits.append({"path": rel, "line": lineno, "text": line.strip()})
    return {"query": query, "file_pattern": file_pattern, "hits": hits}


def is_destructive(command: str) -> bool:
    text = command or ""
    return any(pattern.search(text) for pattern, _ in DESTRUCTIVE_PATTERNS)


def destructive_reason(command: str) -> str | None:
    text = command or ""
    for pattern, label in DESTRUCTIVE_PATTERNS:
        if pattern.search(text):
            return label
    return None


def confirm_bash(command: str, auto_approve: bool = False) -> dict:
    """Return allow/block with a short reason. Pure Python; no model."""
    command = (command or "").strip()
    if not command:
        return {"allowed": False, "reason": "empty command"}

    reason = destructive_reason(command)
    if reason:
        if auto_approve:
            return {
                "allowed": True,
                "reason": f"destructive ({reason}) explicitly confirmed",
            }
        return {
            "allowed": False,
            "reason": f"blocked destructive command: {reason}",
        }

    if any(command == prefix.strip() or command.startswith(prefix) for prefix in SAFE_PREFIXES):
        return {"allowed": True, "reason": "matches SAFE_PREFIXES"}

    return {"allowed": False, "reason": "command not in SAFE_PREFIXES"}


def bash(sandbox: Path, command: str, auto_approve: bool = False) -> dict:
    gate = confirm_bash(command, auto_approve=auto_approve)
    if not gate["allowed"]:
        return {"ok": False, "gate": gate, "stdout": "", "stderr": gate["reason"]}
    completed = subprocess.run(
        command,
        shell=True,
        cwd=str(sandbox.resolve()),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return {
        "ok": completed.returncode == 0,
        "gate": gate,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "returncode": completed.returncode,
    }


def reset_sandbox(sandbox: Path) -> None:
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True, exist_ok=True)
