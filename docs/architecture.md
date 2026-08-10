# Legal-AI — Architecture Plan

**Korean paralegal AI web chat for the general public**
Repo: github.com/moon081588-lab/Legal-AI · Draft v1 · 2026-08-10

## 1. What it is

A web chat app where ordinary people ask everyday legal questions in plain Korean (leases/jeonse, labor, contracts, traffic, family) and get answers grounded in actual Korean statutes, with article-level citations. It is a legal *information* assistant, not a lawyer: every answer explains the relevant law and cites it, and directs users to a licensed attorney or public legal aid for case-specific advice.

## 2. Legal constraints that shape the design

These are design requirements, not fine print:

**Attorney-at-Law Act (변호사법).** Paid legal advice by non-lawyers is prohibited in Korea, and this has been applied to AI chatbot services. Services that explain legal principles and locate relevant statutes/precedents are generally viewed as permissible; personalized "you should sue / you will win" advice is not. Design consequence: the system prompt hard-constrains answers to explaining law + citing sources + suggesting professional help; the MVP is free; monetization waits for the pending LegalTech Promotion Act to clarify the rules.

**AI Basic Act (AI 기본법, effective 2026-01-22).** Generative AI output must be disclosed as AI-generated, and transparency/safety obligations apply. Design consequence: persistent "AI-generated, not legal advice" labeling in the UI and in every answer.

## 3. High-level architecture

```
User ──> Web chat UI (Next.js)
              │
              ▼
        API backend (FastAPI, Python)
         │            │
         ▼            ▼
   RAG retriever   Claude API (Sonnet)
         │         (answer synthesis w/ citations)
         ▼
   Vector DB + keyword index (hybrid search)
         ▲
         │  nightly/weekly sync
   Ingestion pipeline ◄── law.go.kr Open API (법제처 국가법령정보)
```

## 4. Data layer

**Source.** The Ministry of Government Legislation's Open API (open.law.go.kr) is free with registration and provides current statutes as structured XML/JSON: a list-search API returns law serial numbers, and a full-text API returns the complete law body down to article/paragraph/item level (조·항·호·목), plus effective dates, amendment history, and administrative interpretations (법령해석례). Precedents can be added later via the same platform's case-law endpoints.

**Ingestion.** A scheduled Python job pulls target statutes, parses them into article-level records (`law_id, law_name, article_no, clause_no, text, effective_date, source_url`), and upserts changed articles only. Start with ~30 high-demand statutes: 주택임대차보호법, 근로기준법, 민법 (핵심 편), 도로교통법, 소비자기본법, 가족관계 관련 법 등.

**Chunking.** Chunk by article (조), keeping the law name + article heading in every chunk so retrieval and citation stay precise. Korean statutes are naturally article-sized, so this avoids arbitrary splitting.

**Storage.** Postgres + pgvector for the MVP (one database for both metadata and vectors — cheap, simple), with a keyword index (Postgres full-text or a BM25 layer) for hybrid search. Korean legal terms are exact-match-sensitive (e.g. 전세권 vs 임차권), so hybrid retrieval materially beats pure vector search. Embeddings: a multilingual/Korean-capable model (e.g. BGE-M3 or a commercial embedding API).

## 5. Answer pipeline (RAG)

Per question: (1) Claude rewrites the user's colloquial question into legal search terms ("월세 보증금을 못 돌려받아요" → 주택임대차보호법, 보증금 반환, 임차권등기명령); (2) hybrid search returns top-k article chunks; (3) Claude Sonnet synthesizes an answer under a constrained system prompt — plain Korean, cite every claim as (법령명 제N조), only use retrieved text, say "확인할 수 없습니다" when retrieval is empty rather than guessing, and append the referral line (대한법률구조공단 132, 지역 법률홈닥터 등) plus the AI disclosure notice; (4) answers stream with an expandable "근거 조문" panel showing the cited article text and law.go.kr links.

A lightweight classifier step routes out-of-scope requests (litigation strategy, "will I win", document drafting for filing) to a polite scope message instead of the RAG pipeline — this is the main Attorney-at-Law Act guardrail.

## 6. Stack summary

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js + Tailwind, Vercel | Fast to build, streaming chat, Korean i18n trivial |
| Backend | FastAPI (Python) | Same language as ingestion; async streaming |
| LLM | Claude Sonnet via API | Strong Korean, citation-following, cost-reasonable |
| DB | Postgres + pgvector (Supabase or RDS) | One system for metadata + vectors + keyword search |
| Ingestion | Python cron (GitHub Actions schedule works for MVP) | Free, versioned in-repo |
| Evals | Question set of ~100 real questions, graded on citation accuracy | Catch hallucinated articles before users do |

## 7. Roadmap

| Phase | Scope | Exit criterion |
|---|---|---|
| 0 (1–2 wk) | law.go.kr API key, ingest 5 statutes, CLI RAG prototype | Correct article citations on 20 test questions |
| 1 (2–4 wk) | Full pipeline, 30 statutes, web chat UI, guardrails + disclosures | Public-demoable free MVP |
| 2 | Precedents (판례) + legal interpretations, conversation memory, eval harness | Citation accuracy ≥95% on eval set |
| 3 | Accounts, feedback loop, template/form helper (permitted automation category), monetization review pending LegalTech Act | — |

## 8. Key risks

Hallucinated or outdated citations are the product-killing failure — mitigated by article-level retrieval, "answer only from retrieved text" prompting, showing source text verbatim, and the ingestion sync keyed to effective dates. Regulatory risk is managed by staying free, information-only, and clearly labeled while the LegalTech Promotion Act is pending. Claude API cost is controlled by caching frequent questions and using Haiku for the query-rewrite/classifier steps.

## 9. Repo structure (proposed)

```
Legal-AI/
├── ingest/        # law.go.kr fetch + parse + embed
├── backend/       # FastAPI app, RAG pipeline, prompts/
├── frontend/      # Next.js chat UI
├── evals/         # test questions + grading script
└── docs/          # this plan, data source notes
```
