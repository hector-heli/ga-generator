import json
import time
import uuid

from flask import Flask, jsonify, render_template, request, send_from_directory
from pathlib import Path

from config import DRAFT_DIR, OUTPUT_DIR, public_config, save_config
from services.defaults import MOMENT_ORDER, MOMENTS, empty_guide, normalize_guide, safe_slug
from services.docx_builder import build_docx
from services.importers import import_file
from services.pdf_converter import convert_to_pdf
from services.suggestions import suggest_section
from services.validation import validate_guide

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DRAFT_DIR.mkdir(parents=True, exist_ok=True)


def _payload_guide():
    data = request.get_json(silent=True) or {}
    if "guide" in data:
        return normalize_guide(data["guide"])
    return normalize_guide(data)


@app.get("/")
def index():
    base = empty_guide()
    return render_template(
        "index.html",
        guide=json.dumps(base, ensure_ascii=False),
        moments=MOMENTS,
        order=MOMENT_ORDER,
        config=public_config(),
    )


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/config")
def config():
    return jsonify(public_config())


@app.post("/api/config")
def api_save_config():
    data = request.get_json(silent=True) or {}
    llm = data.get("llm")
    if not isinstance(llm, dict):
        return jsonify({"error": "Configuración LLM inválida."}), 400
    allowed = {"enabled", "base_url", "model", "api_key"}
    update = {key: llm[key] for key in allowed if key in llm}
    if update.get("api_key") in ("***", ""):
        update.pop("api_key", None)
    if "enabled" in update:
        update["enabled"] = bool(update["enabled"])
    save_config({"llm": update})
    return jsonify(public_config())


@app.post("/api/config/test")
def api_test_config():
    from services import llm

    if not llm.available():
        return jsonify({"ok": False, "error": "La IA está deshabilitada o sin API key."}), 400
    try:
        reply = llm.chat(
            [{"role": "user", "content": "Responde únicamente con la palabra OK."}],
            temperature=0,
            timeout=20,
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502
    return jsonify({"ok": True, "reply": str(reply)[:200]})


@app.post("/api/normalize")
def api_normalize():
    return jsonify(_payload_guide())


@app.post("/api/validate")
def api_validate():
    guide = _payload_guide()
    return jsonify(validate_guide(guide))


@app.post("/api/suggest")
def api_suggest():
    data = request.get_json(silent=True) or {}
    guide = _payload_guide()
    section = data.get("section", "")
    try:
        out = suggest_section(
            guide,
            section,
            data.get("moment_id"),
            data.get("index", 0),
            use_llm=bool(data.get("use_llm")),
        )
        return jsonify(out)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/import")
def api_import():
    if "file" not in request.files or not request.files["file"].filename:
        return jsonify({"error": "Suba un archivo DOCX, XLSX o PDF."}), 400
    upload = request.files["file"]
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in (".docx", ".xlsx", ".xlsm", ".pdf"):
        return jsonify({"error": "Formato no soportado."}), 400
    tmp = OUTPUT_DIR / f"_upload_{uuid.uuid4().hex}{suffix}"
    upload.save(str(tmp))
    try:
        result = import_file(str(tmp))
    except Exception as exc:
        return jsonify({"error": f"No fue posible importar el archivo: {exc}"}), 400
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    return jsonify(result)


@app.post("/api/generate")
def api_generate():
    data = request.get_json(silent=True) or {}
    guide = _payload_guide()
    fmt = (data.get("format") or "docx").lower()
    rae = guide["identificacion"].get("resultados_aprendizaje", "guia")
    code = safe_slug(rae, "guia")
    stamp = time.strftime("%Y%m%d%H%M%S")
    name = f"GA_{code}_{stamp}_{uuid.uuid4().hex[:6]}"
    docx_path = OUTPUT_DIR / f"{name}.docx"
    try:
        build_docx(guide, docx_path)
    except Exception as exc:
        return jsonify({"error": f"No fue posible generar el DOCX: {exc}"}), 500
    if fmt == "pdf":
        conv = convert_to_pdf(str(docx_path), str(OUTPUT_DIR))
        if not conv["ok"]:
            # Fallback: generate DOCX and offer it; PDF export needs LibreOffice.
            return jsonify(
                {
                    "error": conv["error"],
                    "docx": docx_path.name,
                    "download": f"/download/{docx_path.name}",
                    "download_docx": f"/download/{docx_path.name}",
                }
            )
        path = Path(conv["pdf"])
        return jsonify(
            {
                "ok": True,
                "file": path.name,
                "download": f"/download/{path.name}",
                "docx": docx_path.name,
                "docx_download": f"/download/{docx_path.name}",
            }
        )
    return jsonify(
        {"ok": True, "file": docx_path.name, "download": f"/download/{docx_path.name}"}
    )


@app.get("/download/<path:filename>")
def download(filename):
    if "/" in filename or "\\" in filename or ".." in filename:
        return jsonify({"error": "Archivo inválido."}), 400
    path = OUTPUT_DIR / filename
    if not path.exists():
        return jsonify({"error": "Archivo no encontrado."}), 404
    return send_from_directory(str(OUTPUT_DIR), filename, as_attachment=True)


@app.post("/api/draft")
def api_save_draft():
    guide = _payload_guide()
    draft_id = uuid.uuid4().hex
    path = DRAFT_DIR / f"{draft_id}.json"
    path.write_text(json.dumps(guide, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"id": draft_id})


@app.get("/api/draft/<draft_id>")
def api_load_draft(draft_id):
    if "/" in draft_id or "\\" in draft_id or ".." in draft_id:
        return jsonify({"error": "Borrador inválido."}), 400
    path = DRAFT_DIR / f"{draft_id}.json"
    if not path.exists():
        return jsonify({"error": "Borrador no encontrado."}), 404
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return jsonify({"error": "El borrador está corrupto o no se pudo leer."}), 400
    return jsonify(normalize_guide(stored))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
