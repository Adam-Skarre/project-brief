# Implementation and evidence

| Guide area | Implementation | Verification |
|---|---|---|
| Dense baseline | Provider embeddings, cosine retrieval, top five context | Offline lexical vectors tested; live embeddings need credentials |
| Source ingestion | Markdown/text, overlapping word chunks, original offsets and lines | Offset/stability tests |
| Citations and abstention | Structured output, known chunk IDs, exact quotation validation | Validators and offline preview tested; live semantic quality unmeasured |
| Hybrid retrieval | BM25 + dense, RRF, top 50 candidates | Tests and nine offline comparisons |
| Reranking | Lexical preview or Cohere adapter | Lexical path tested; Cohere unverified live |
| Chunk tuning | CLI chunk sweep, overlap retained in index config | 60/120/180-word development sweep recorded |
| Embedding comparison | Multi-model evaluation CLI, OpenAI and Ollama adapters | Two learned models have not been benchmarked |
| Vector database | Optional persistent Chroma; default SQLite exact scan | SQLite tested; Chroma integration unverified |
| Retrieval evaluation | Recall@20, Precision@5, MRR, nDCG@5, p95 retrieval latency | 24 development questions; corpus too small for meaningful Recall@20 |
| Generation evaluation | Saved answers, human CSV, optional structured model judge, Cohen kappa | Metric tests; no human or live judge scores yet |
| Observability | Local traces and optional Langfuse observations | Local traces exercised; external trace service unverified |
| Cache and budget | Model/corpus-aware TTL cache, transactional per-database reservation cap | Cache isolation and budget tests |
| UI and API | FastAPI, upload/index/question/source/trace interface | JavaScript syntax checked; API authorization, ingestion, question, body and rate limit test passed in GitHub Actions |
| Deployment | Nonroot Docker, persistent volume, bearer token, body/rate limits | Config supplied; image build and remote deployment not run |
| CI | Core/API tests and offline MRR floor | Passed on Python 3.11 and 3.13; run 39173329529 |

## Remaining work before making live performance claims

1. Install dependencies and verify the browser UI end to end; the API integration test already passed in CI.
2. Supply live model credentials or local Ollama models; verify provider contracts.
3. Use a larger authorized corpus with held-out questions and independently reviewed source labels.
4. Compare at least two learned embedding models and a live reranker.
5. Review at least 20% of generation outputs independently, calibrate the judge, and publish measured scores with coverage.
6. Test optional services, build the image, and deploy only after validating secret handling and persistence.

The baseline and improved methods share the same question set. No guide example numbers are used as results. This repository makes no claims about enterprise deployment, employer adoption, training a foundation model, or production reliability.

CI evidence: [run 39173329529](https://github.com/Adam-Skarre/project-brief/actions/runs/39173329529), implementation commit `c08346874d1d75b4adb79447a82906d2ebcb35c3`. All 30 tests passed without skips in CI. Locally, 29 passed and one API test was skipped because dependencies were unavailable.
