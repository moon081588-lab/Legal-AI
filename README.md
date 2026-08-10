# Legal-AI

Korean paralegal AI assistant for the general public. Answers everyday legal questions in plain Korean, grounded in actual statutes from the [국가법령정보 Open API](https://open.law.go.kr), with article-level citations.

**This is a legal information service, not legal advice.** It explains law and cites sources; it does not predict case outcomes, give litigation strategy, or draft court filings (변호사법 준수). All output is AI-generated and labeled as such (AI 기본법 준수).

See [docs/architecture.md](docs/architecture.md) for the full design.

## Phase 0 prototype (this repo)

```
ingest/   fetch + parse statutes from law.go.kr into article-level JSONL
rag/      BM25 retrieval over articles + Claude answer synthesis
cli.py    ask a question end-to-end
evals/    retrieval accuracy tests
data/     sample/ ships with a small dev fixture so everything runs immediately
```

## Quick start

```bash
pip install -r requirements.txt

# Runs immediately on the bundled sample data (no keys needed):
python cli.py "전세 보증금을 못 돌려받고 있어요"
python evals/run_evals.py

# For Claude-generated answers:
export ANTHROPIC_API_KEY=sk-ant-...
python cli.py "전세 보증금을 못 돌려받고 있어요"
```

## Ingesting real statutes

1. Register (free) at [open.law.go.kr](https://open.law.go.kr) — your OC is the part of your email before `@`.
2. ```bash
   export LAW_GO_KR_OC=your_id
   python ingest/fetch_laws.py      # downloads statutes listed in ingest/laws.txt
   python ingest/parse_laws.py      # -> data/articles.jsonl (used automatically over the sample)
   ```
3. Add more statutes by appending exact official names to `ingest/laws.txt`.

⚠️ `data/sample/` is a hand-made dev fixture, possibly outdated — never serve it to real users. Real deployments must use API-ingested data with effective dates.

## Roadmap

Phase 1: FastAPI backend + Next.js chat UI + pgvector hybrid search. Phase 2: 판례/법령해석례, eval hardening. Phase 3: accounts, feedback, monetization review pending the LegalTech Promotion Act. Details in `docs/architecture.md`.
