from docx import Document

from services.docx_builder import build_docx


def test_build_docx(sample_guide, tmp_path):
    output = tmp_path / "guia.docx"
    build_docx(sample_guide, output)
    assert output.exists()
    assert output.stat().st_size > 1000
    document = Document(str(output))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "FORMATO GUÍA DE APRENDIZAJE" in text
    assert "IDENTIFICACIÓN DE LA GUIA DE APRENDIZAJE" in text
    assert document.tables
