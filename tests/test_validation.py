from services.defaults import total_hours
from services.validation import validate_guide


def test_validate_sample(sample_guide):
    result = validate_guide(sample_guide)
    assert set(result) >= {
        "ok",
        "errors",
        "warnings",
        "computed_hours",
        "declared_hours",
        "evidence_rows",
        "activity_evidence",
    }
    assert result["computed_hours"] == total_hours(sample_guide)
    assert result["declared_hours"] == 96
    assert any("no coincide" in warning for warning in result["warnings"])
    assert result["evidence_rows"]


def test_validate_empty_has_errors(empty_guide_data):
    result = validate_guide(empty_guide_data)
    assert result["ok"] is False
    assert result["errors"]
