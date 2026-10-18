# Project Brief

A local AI-assisted project-status reporting prototype: CSV ingestion, deterministic fact extraction, optional LLM commentary, source references, and human-reviewed JSON export.

## Run now

Requires Python 3.10 or later. No third-party dependencies.

```sh
python3 app.py
```

Open **http://127.0.0.1:8765**. Keep the terminal running. Choose **Demo**, generate a report, inspect evidence, edit the summary, enter your name, approve, and download JSON. The included data is synthetic and uses an October 18, 2026 reporting date.

Demo uses deterministic rules. It is not an LLM simulation and does not demonstrate live model accuracy.

## Enable live LLM mode

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in the server environment before starting. Use an account-enabled model that supports Responses API structured outputs. Do not place secrets in code, browser fields, screenshots, or Git.

On macOS/Linux, enter the key without putting its literal value in shell history:

```sh
read -s OPENAI_API_KEY
export OPENAI_API_KEY
export OPENAI_MODEL="your-enabled-model-id"
python3 app.py
```

Live mode sends the source records to OpenAI and can incur charges. No call is made unless Live is selected and Generate is clicked. A failure never silently falls back to demo. `store: false` is sent; this is not a promise of zero provider retention. Use synthetic or authorized data.

Optional `INPUT_USD_PER_MILLION` and `OUTPUT_USD_PER_MILLION` configure a simple cost estimate. Obtain applicable rates for your model; otherwise cost remains unknown. Estimate excludes cached-token discounts and any non-token charges. Usage counts and latency are retained.

## Architecture

1. Validate CSV headers, unique record IDs, dates, status values and size limits.
2. Compute overdue tasks, blocked tasks, missing owners/dates and conflicting structured records in Python.
3. Generate commentary with deterministic rules or a single LLM request using strict JSON schema.
4. Validate output structure and source IDs locally. Unknown citations fail closed.
5. Display original records and require a named human review.
6. Export original commentary, computed facts, source records, metrics and review corrections together.

**No agents, RAG, vector database, or autonomous actions are claimed.** One model call is enough for this scoped task. External APIs are never accessible to instructions in uploaded records except the predefined model request.

## Evaluation

```sh
python3 -m unittest discover -s tests -v
python3 evaluate.py
```

`evaluation/demo_results.json` covers 32 combinations of status, due date and owner. All include an embedded adversarial instruction; the demo ignores free-text instructions by construction. These tests assess deterministic logic, not model prompt-injection resistance. Unit tests also check malformed inputs, unknown citations, provider refusal, mock API shape, and HTTP approval gates.

Live quality has **not been evaluated**. `evaluation/live_review.csv` is a manual scoring template. Run representative live reports and score factual claims against the cited records; record prompt/model versions, missed risks, unsupported claims, and citation relevance. Do not publish an LLM accuracy percentage based on demo tests.

## Limits and known failure modes

- Record status is supplied data, not ground truth. Narrative contradictions are for the model/reviewer to detect; deterministic conflict detection only compares structured fields for matching project/task names.
- No update timestamps: conflicting rows are flagged rather than resolved as latest.
- Due today is not overdue; completed records are never overdue. Missing dates are flagged, not guessed.
- Source-ID validation proves reference existence, not semantic support. Hallucinated claims can still cite valid IDs. Review is required.
- Prompt injection is mitigated by instruction separation and no tool access, not eliminated. Adversarial source text may affect live commentary.
- This is a single-user local prototype, not an authenticated enterprise application. Review names are self-reported, and JSON exports are not tamper-proof.
- Reports remain in memory (latest 30 runs) and disappear on restart. Export to retain them. Reviewer summary edits preserve original model output; observation corrections go in review notes.
- Local session token protects POST routes from ordinary cross-site requests. Do not expose the loopback server through a public tunnel.
- API errors, refusal, incomplete output and invalid citations block report creation. Transient provider errors retry twice; ambiguous network failures may incur duplicate model charges.

## Files

`core.py`: validation, rules, provider integration, review. `app.py`: local HTTP server. `index.html`: review UI. `data/sample.csv`: synthetic sample. `tests/`: automated controls. `evaluate.py`: deterministic scenario evaluation.

## Portfolio attribution

Built with AI coding assistance. Before claiming ownership of implementation skills, understand the code, modify the workflow yourself, run live evaluations, and explain the tradeoffs and limitations. Describe current maturity as a **local prototype**, not an enterprise deployment.

## API reference

https://developers.openai.com/api/reference/resources/responses/methods/create
https://developers.openai.com/api/docs/guides/structured-outputs
