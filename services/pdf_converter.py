import subprocess
from pathlib import Path

from config import find_soffice


def convert_to_pdf(docx_path, output_dir=None):
    docx_path = Path(docx_path)
    output_dir = Path(output_dir) if output_dir else docx_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    soffice = find_soffice()
    if not soffice:
        return {
            "ok": False,
            "pdf": None,
            "error": "LibreOffice no está instalado. Instálelo para habilitar la exportación a PDF.",
        }
    command = [
        str(soffice),
        "--headless",
        "--norestore",
        "--convert-to",
        "pdf:writer_pdf_Export",
        "--outdir",
        str(output_dir),
        str(docx_path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=180,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "pdf": None, "error": f"No fue posible ejecutar LibreOffice: {error}"}
    pdf_path = output_dir / f"{docx_path.stem}.pdf"
    if result.returncode != 0 or not pdf_path.exists():
        message = (result.stderr or result.stdout or "").strip()
        return {
            "ok": False,
            "pdf": None,
            "error": f"LibreOffice no generó el PDF. {message[:400]}",
        }
    return {"ok": True, "pdf": str(pdf_path), "error": None}
