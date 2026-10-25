"""Run the sandbox file-tool demo and the allow/block bash checks."""

from pathlib import Path

from file_tools import (
    confirm_bash,
    glob_files,
    is_destructive,
    read_file,
    reset_sandbox,
    search_in_files,
    write_file,
)

ROOT = Path(__file__).resolve().parents[2]
SANDBOX = ROOT / "reports" / "hw07" / "raw" / "sandbox"


def integration_debug_search() -> dict:
    reset_sandbox(SANDBOX)
    write_file(SANDBOX, "alpha.py", "print('alpha')\n")
    write_file(SANDBOX, "beta.py", "DEBUG = True\nprint('beta')\n")
    write_file(SANDBOX, "gamma.py", "print('gamma')\n")
    found = glob_files(SANDBOX, "*.py")
    hits = search_in_files(SANDBOX, "DEBUG", file_pattern="*.py")
    target = hits["hits"][0]["path"]
    content = read_file(SANDBOX, target)
    return {
        "glob_files": found["files"],
        "search_hits": hits["hits"],
        "read_path": target,
        "read_lines": content["lines"],
    }


PASS_COMMANDS = [
    "ls",
    "pwd",
    "echo hello",
    "python3 -c 'print(1)'",
    "wc -l beta.py",
]

BLOCK_COMMANDS = [
    "rm -rf /tmp/demo",
    "sudo apt install evil",
    "chmod 777 /etc/passwd",
    "dd if=/dev/zero of=/dev/sda",
    "echo hacked > /etc/hosts",
]


def safety_gate_tests() -> list[dict]:
    rows = []
    for command in PASS_COMMANDS:
        gate = confirm_bash(command, auto_approve=False)
        rows.append(
            {
                "command": command,
                "expect": "allow",
                "destructive": is_destructive(command),
                "allowed": gate["allowed"],
                "reason": gate["reason"],
                "ok": gate["allowed"] is True,
            }
        )
    for command in BLOCK_COMMANDS:
        gate = confirm_bash(command, auto_approve=False)
        rows.append(
            {
                "command": command,
                "expect": "block",
                "destructive": is_destructive(command),
                "allowed": gate["allowed"],
                "reason": gate["reason"],
                "ok": gate["allowed"] is False and is_destructive(command),
            }
        )
    # False-allow check: a destructive command that starts with a safe prefix.
    tricky = "echo hi; rm -rf /var/tmp/x"
    gate = confirm_bash(tricky, auto_approve=False)
    rows.append(
        {
            "command": tricky,
            "expect": "block",
            "destructive": is_destructive(tricky),
            "allowed": gate["allowed"],
            "reason": gate["reason"],
            "ok": gate["allowed"] is False,
            "note": "false-allow candidate fixed by destructive deny-list",
        }
    )
    return rows


def main() -> None:
    print("Eric Zhao (SID4 1421) - file tools and safety gate")
    integration = integration_debug_search()
    print("integration glob -> search -> read")
    print(integration)
    assert "beta.py" in integration["glob_files"]
    assert integration["read_path"] == "beta.py"
    assert any("DEBUG" in line for line in integration["read_lines"])

    rows = safety_gate_tests()
    passed = sum(1 for row in rows if row["ok"])
    print(f"\nsafety gate {passed}/{len(rows)}")
    for row in rows:
        mark = "PASS" if row["ok"] else "FAIL"
        print(f"[{mark}] expect={row['expect']} allowed={row['allowed']} :: {row['command']}")
        print(f"       reason={row['reason']}")
    if passed != len(rows):
        raise SystemExit(1)
    print("all safety-gate checks passed")


if __name__ == "__main__":
    main()
