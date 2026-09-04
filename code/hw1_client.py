import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model_client import OllamaModelClient


def serialized_history_length(messages: list[dict[str, str]]) -> int:
    serialized = json.dumps(
        messages,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return len(serialized.encode("utf-8"))


def is_bullet_only(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return bool(lines) and all(line.startswith("- ") for line in lines)


class ConversationSession:
    def __init__(self, client: OllamaModelClient, system_prompt: str) -> None:
        self.client = client
        self.system_prompt = system_prompt
        self.conversation: list[dict[str, str]] = []
        self.turn_records: list[dict[str, Any]] = []
        self.stats_snapshots: list[dict[str, Any]] = []
        self.cumulative_input_tokens = 0
        self.cumulative_output_tokens = 0

    @property
    def turn_count(self) -> int:
        return len(self.turn_records)

    def messages(self) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.system_prompt},
            *self.conversation,
        ]

    def stats(self) -> dict[str, Any]:
        return {
            "turn_count": self.turn_count,
            "cumulative_input_tokens": self.cumulative_input_tokens,
            "cumulative_output_tokens": self.cumulative_output_tokens,
            "serialized_history_length_bytes": serialized_history_length(
                self.messages()
            ),
            "history_message_count": len(self.messages()),
        }

    def show_stats(self, label: str = "/stats") -> dict[str, Any]:
        snapshot = {"label": label, **self.stats()}
        self.stats_snapshots.append(snapshot)
        print(f"\n{label}")
        print(f"turn_count: {snapshot['turn_count']}")
        print(
            "cumulative_tokens: "
            f"input={snapshot['cumulative_input_tokens']}, "
            f"output={snapshot['cumulative_output_tokens']}"
        )
        print(
            "serialized_history_length_bytes: "
            f"{snapshot['serialized_history_length_bytes']}"
        )
        print(f"history_message_count: {snapshot['history_message_count']}")
        return snapshot

    def complete_turn(self, user_message: str) -> None:
        self.conversation.append({"role": "user", "content": user_message})
        response = self.client.complete(self.messages())
        self.conversation.append({"role": "assistant", "content": response.content})

        self.cumulative_input_tokens += response.input_tokens
        self.cumulative_output_tokens += response.output_tokens
        bullet_only = is_bullet_only(response.content)
        record = {
            "turn": self.turn_count + 1,
            "user_message": user_message,
            "assistant_message": response.content,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "bullet_only": bullet_only,
            "serialized_history_length_bytes_after_turn": serialized_history_length(
                self.messages()
            ),
        }
        self.turn_records.append(record)

        print(f"\nassistant (turn {record['turn']}):")
        print(response.content)
        print(
            "tokens: "
            f"input={response.input_tokens}, "
            f"output={response.output_tokens}, "
            f"total={response.total_tokens}"
        )
        print(f"bullet_only_check: {'PASS' if bullet_only else 'FAIL'}")

    def save_results(self, path: Path, model: str) -> None:
        payload = {
            "model": model,
            "system_prompt_file": "AGENT.md",
            "turn_records": self.turn_records,
            "stats_snapshots": self.stats_snapshots,
            "final_stats": self.stats(),
            "conversation": self.conversation,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_script(path: Path) -> list[str]:
    messages = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(messages, list) or not all(
        isinstance(message, str) and message.strip() for message in messages
    ):
        raise ValueError("Script file must contain a JSON array of non-empty strings")
    return messages


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.environ.get("SMOL_MODEL", "qwen3:8b"))
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--agent", default="AGENT.md")
    parser.add_argument("--script")
    parser.add_argument("--stats-after", type=int, nargs="*", default=[])
    parser.add_argument("--json-output")
    args = parser.parse_args()

    agent_path = (PROJECT_ROOT / args.agent).resolve()
    system_prompt = agent_path.read_text(encoding="utf-8").strip()
    client = OllamaModelClient(
        model=args.model,
        base_url=args.base_url,
        temperature=args.temperature,
    )
    session = ConversationSession(client, system_prompt)

    if args.script:
        script_path = (PROJECT_ROOT / args.script).resolve()
        for message in load_script(script_path):
            print(f"\nuser: {message}")
            session.complete_turn(message)
            if session.turn_count in set(args.stats_after):
                session.show_stats(f"/stats after turn {session.turn_count}")
    else:
        print("Commands: /stats, /exit")
        while True:
            try:
                message = input("\nuser: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not message:
                continue
            if message == "/exit":
                break
            if message == "/stats":
                session.show_stats()
                continue
            session.complete_turn(message)

    print("\nexit totals")
    print(f"turn_count: {session.turn_count}")
    print(f"cumulative_input_tokens: {session.cumulative_input_tokens}")
    print(f"cumulative_output_tokens: {session.cumulative_output_tokens}")

    if args.json_output:
        output_path = (PROJECT_ROOT / args.json_output).resolve()
        session.save_results(output_path, args.model)
        print(f"saved_results: {output_path}")


if __name__ == "__main__":
    main()
