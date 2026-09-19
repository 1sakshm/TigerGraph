"""The public preview must be reproducible and honest about provenance."""

import json
from pathlib import Path

from scripts.build_pages_preview import build


ROOT = Path(__file__).resolve().parents[1]


def test_pages_preview_contains_all_cases_and_no_backend_actions(tmp_path):
    build(ROOT, tmp_path)

    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    summaries = json.loads((tmp_path / "data/index.json").read_text(encoding="utf-8"))
    script = (tmp_path / "static/benchmark.js").read_text(encoding="utf-8")

    assert 'data-static-preview="true"' in page
    assert 'href="./static/style.css"' in page
    assert 'src="./static/benchmark.js"' in page
    assert "Read-only preview" in page
    assert len(summaries) == 20
    assert [item["case_id"] for item in summaries] == [f"HHG-{i:03d}" for i in range(1, 21)]
    assert "./data/index.json" in script
    for item in summaries:
        case_id = item["case_id"]
        answer = json.loads((tmp_path / f"data/{case_id}.json").read_text(encoding="utf-8"))
        trace = json.loads((tmp_path / f"data/investigations/{case_id}.json").read_text(encoding="utf-8"))
        assert answer["case"]["written_to_graph"] is False
        assert answer["case_id"] == case_id
        assert isinstance(trace, list)
