import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

import faiss
import yaml
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import TokenTextSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.faiss import FaissVectorStore

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.model_client import OllamaModelClient

HW = ROOT / "reports" / "hw04"
CORPUS = HW / "corpus"
QUESTIONS = HW / "questions.yaml"
RAW = HW / "raw"

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL = "qwen3:8b"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 3
SWEEP_KS = [1, 3, 5]
SWEEP_QUESTIONS = ["Q2", "Q3"]
MIN_SCORE = 0.35  # chunks below this cosine score are treated as irrelevant in config C
DUP_OVERLAP = 0.8  # word-set Jaccard at or above this counts as a duplicate chunk

REFUSAL = "I cannot answer this question from the provided documents"
REFUSAL_PATTERNS = re.compile(
    r"cannot answer|can't answer|unable to answer|do not have|don't have|"
    r"no information|not (?:mentioned|provided|specified|included|contain)",
    re.IGNORECASE,
)
CITATION = re.compile(r"\[\d+\]")

RULES = f"""You answer questions using only the numbered context passages you are given.
Rules:
1. Use only facts stated in the context. Do not use outside knowledge.
2. After every fact, cite the passage number in square brackets, e.g. [1].
3. If the question is ambiguous, say so and answer each reading the context supports.
4. If the context does not contain enough evidence, reply exactly: "{REFUSAL}" and nothing else."""


# Corpus and index
def load_docs():
    return [
        Document(text=path.read_text(encoding="utf-8"), metadata={"source": path.name})
        for path in sorted(CORPUS.glob("*.md"))
    ]


def build_index(embed_model):
    splitter = TokenTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    nodes = splitter.get_nodes_from_documents(load_docs())
    per_source = {}
    for node in nodes:
        source = node.metadata["source"]
        per_source[source] = per_source.get(source, 0) + 1
        node.metadata["chunk_id"] = f"{source}#{per_source[source]}"
    dim = len(embed_model.get_text_embedding("dimension probe"))
    storage = StorageContext.from_defaults(
        vector_store=FaissVectorStore(faiss_index=faiss.IndexFlatIP(dim))
    )
    index = VectorStoreIndex(nodes, storage_context=storage, embed_model=embed_model)
    return index, per_source


# Retrieval
def retrieve(index, question, k):
    hits = index.as_retriever(similarity_top_k=k).retrieve(question)
    return [
        {
            "rank": rank,
            "score": round(float(hit.score), 4),
            "source": hit.node.metadata["source"],
            "chunk_id": hit.node.metadata["chunk_id"],
            "text": hit.node.get_content(),
        }
        for rank, hit in enumerate(hits, 1)
    ]


def format_hits(qid, question, k, hits):
    lines = [f"=== {qid} | k={k} | {question}"]
    for h in hits:
        preview = " ".join(h["text"].split())[:160]
        lines.append(f"  #{h['rank']} score={h['score']:.4f} {h['chunk_id']}  {preview}")
    return "\n".join(lines)


# Context engineering for config C
def words(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def curate(hits):
    kept, dropped = [], []
    for h in sorted(hits, key=lambda h: h["score"], reverse=True):
        if h["score"] < MIN_SCORE:
            dropped.append({**h, "reason": f"score < {MIN_SCORE}"})
            continue
        dup = next(
            (k for k in kept
             if len(words(h["text"]) & words(k["text"])) / len(words(h["text"]) | words(k["text"])) >= DUP_OVERLAP),
            None,
        )
        if dup:
            dropped.append({**h, "reason": f"duplicate of {dup['chunk_id']}"})
            continue
        kept.append(h)
    return kept, dropped


# Prompts
def prompt_no_rag(question):
    return [{"role": "user", "content": question}]


def prompt_basic(question, hits):
    context = "\n\n".join(h["text"] for h in hits)
    return [{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"}]


def prompt_curated(question, kept):
    context = "\n\n".join(
        f"[{i}] (source: {h['source']}, {h['chunk_id']})\n{h['text']}" for i, h in enumerate(kept, 1)
    )
    return [
        {"role": "system", "content": RULES},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]


def ask(client, messages):
    t0 = time.perf_counter()
    resp = client.complete(messages)
    return {
        "answer": resp.content,
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


def run_config(client, config, q, hits):
    record = {"id": q["id"], "config": config, "k": len(hits), "question": q["question"]}
    if config == "A":
        return {**record, "k": 0, "chunks": [], **ask(client, prompt_no_rag(q["question"]))}
    if config == "B":
        chunks = [{**h, "kept": True} for h in hits]
        return {**record, "chunks": chunks, **ask(client, prompt_basic(q["question"], hits))}

    kept, dropped = curate(hits)
    chunks = [{**h, "kept": True, "label": i} for i, h in enumerate(kept, 1)]
    chunks += [{**h, "kept": False} for h in dropped]
    if not kept:
        return {**record, "chunks": chunks, "answer": REFUSAL, "input_tokens": 0,
                "output_tokens": 0, "latency_ms": 0.0, "llm_called": False}
    return {**record, "chunks": chunks, "llm_called": True,
            **ask(client, prompt_curated(q["question"], kept))}


# Evaluation
def auto_eval(rec, q):
    used = {c["source"] for c in rec["chunks"] if c["kept"]}
    expected = set(q["expected_sources"])
    answer = rec["answer"]
    refused = answer.strip().rstrip(".") == REFUSAL or bool(REFUSAL_PATTERNS.search(answer))
    if rec["config"] == "A":
        retrieval = "n/a"
    elif expected:
        retrieval = int(expected <= used)
    else:
        retrieval = int(not used) if rec["config"] == "C" else "n/a"
    if rec["config"] == "A":
        fmt = "n/a"
    else:
        fmt = int(answer.strip().rstrip(".") == REFUSAL or bool(CITATION.search(answer)))
    return {
        "id": rec["id"],
        "config": rec["config"],
        "k": rec["k"],
        "must_refuse": int(q["must_refuse"]),
        "correct_retrieval": retrieval,
        "refused": int(refused),
        "refused_when_needed": int(refused == q["must_refuse"]),
        "format_ok": fmt,
        "correct_answer": "",
        "grounded": "",
        "answer": " ".join(answer.split()),
    }


def summarize():
    rows = list(csv.DictReader((RAW / "rag_eval.csv").open()))
    missing = [f"{r['id']}/{r['config']}" for r in rows
               if r["correct_answer"] == "" or (r["config"] != "A" and r["grounded"] == "")]
    if missing:
        sys.exit(f"fill correct_answer / grounded first: {', '.join(missing)}")

    def mean(values):
        values = [int(v) for v in values if v not in ("", "n/a")]
        return f"{sum(values) / len(values):.2f}" if values else "n/a"

    out = []
    for config in ["A", "B", "C"]:
        group = [r for r in rows if r["config"] == config]
        answered = [r for r in group if r["refused"] == "0"]
        out.append({
            "config": config,
            "accuracy": mean(r["correct_answer"] for r in group),
            "faithfulness": mean(r["grounded"] for r in answered) if config != "A" else "n/a",
            "format_compliance": mean(r["format_ok"] for r in group),
            "robustness": mean(r["refused_when_needed"] for r in group),
            "retrieval_correct": mean(r["correct_retrieval"] for r in group),
        })
    write_csv(RAW / "rag_eval_summary.csv", out)
    print("| Config | Accuracy | Faithfulness | Format compliance | Robustness | Retrieval correct |")
    print("|---|---|---|---|---|---|")
    for r in out:
        print(f"| {r['config']} | {r['accuracy']} | {r['faithfulness']} | {r['format_compliance']} | "
              f"{r['robustness']} | {r['retrieval_correct']} |")


def write_csv(path, rows):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieve-only", action="store_true", help="print top-5 retrievals, no LLM calls")
    parser.add_argument("--summarize", action="store_true", help="summarize rag_eval.csv after manual grading")
    args = parser.parse_args()

    if args.summarize:
        summarize()
        return

    RAW.mkdir(parents=True, exist_ok=True)
    questions = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)
    index, per_source = build_index(embed_model)
    print(f"chunks per source: {per_source}  total: {sum(per_source.values())}")

    if args.retrieve_only:
        for q in questions:
            print(format_hits(q["id"], q["question"], 5, retrieve(index, q["question"], 5)))
        return

    client = OllamaModelClient(model=LLM_MODEL, num_predict=400)
    printouts, runs, evals = [], [], []
    for q in questions:
        hits = retrieve(index, q["question"], TOP_K)
        block = format_hits(q["id"], q["question"], TOP_K, hits)
        print(block)
        printouts.append(block)
        for config in ["A", "B", "C"]:
            rec = run_config(client, config, q, hits)
            runs.append(rec)
            evals.append(auto_eval(rec, q))
            print(f"  [{config}] {' '.join(rec['answer'].split())[:300]}")

    by_id = {q["id"]: q for q in questions}
    sweep = []
    for qid in SWEEP_QUESTIONS:
        q = by_id[qid]
        for k in SWEEP_KS:
            hits = retrieve(index, q["question"], k)
            block = format_hits(qid, q["question"], k, hits)
            print(block)
            printouts.append(block)
            for config in ["B", "C"]:
                rec = run_config(client, config, q, hits)
                rec["k"] = k
                auto = auto_eval(rec, q)
                sweep.append({
                    "id": qid,
                    "config": config,
                    "k": k,
                    "retrieved": ";".join(h["chunk_id"] for h in hits),
                    "irrelevant_retrieved": sum(h["source"] not in q["expected_sources"] for h in hits),
                    "kept": sum(c["kept"] for c in rec["chunks"]),
                    "correct_retrieval": auto["correct_retrieval"],
                    "input_tokens": rec["input_tokens"],
                    "latency_ms": rec["latency_ms"],
                    "correct_answer": "",
                    "answer": auto["answer"],
                })
                print(f"  [{config} k={k}] {auto['answer'][:300]}")

    (RAW / "rag_retrievals.txt").write_text("\n\n".join(printouts) + "\n")
    (RAW / "rag_runs.json").write_text(json.dumps(runs, indent=2))
    write_csv(RAW / "rag_eval.csv", evals)
    write_csv(RAW / "rag_k_sweep.csv", sweep)
    print(f"\nwrote rag_retrievals.txt, rag_runs.json, rag_eval.csv, rag_k_sweep.csv to {RAW}")


if __name__ == "__main__":
    main()
