import argparse, json, os, re, sys, time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Iterable, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.model_client import OllamaModelClient


STOP = {
    "the", "and", "for", "that", "with", "this", "from", "into", "than", "your", "you",
    "are", "was", "were", "have", "has", "had", "use", "used", "using", "about", "how",
    "can", "will", "more", "less", "very", "over", "under", "their", "there", "then",
    "our", "out", "on", "in", "of", "to", "by", "a", "an", "is", "it", "as",
}



def strip_code_and_md(s: str) -> str:
    text = str(s)

    for lang in ("json", "javascript", "python", "text"):
        text = text.replace(f"```{lang}", "")
        text = text.replace(f"```{lang.upper()}", "")
    text = text.replace("```", "").replace("`", "")

    cleaned_lines = []
    for line in text.splitlines():
        line = line.lstrip()
        while line.startswith("#"):
            line = line.lstrip("#").lstrip()
        if line.startswith(("- ", "* ", "+ ")):
            line = line[2:]
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)
    return " ".join(text.split())


def extract_json_block(text: str) -> str:
    text = str(text).strip()

    for start, char in enumerate(text):
        if char != "{":
            continue

        depth = 0
        in_string = False
        escaped = False

        for end in range(start, len(text)):
            current = text[end]

            if in_string:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    in_string = False
                continue

            if current == '"':
                in_string = True
            elif current == "{":
                depth += 1
            elif current == "}":
                depth -= 1
                if depth == 0:
                    return text[start:end + 1]

    return json.dumps({"message": strip_code_and_md(text)}, ensure_ascii=False)




def tokens(txt: str) -> List[str]:
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(txt).lower())


def ngrams(words: List[str], n: int) -> Iterable[Tuple[str, ...]]:
    for i in range(max(0, len(words) - n + 1)):
        yield tuple(words[i:i + n])


def phrase_candidates(title: str, content: str, maxn: int = 12) -> List[str]:
    title_words = [word for word in tokens(title) if word not in STOP and len(word) > 1]
    content_words = [word for word in tokens(content) if word not in STOP and len(word) > 1]
    all_words = title_words + content_words

    if not all_words or maxn <= 0:
        return []

    counts: Counter[str] = Counter()
    first_seen: Dict[str, int] = {}
    title_phrases = set()

    position = 0
    for word_list, is_title in ((title_words, True), (content_words, False)):
        for size in (3, 2):
            for group in ngrams(word_list, size):
                phrase = " ".join(group)
                counts[phrase] += 1
                first_seen.setdefault(phrase, position)
                position += 1
                if is_title:
                    title_phrases.add(phrase)

    ranked_phrases = sorted(
        counts,
        key=lambda phrase: (
            -(counts[phrase] + (1 if phrase in title_phrases else 0)),
            -len(phrase.split()),
            first_seen[phrase],
        ),
    )

    candidates: List[str] = []
    for candidate in ranked_phrases:
        if candidate not in candidates:
            candidates.append(candidate)
        if len(candidates) >= maxn:
            return candidates

    unigram_counts = Counter(all_words)
    first_word_position = {word: all_words.index(word) for word in set(all_words)}
    ranked_words = sorted(
        unigram_counts,
        key=lambda word: (-unigram_counts[word], first_word_position[word]),
    )
    for word in ranked_words:
        if word not in candidates:
            candidates.append(word)
        if len(candidates) >= maxn:
            break

    return candidates



def coerce_reply(raw_obj: Any, title: str, content: str, strict: bool) -> Dict[str, Any]:
    obj = raw_obj if isinstance(raw_obj, dict) else {}
    raw_data = obj.get("data", {})
    data = raw_data if isinstance(raw_data, dict) else {}

    def clean_and_limit(value: Any, limit: int) -> str:
        cleaned = strip_code_and_md(value)
        return " ".join(cleaned.split()[:limit])

    thought = clean_and_limit(obj.get("thought", ""), 60)
    message = clean_and_limit(obj.get("message", ""), 60)
    if not message:
        message = "Proposal reviewed; tags and summary prepared."

    source_token_set = set(tokens(f"{title} {content}"))
    candidates = phrase_candidates(title, content, maxn=30)

    raw_tags = data.get("tags", obj.get("tags", []))
    if isinstance(raw_tags, str):
        raw_tags = re.split(r"[,;|]", raw_tags)
    if not isinstance(raw_tags, list):
        raw_tags = []

    tags: List[str] = []
    for raw_tag in raw_tags:
        tag = strip_code_and_md(raw_tag).strip(" -.,:;[]\"'").lower()
        tag_tokens = tokens(tag)
        grounded_count = sum(token in source_token_set for token in tag_tokens)
        minimum_grounded = (len(tag_tokens) + 1) // 2
        is_grounded = (
            bool(tag_tokens)
            and len(tag_tokens) <= 5
            and grounded_count >= minimum_grounded
        )
        if is_grounded and tag not in tags:
            tags.append(tag)

    preferred_candidates = candidates
    if strict:
        preferred_candidates = (
            [item for item in candidates if len(item.split()) > 1]
            + [item for item in candidates if len(item.split()) == 1]
        )

    for candidate in preferred_candidates:
        if candidate not in tags:
            tags.append(candidate)
        if len(tags) == 3:
            break

    if strict and len(tags) >= 3 and sum(len(tag.split()) > 1 for tag in tags[:3]) < 2:
        multiword = [item for item in candidates if len(item.split()) > 1]
        for candidate in multiword:
            if candidate in tags[:3]:
                continue
            replace_at = next(
                (index for index in range(2, -1, -1) if len(tags[index].split()) == 1),
                None,
            )
            if replace_at is None:
                break
            tags[replace_at] = candidate
            if sum(len(tag.split()) > 1 for tag in tags[:3]) >= 2:
                break

    if len(tags) < 3:
        raise ValueError("The title and content must contain enough topical words to create three tags.")
    tags = tags[:3]

    summary_value = data.get("summary", obj.get("summary", ""))
    summary = strip_code_and_md(summary_value).replace("...", "").replace("…", "")
    if not summary:
        summary = strip_code_and_md(content or title)
    summary_words = summary.split()[:25]
    summary = " ".join(summary_words).rstrip(" ,;:-.!?") + "."

    raw_issues = data.get("issues", obj.get("issues", []))
    if isinstance(raw_issues, str):
        raw_issues = [raw_issues]
    if not isinstance(raw_issues, list):
        raw_issues = []
    issues = []
    for item in raw_issues:
        issue = clean_and_limit(item, 25)
        if issue and issue not in issues:
            issues.append(issue)

    return {
        "thought": thought,
        "message": message,
        "data": {"tags": tags, "summary": summary, "issues": issues},
    }


def parse_and_coerce(text: str, title: str, content: str, strict: bool) -> Dict[str, Any]:
    try:
        obj = json.loads(extract_json_block(text))
    except Exception:
        obj = {"message": strip_code_and_md(text)}
    return coerce_reply(obj, title, content, strict)



@dataclass
class SimpleAgent:
    name: str
    system: str
    model: OllamaModelClient

    def respond(
        self,
        conversation: List[Dict[str, str]],
        task: str,
        title: str,
        content: str,
        strict: bool,
    ) -> Dict[str, Any]:
        history_text = "\n".join([f'{m["role"]}: {m["content"]}' for m in conversation]) or "(empty)"
        human_prompt = (
            f"Task:\n{task}\n\nTitle:\n{title}\n\nContent:\n{content}\n\n"
            f"Conversation so far:\n{history_text}\n\n"
            "Return ONLY one JSON object (no code fences, no markdown, no explanations). "
            "Keys: thought (string), message (non-empty, <=60 words, no code), "
            "data.tags (array of exactly 3 topical tags), "
            "data.summary (<=25 words, no ellipses), data.issues (array).\n"
            "Do not add extra text outside JSON."
        )
        response = self.model.complete([
            {"role": "system", "content": self.system},
            {"role": "user", "content": human_prompt},
        ])
        return parse_and_coerce(response.content, title, content, strict)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="Untitled")
    ap.add_argument("--content", default="No content provided.")
    ap.add_argument("--email", default="student@example.com")
    ap.add_argument("--model", default=os.environ.get("SMOL_MODEL", "qwen3:8b"))
    ap.add_argument("--base_url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    if not 0.0 <= args.temperature <= 2.0:
        ap.error("--temperature must be between 0.0 and 2.0")

    try:
        llm = OllamaModelClient(
            model=args.model,
            temperature=args.temperature,
            base_url=args.base_url,
            num_ctx=2048,
            num_predict=256,
            reasoning=False,
            keep_alive="30m",
            output_format="json",
        )
    except Exception:
        print(
            "Failed to initialize the Ollama model client. Is Ollama running and the model available?\n"
            "Try: `ollama serve` and `ollama pull <your-model-tag>`.",
            file=sys.stderr,
        )
        raise

    planner = SimpleAgent(
        name="Planner",
        system="Propose exactly 3 distinct, topical tags (prefer multi-word phrases) and a one-line summary for the given title and content.",
        model=llm,
    )
    reviewer = SimpleAgent(
        name="Reviewer",
        system=(
            "Validate: tags topical and not generic; summary ≤ 25 words; no code or markdown. "
            "If issues, list in data.issues; otherwise echo cleaned tags/summary."
        ),
        model=llm,
    )
    finalizer = SimpleAgent(
        name="Finalizer",
        system=(
            "Use reviewer feedback to finalize. Output exactly 3 tags in data.tags and the final summary in data.summary. "
            "Set data.issues to []."
        ),
        model=llm,
    )

    task = (
        f'Given the title "{args.title}" and content "{args.content}", produce exactly 3 topical tags '
        f'and a one-sentence summary in your own words. Email is {args.email}.'
    )

    transcript: List[Dict[str, str]] = []

    # Planner
    t0 = time.time()
    a = planner.respond(transcript, task, args.title, args.content, args.strict)
    t1 = time.time()
    transcript.append({"role": "Planner", "content": json.dumps(a, ensure_ascii=False)})
    print(f"\n--- Planner ({int((t1 - t0) * 1000)} ms) ---\n{json.dumps(a, indent=2)}")

    # Reviewer
    t0 = time.time()
    b = reviewer.respond(transcript, task, args.title, args.content, args.strict)
    t1 = time.time()
    transcript.append({"role": "Reviewer", "content": json.dumps(b, ensure_ascii=False)})
    print(f"\n--- Reviewer ({int((t1 - t0) * 1000)} ms) ---\n{json.dumps(b, indent=2)}")

    # Finalizer
    final = finalizer.respond(transcript, task, args.title, args.content, args.strict)
    print(f"\n Finalized Output \n{json.dumps(final, indent=2)}")

    # Publish package
    package = {
        "title": args.title,
        "email": args.email,
        "content": args.content,
        "agents": {"transcript": transcript, "final": final.get("data", {})},
        "submissionDate": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print(f"\n Publish Package \n{json.dumps(package, indent=2)}")


if __name__ == "__main__":
    main()
