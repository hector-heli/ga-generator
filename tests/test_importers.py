from services.docx_builder import build_docx
from services.importers.docx_importer import import_docx


def test_docx_roundtrip(sample_guide, tmp_path):
    path = tmp_path / "guia.docx"
    build_docx(sample_guide, path)
    result = import_docx(path)
    imported = result["guide"]
    assert imported["identificacion"]["programa"] == sample_guide["identificacion"]["programa"]
    assert imported["identificacion"]["codigo_programa"] == sample_guide["identificacion"]["codigo_programa"]
    for moment_id in ("apropiacion", "transferencia"):
        assert imported["momentos"][moment_id]["actividades"]
