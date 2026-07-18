# Retriever Evaluation Report

Comparative performance of Grandmate's three retrieval strategies at **K=3**, measured against **135 queries derived from the corpus itself** (40 lexical + 46 extractive/semantic + 46 LLM-paraphrase + 3 negative, over 339 chunks). Each query's relevant chunk is known by construction, so Hit Rate and MRR are true relevance measures rather than substring matches. All three strategies are exercised through the production `retrieve_context(...)`.

## Query types

| Type | How it is built | What it probes |
| --- | --- | --- |
| `lexical` | The opening name / concept title verbatim | Exact keyword matching — favours BM25 |
| `semantic` | The chunk's description with the name/title **removed** | Conceptual recall when the name is absent — favours dense vectors |
| `negative` | Out-of-corpus questions (Go, football, backgammon) | Whether a retriever confidently returns junk |

## Results — bucketed (production path)

This is how the application actually retrieves: a `bucket` filter (`rules` vs `strategies`) is applied so the two corpora cannot bleed into each other.

| Retriever | Hit Rate @ K | MRR | Avg Latency |
| --- | --- | --- | --- |
| Dense Vector (semantic) | 87.1% | 0.795 | 527.17ms |
| BM25 Lexical (sparse) | 80.3% | 0.755 | 178.15ms |
| Hybrid RRF (dense + BM25) | 85.6% | 0.817 | 344.17ms |

## Results — unbucketed (diagnostic)

Retrieval across the whole corpus with no bucket filter. Shown only for comparison; earlier versions of this harness measured **only** this mode and reported it as if it were production behaviour.

| Retriever | Hit Rate @ K | MRR | Avg Latency |
| --- | --- | --- | --- |
| Dense Vector (semantic) | 83.3% | 0.684 | 382.49ms |
| BM25 Lexical (sparse) | 78.8% | 0.655 | 61.38ms |
| Hybrid RRF (dense + BM25) | 84.8% | 0.710 | 425.95ms |

## Breakdown by query type (bucketed)

| Retriever | By query type | Negative-query false positives |
| --- | --- | --- |
| Dense Vector (semantic) | {'lexical': '40/40 (100%)', 'paraphrase': '30/46 (65%)', 'semantic': '45/46 (98%)'} | 3/3 |
| BM25 Lexical (sparse) | {'lexical': '40/40 (100%)', 'paraphrase': '20/46 (43%)', 'semantic': '46/46 (100%)'} | 3/3 |
| Hybrid RRF (dense + BM25) | {'lexical': '40/40 (100%)', 'paraphrase': '28/46 (61%)', 'semantic': '45/46 (98%)'} | 3/3 |

## Observations

- **Highest ranking quality:** Hybrid RRF (dense + BM25) (MRR 0.817, Hit Rate 85.6%).
- **Fastest:** BM25 Lexical (sparse) (178.15ms).
- `lexical` and `semantic` breakdowns are reported separately because a query set made only of exact names structurally favours BM25 and would overstate it.
- Negative queries have no correct answer; every returned chunk is a false positive. This bounds how much junk a retriever will confidently surface.

> Reproducibility: Hit Rate and MRR are deterministic for a fixed corpus and query set. Latency is **not** — dense retrieval includes a network call to the embedding API, so timings vary between runs and should be read as orders of magnitude.

> All numbers in this report are generated from the measured run. No figure here is hardcoded — an earlier version of this script wrote a fixed narrative that contradicted its own table.
