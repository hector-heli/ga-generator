from services.defaults import empty_guide
from services.evidence import derive_evidence


def test_derive_evidence_codes(sample_guide):
    rows, activity_map = derive_evidence(sample_guide)
    assert rows
    assert rows[0]["evidencia"].startswith("Ev1.")
    evidences = [row["evidencia"] for row in rows]
    assert len(evidences) == len(set(evidences))
    for items in activity_map.values():
        for item in items:
            assert set(item) == {"codigo", "descripcion"}


def test_derive_evidence_pending_when_missing():
    guide = empty_guide()
    guide["momentos"]["apropiacion"]["actividades"][0]["titulo"] = "Sin evidencias"
    rows, activity_map = derive_evidence(guide)
    assert any(row["evidencia"] == "Pendiente por definir" for row in rows)
    assert activity_map[("apropiacion", 0)][0]["codigo"] == "Pendiente"
