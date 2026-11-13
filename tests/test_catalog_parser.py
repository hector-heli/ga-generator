from pathlib import Path
from services import catalog_importer

PDF_PATH = Path(r"D:\Desarrollo Curricular\Desarrollo Curricular ASM\224312 AUTOMATIZACION DE SISTEMAS MECATRONICOS.pdf")


def test_parse_design_pdf_smoke():
    if not PDF_PATH.exists():
        return
    data = catalog_importer.parse_design_pdf(PDF_PATH)
    prog = data["programa"]
    assert prog["codigo"] == "224312"
    assert prog["horas_total"] in (3984, 3984.0)
    assert len(data["competencias"]) >= 10
    total_rae = sum(len(c.get("resultados", [])) for c in data["competencias"])
    assert total_rae >= 40
    assert isinstance(data.get("warnings"), list)
    # has at least some knowledge/criteria extracted somewhere
    assert any(c.get("conocimientos_proceso") or c.get("conocimientos_saber") for c in data["competencias"])
