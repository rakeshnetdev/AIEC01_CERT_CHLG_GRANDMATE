"""Retriever comparison for Grandmate: Dense vs BM25 vs Hybrid RRF.

Rewritten to fix three defects that made the previous results uninterpretable
(see final_docs/synthetic_data_and_eval_design.md §2.4-2.6):

  1. **It did not test production code.** It reimplemented dense search
     (``collection.query``) and BM25 (``BM25Okapi``) locally, so it measured the eval
     script rather than ``retrieve_context``. It now calls the production retriever for
     all three strategies via ``retriever_type=``.
  2. **It ignored bucket filtering.** It called ``retrieve_context(query, dir, limit=k)``
     with no ``bucket=``, measuring unbucketed retrieval over a dual-corpus index -- which
     is not how the application retrieves. Both modes are now reported.
  3. **Relevance was substring matching over 5 hand-written queries.** "Did any returned
     chunk contain the word 'pin'?" is not relevance. The query set is now *derived from
     the corpus itself* -- each chunk yields queries whose known-relevant chunk id is that
     chunk -- giving true Hit Rate / MRR at scale.

Query types generated:
  * ``lexical``  -- the opening name / concept title verbatim (favours BM25).
  * ``semantic`` -- the chunk's description with the name/title stripped out, so the
    answer cannot be found by matching the name (favours dense). This is the discriminator
    that justifies hybrid fusion; the old 5 lexical-only queries structurally favoured BM25.
  * ``negative`` -- out-of-corpus queries that *should* retrieve nothing relevant.

Usage:
    cd backend && uv run python ../evals/compare_retrievers.py [--k 3] [--sample-per-type 20]
"""

import argparse
import json
import os
import re
import sys
import time
from typing import Dict, List, Optional

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.append(backend_dir)
sys.path.append(os.path.join(backend_dir, "src"))

from coach.rag.vector_db import get_collection
from coach.rag.pipeline import retrieve_context

CHROMA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "data", "chroma"))

RETRIEVERS = [
    ("Dense Vector (semantic)", "dense"),
    ("BM25 Lexical (sparse)", "sparse"),
    ("Hybrid RRF (dense + BM25)", "hybrid"),
]

# Queries with no supporting chunk anywhere in the corpus. A good retriever should surface
# nothing relevant; we measure how confidently each one returns junk.
NEGATIVE_QUERIES = [
    "what is the ko rule in the game of Go",
    "offside rule in association football",
    "how to castle in backgammon",
]


def _strip_terms(text: str, terms: str) -> str:
    """Remove the name/title tokens from a description so lexical matching can't win trivially."""
    out = text
    for token in re.findall(r"[A-Za-z]{3,}", terms):
        out = re.sub(rf"\b{re.escape(token)}\b", "", out, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", out).strip(" .,")


def build_query_set(collection, sample_per_type: int) -> List[Dict]:
    """Derive queries from corpus chunks, each with its known-relevant chunk id."""
    data = collection.get()
    ids, docs, metas = data["ids"], data["documents"], data["metadatas"]

    by_type: Dict[str, List[int]] = {}
    for i, meta in enumerate(metas):
        by_type.setdefault((meta or {}).get("type", "unknown"), []).append(i)

    cases: List[Dict] = []

    def sample(indices: List[int], n: int) -> List[int]:
        """Deterministic even stride, so runs are comparable."""
        if len(indices) <= n:
            return indices
        stride = len(indices) / n
        return [indices[int(j * stride)] for j in range(n)]

    # --- openings: name (lexical) + description with the name removed (semantic) --------
    for i in sample(by_type.get("opening", []), sample_per_type):
        meta, doc = metas[i], docs[i]
        name = meta.get("name")
        if not name:
            continue
        cases.append({"query": name, "relevant_id": ids[i], "qtype": "lexical",
                      "bucket": meta.get("bucket")})
        m = re.search(r"Description:\s*(.+?)(?:\.\.|\. Moves:|$)", doc)
        if m:
            semantic = _strip_terms(m.group(1), name)
            if len(semantic.split()) >= 4:
                cases.append({"query": semantic, "relevant_id": ids[i], "qtype": "semantic",
                              "bucket": meta.get("bucket")})

    # --- concepts: title (lexical) + body first sentence with the title removed ---------
    for i in sample(by_type.get("concept", []), sample_per_type):
        meta, doc = metas[i], docs[i]
        title = meta.get("title")
        if not title:
            continue
        cases.append({"query": title, "relevant_id": ids[i], "qtype": "lexical",
                      "bucket": meta.get("bucket")})
        body = re.sub(r"^#+\s*.*?\n", "", doc, count=1).strip()
        first = re.split(r"(?<=[.!?])\s", body)[0] if body else ""
        semantic = _strip_terms(first, title)
        if len(semantic.split()) >= 5:
            cases.append({"query": semantic, "relevant_id": ids[i], "qtype": "semantic",
                          "bucket": meta.get("bucket")})

    # --- FIDE rulebook: distinctive phrases lifted from the chunk itself ----------------
    for i in sample(by_type.get("pdf_chunk", []), max(3, sample_per_type // 3)):
        words = re.findall(r"[A-Za-z]{4,}", docs[i])
        if len(words) < 12:
            continue
        cases.append({"query": " ".join(words[4:14]), "relevant_id": ids[i],
                      "qtype": "semantic", "bucket": (metas[i] or {}).get("bucket")})

    for q in NEGATIVE_QUERIES:
        cases.append({"query": q, "relevant_id": None, "qtype": "negative", "bucket": None})

    return cases


PARAPHRASE_CACHE = os.path.join(os.path.dirname(__file__), "paraphrase_cache.json")


def add_paraphrase_queries(cases: List[Dict], collection) -> List[Dict]:
    """Add LLM-reworded queries: the honest test of dense vs sparse retrieval.

    The `semantic` queries built by ``build_query_set`` are *extractive* -- they are lifted
    verbatim from the chunk (minus the name), so BM25 matches them by exact word overlap and
    scores ~100%. That structurally favours sparse retrieval and cannot settle whether dense
    or hybrid earns its keep.

    A real paraphrase must *reword* the idea, which needs an LLM. Results are cached to
    ``paraphrase_cache.json`` keyed by chunk id, so the query set stays deterministic across
    runs (a generated-fresh-each-run query set would make runs incomparable).
    """
    from coach.llm.gateway import chat

    cache: Dict[str, str] = {}
    if os.path.exists(PARAPHRASE_CACHE):
        cache = json.loads(open(PARAPHRASE_CACHE, encoding="utf-8").read())

    data = collection.get()
    lookup = dict(zip(data["ids"], data["documents"]))
    targets = [c for c in cases if c["qtype"] == "semantic"]
    added: List[Dict] = []
    misses = 0

    for case in targets:
        cid = case["relevant_id"]
        if cid not in cache:
            doc = lookup.get(cid, "")[:600]
            try:
                reply = chat(messages=[
                    {"role": "system", "content":
                        "You write chess search queries. Given a corpus passage, write ONE natural "
                        "question a learner would ask whose answer is that passage. Reuse as few of "
                        "the passage's distinctive words as possible -- paraphrase the idea instead. "
                        "Never name the opening/concept directly. Reply with the question only."},
                    {"role": "user", "content": doc},
                ])
                cache[cid] = reply.strip().strip('"')
                print(f"    paraphrased {cid}: {cache[cid][:60]}…")
            except Exception as exc:
                print(f"    paraphrase FAILED for {cid}: {exc}")
                misses += 1
                continue
        added.append({"query": cache[cid], "relevant_id": cid, "qtype": "paraphrase",
                      "bucket": case["bucket"]})

    with open(PARAPHRASE_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)
    if misses:
        print(f"    WARNING: {misses} paraphrases unavailable; those chunks are untested "
              f"for abstractive recall.")
    return cases + added


def evaluate(retriever_type: str, cases: List[Dict], k: int, use_bucket: bool) -> Dict:
    """Score one retriever over the query set, through the production retrieve_context."""
    positives = [c for c in cases if c["relevant_id"] is not None]
    negatives = [c for c in cases if c["relevant_id"] is None]

    hits = 0
    rr_total = 0.0
    latency_total = 0.0
    by_qtype: Dict[str, List[bool]] = {}
    bucket_violations = 0
    false_positives = 0

    for case in positives:
        bucket = case["bucket"] if use_bucket else None
        t0 = time.perf_counter()
        results = retrieve_context(case["query"], CHROMA_DIR, limit=k,
                                   retriever_type=retriever_type, bucket=bucket)
        latency_total += (time.perf_counter() - t0) * 1000

        rank: Optional[int] = None
        for idx, item in enumerate(results, start=1):
            if item.get("id") == case["relevant_id"]:
                rank = idx
                break
            if use_bucket and bucket and (item.get("metadata") or {}).get("bucket") != bucket:
                bucket_violations += 1

        if rank:
            hits += 1
            rr_total += 1.0 / rank
        by_qtype.setdefault(case["qtype"], []).append(rank is not None)

    for case in negatives:
        results = retrieve_context(case["query"], CHROMA_DIR, limit=k,
                                   retriever_type=retriever_type, bucket=None)
        if results:
            false_positives += 1

    n = len(positives)
    return {
        "Retriever": retriever_type,
        "Hit Rate @ K": f"{100.0 * hits / n:.1f}%" if n else "n/a",
        "MRR": f"{rr_total / n:.3f}" if n else "n/a",
        "Avg Latency": f"{latency_total / n:.2f}ms" if n else "n/a",
        "_hit_rate": hits / n if n else 0.0,
        "_mrr": rr_total / n if n else 0.0,
        "_latency": latency_total / n if n else 0.0,
        "_by_qtype": {q: f"{sum(v)}/{len(v)} ({100.0 * sum(v) / len(v):.0f}%)"
                      for q, v in sorted(by_qtype.items())},
        "_bucket_violations": bucket_violations,
        "_negative_false_positives": f"{false_positives}/{len(negatives)}" if negatives else "n/a",
    }


def markdown_table(rows: List[Dict]) -> str:
    headers = [h for h in rows[0] if not h.startswith("_")]
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join(["---"] * len(headers)) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(str(r[h]) for h in headers) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Grandmate's retrieval strategies.")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--sample-per-type", type=int, default=20)
    parser.add_argument("--paraphrase", action="store_true",
                        help="Add LLM-reworded queries (cached). Without this, 'semantic' "
                             "queries are verbatim corpus extracts, which structurally "
                             "favours BM25 and cannot fairly judge dense/hybrid retrieval.")
    args = parser.parse_args()

    print(f"Connecting to ChromaDB at: {CHROMA_DIR}")
    collection = get_collection(CHROMA_DIR)
    data = collection.get()
    if not data or not data.get("documents"):
        sys.exit("Error: the ChromaDB collection is empty. Run ingestion first.")
    print(f"Loaded {len(data['documents'])} chunks.")

    cases = build_query_set(collection, args.sample_per_type)
    if args.paraphrase:
        print("Generating/loading LLM-paraphrased queries (cached)...")
        cases = add_paraphrase_queries(cases, collection)
    positives = [c for c in cases if c["relevant_id"]]
    qtypes: Dict[str, int] = {}
    for c in cases:
        qtypes[c["qtype"]] = qtypes.get(c["qtype"], 0) + 1
    print(f"Derived {len(cases)} queries from the corpus: {qtypes}\n")

    sections = {}
    for use_bucket, label in ((True, "bucketed (production path)"), (False, "unbucketed")):
        print(f"Evaluating retrievers — {label} ...")
        rows = [evaluate(rt, cases, args.k, use_bucket) for _, rt in RETRIEVERS]
        for row, (name, _) in zip(rows, RETRIEVERS):
            row["Retriever"] = name
        sections[label] = rows
        print(markdown_table(rows) + "\n")

    prod = sections["bucketed (production path)"]
    best_mrr = max(prod, key=lambda r: r["_mrr"])
    fastest = min(prod, key=lambda r: r["_latency"])

    report = [
        "# Retriever Evaluation Report\n",
        f"Comparative performance of Grandmate's three retrieval strategies at **K={args.k}**, "
        f"measured against **{len(positives)} queries derived from the corpus itself** "
        f"({len(data['documents'])} chunks). Each query's relevant chunk is known by "
        "construction, so Hit Rate and MRR are true relevance measures rather than substring "
        "matches. All three strategies are exercised through the production "
        "`retrieve_context(...)`.\n",
        "## Query types\n",
        "| Type | How it is built | What it probes |",
        "| --- | --- | --- |",
        "| `lexical` | The opening name / concept title verbatim | Exact keyword matching — favours BM25 |",
        "| `semantic` | The chunk's description with the name/title **removed** | Conceptual recall when the name is absent — favours dense vectors |",
        "| `negative` | Out-of-corpus questions (Go, football, backgammon) | Whether a retriever confidently returns junk |",
        "\n## Results — bucketed (production path)\n",
        "This is how the application actually retrieves: a `bucket` filter (`rules` vs "
        "`strategies`) is applied so the two corpora cannot bleed into each other.\n",
        markdown_table(prod),
        "\n## Results — unbucketed (diagnostic)\n",
        "Retrieval across the whole corpus with no bucket filter. Shown only for comparison; "
        "earlier versions of this harness measured **only** this mode and reported it as if it "
        "were production behaviour.\n",
        markdown_table(sections["unbucketed"]),
        "\n## Breakdown by query type (bucketed)\n",
        "| Retriever | By query type | Negative-query false positives |",
        "| --- | --- | --- |",
    ]
    for row in prod:
        report.append(f"| {row['Retriever']} | {row['_by_qtype']} | {row['_negative_false_positives']} |")

    report += [
        "\n## Observations\n",
        f"- **Highest ranking quality:** {best_mrr['Retriever']} (MRR {best_mrr['MRR']}, "
        f"Hit Rate {best_mrr['Hit Rate @ K']}).",
        f"- **Fastest:** {fastest['Retriever']} ({fastest['Avg Latency']}).",
        "- `lexical` and `semantic` breakdowns are reported separately because a query set made "
        "only of exact names structurally favours BM25 and would overstate it.",
        "- Negative queries have no correct answer; every returned chunk is a false positive. "
        "This bounds how much junk a retriever will confidently surface.",
        "\n> Reproducibility: Hit Rate and MRR are deterministic for a fixed corpus and query "
        "set. Latency is **not** — dense retrieval includes a network call to the embedding "
        "API, so timings vary between runs and should be read as orders of magnitude.\n",
        "> All numbers in this report are generated from the measured run. No figure here is "
        "hardcoded — an earlier version of this script wrote a fixed narrative that "
        "contradicted its own table.\n",
    ]

    target = os.path.join(os.path.dirname(__file__), "..", "final_docs", "retriever_evaluation_report.md")
    with open(target, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"Report saved to {os.path.abspath(target)}")


if __name__ == "__main__":
    main()
