"""Typed schemas for the JSON data files and API responses.

One set of models does double duty:
  * validates every `data/content/*.json` file (in CI and at server startup), so a
    malformed or drifted file fails loudly instead of 500-ing a user request
  * types the API responses, which feeds OpenAPI → generated TypeScript types

This exists because adding a `verified_on` key to checklists.json silently broke
/api/checklists in production. Shapes are now checked, not assumed.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "content"

# Provenance metadata that may appear at the top level of any data file.
# Never content — see META_KEYS in app.py.


class SourceLink(BaseModel):
    label: str = Field(min_length=1)
    url: HttpUrl


class Provenance(BaseModel):
    """Mixin-ish base: every user-facing dataset must say where it came from."""

    note: str | None = None
    sources: list[SourceLink] = Field(min_length=1)
    verified_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


# ---------- checklists.json ----------

class ChecklistItem(BaseModel):
    item: str = Field(min_length=1)
    why: str | None = None
    deadline: str | None = None


class Checklist(BaseModel):
    label: str = Field(min_length=1)
    urgent: list[ChecklistItem] = []
    items: list[ChecklistItem] = Field(min_length=1)
    sources: list[SourceLink] = Field(min_length=1)


# ---------- support.json ----------

class SupportOption(BaseModel):
    value: str
    label: str


class SupportQuestion(BaseModel):
    id: str
    label: str
    options: list[SupportOption] = Field(min_length=2)


class SupportProgram(BaseModel):
    id: str
    title: str
    who: str
    what: str
    how: str
    contact: str
    sources: list[SourceLink] = Field(min_length=1)
    match: dict[str, list[str]] = {}


class SupportFile(Provenance):
    questions: list[SupportQuestion] = Field(min_length=1)
    programs: list[SupportProgram] = Field(min_length=1)
    deadline_notice: dict[str, str] = {}


# ---------- centers.json ----------

class Hotline(BaseModel):
    name: str
    phone: str = Field(pattern=r"^[0-9\-]+$")
    hours: str
    for_: str = Field(alias="for")

    model_config = {"populate_by_name": True}


class RegionRow(BaseModel):
    region: str
    klac: str
    victim_center: str
    sunflower: str


class CentersFile(Provenance):
    hotlines: list[Hotline] = Field(min_length=1)
    regions: list[RegionRow] = Field(min_length=1)


# ---------- deadlines.json ----------

class DeadlineRule(BaseModel):
    id: str
    label: str
    from_: str = Field(alias="from")
    hours: int | None = None
    days: int | None = None
    months: int | None = None
    years: int | None = None
    urgency: str
    desc: str

    model_config = {"populate_by_name": True}


class DeadlinesFile(Provenance):
    rules: list[DeadlineRule] = Field(min_length=1)


# ---------- procedure.json ----------

class Stage(BaseModel):
    id: str
    title: str
    desc: str
    rights: list[str] = []
    tips: str = ""


class ProcedureFile(Provenance):
    stages: list[Stage] = Field(min_length=1)


# ---------- API response models (feed OpenAPI → generated TS types) ----------

class SupportQuestionsResponse(BaseModel):
    note: str
    questions: list[SupportQuestion]


class SupportMatchResponse(BaseModel):
    matched: list[SupportProgram]
    others: list[SupportProgram]
    notes: list[str]
    disclaimer: str
    sources: list[SourceLink]
    verified_on: str | None = None


class HealthResponse(BaseModel):
    status: str
    data: str
    generation: bool
    rate_limit_per_min: int
    articles: int
    cache_entries: int


# ---------- validation entry point ----------

def _load(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def validate_data_files() -> dict[str, int]:
    """Raise pydantic ValidationError on any malformed file. Returns item counts."""
    counts: dict[str, int] = {}

    checklists = _load("checklists.json")
    crime_types = {k: v for k, v in checklists.items() if isinstance(v, dict) and "label" in v}
    if not crime_types:
        raise ValueError("checklists.json 에 범죄 유형이 없습니다.")
    for key, value in crime_types.items():
        Checklist.model_validate(value)
    # metadata keys must be exactly the known ones — catches typos like `verified`
    extra = set(checklists) - set(crime_types) - {"note", "sources", "verified_on"}
    if extra:
        raise ValueError(f"checklists.json 에 알 수 없는 최상위 키: {sorted(extra)}")
    counts["checklists"] = len(crime_types)

    counts["support"] = len(SupportFile.model_validate(_load("support.json")).programs)
    counts["centers"] = len(CentersFile.model_validate(_load("centers.json")).hotlines)
    counts["deadlines"] = len(DeadlinesFile.model_validate(_load("deadlines.json")).rules)
    counts["procedure"] = len(ProcedureFile.model_validate(_load("procedure.json")).stages)

    glossary = _load("glossary.json")
    terms = {k: v for k, v in glossary.items() if isinstance(v, str) and k not in
             {"note", "verified_on"}}
    if not terms:
        raise ValueError("glossary.json 에 용어가 없습니다.")
    counts["glossary"] = len(terms)

    return counts
