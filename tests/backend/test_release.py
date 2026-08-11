"""버전·릴리스 노트 관련 테스트."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import backend  # noqa: E402
from backend.app import app  # noqa: E402
from tools.release_notes import extract  # noqa: E402

client = TestClient(app)


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?", backend.__version__)


def test_health_reports_running_version():
    """배포된 버전을 외부에서 확인할 수 있어야 합니다(연기 테스트·장애 대응)."""
    assert client.get("/api/health").json()["version"] == backend.__version__


def test_openapi_carries_version():
    assert app.openapi()["info"]["version"] == backend.__version__


def test_changelog_has_section_for_current_version():
    """릴리스 워크플로가 CHANGELOG에서 노트를 추출하므로, 항목이 없으면 릴리스가 실패합니다."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    body = extract(backend.__version__, text)
    assert body.strip(), f"CHANGELOG.md 에 [{backend.__version__}] 내용이 비어 있습니다."


def test_release_notes_extraction_stops_at_next_section():
    sample = "\n".join([
        "# 변경 이력", "",
        "## [Unreleased]", "", "미출시 내용", "",
        "## [0.2.0] - 2026-09-01", "", "### 추가됨", "- 새 기능", "", "---", "",
        "## [0.1.0] - 2026-08-11", "", "- 첫 릴리스", "",
    ])
    body = extract("0.2.0", sample)
    assert "새 기능" in body
    assert "첫 릴리스" not in body
    assert not body.endswith("---")
    assert extract("v0.2.0", sample) == body  # v 접두사 허용


def test_unknown_version_fails_loudly():
    with pytest.raises(SystemExit):
        extract("9.9.9", "# 변경 이력\n\n## [0.1.0]\n\n- 내용\n")
