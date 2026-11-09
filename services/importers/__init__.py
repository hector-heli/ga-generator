from pathlib import Path

from services.importers.docx_importer import import_docx
from services.importers.pdf_importer import import_pdf
from services.importers.xlsx_importer import import_xlsx


def import_file(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".docx":
        return import_docx(path)
    if suffix in (".xlsx", ".xlsm"):
        return import_xlsx(path)
    if suffix == ".pdf":
        return import_pdf(path)
    raise ValueError("Formato no soportado. Use DOCX, XLSX o PDF.")
