"""Data-shape tests: the files must match what the code assumes."""

import copy
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.schemas import Checklist, SupportFile, validate_data_files  # noqa: E402

DATA = ROOT / "data"


def test_all_data_files_match_their_schema():
    counts = validate_data_files()
    assert counts["checklists"] == 4
    assert counts["support"] >= 7
    assert counts["glossary"] >= 15


def test_checklist_missing_sources_is_rejected():
    raw = json.loads((DATA / "checklists.json").read_text(encoding="utf-8"))
    broken = copy.deepcopy(raw["assault"])
    broken.pop("sources")
    with pytest.raises(ValidationError):
        Checklist.model_validate(broken)


def test_non_https_source_is_rejected():
    raw = json.loads((DATA / "checklists.json").read_text(encoding="utf-8"))
    broken = copy.deepcopy(raw["assault"])
    broken["sources"] = [{"label": "bad", "url": "not-a-url"}]
    with pytest.raises(ValidationError):
        Checklist.model_validate(broken)


def test_support_requires_verified_on_date():
    raw = json.loads((DATA / "support.json").read_text(encoding="utf-8"))
    broken = copy.deepcopy(raw)
    broken["verified_on"] = "2026/08/11"  # wrong format
    with pytest.raises(ValidationError):
        SupportFile.model_validate(broken)


def test_unknown_top_level_key_in_checklists_is_caught(monkeypatch, tmp_path):
    """Regression for the /api/checklists 500: a stray top-level key must fail
    validation loudly rather than crash a request later."""
    import backend.schemas as s

    raw = json.loads((DATA / "checklists.json").read_text(encoding="utf-8"))
    raw["verifed_on"] = "2026-08-11"  # typo'd metadata key
    (tmp_path / "checklists.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    for name in ("support", "centers", "deadlines", "procedure", "glossary"):
        (tmp_path / f"{name}.json").write_text(
            (DATA / f"{name}.json").read_text(encoding="utf-8"), encoding="utf-8"
        )
    monkeypatch.setattr(s, "DATA_DIR", tmp_path)
    with pytest.raises(ValueError, match="알 수 없는 최상위 키"):
        s.validate_data_files()
