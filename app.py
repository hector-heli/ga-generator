import json
import os
import secrets
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from config import DRAFT_DIR, OUTPUT_DIR, public_config, save_config
from services import store
from services.defaults import (
    MOMENT_ORDER,
    MOMENTS,
    empty_guide,
    normalize_guide,
    safe_slug,
)
from services.docx_builder import build_docx
from services.guide_forms import parse_identification, parse_section
from services.importers import import_file
from services.pdf_converter import convert_to_pdf
from services.progress import STATUS_LABELS, build_navigation, guide_summary
from services.suggestions import suggest_section
from services.validation import validate_guide

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
app.config.update(
    SECRET_KEY=os.environ.get("GA_SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    CSRF_ENABLED=True,
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DRAFT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Utilidades de sesión, CSRF y contexto
# ---------------------------------------------------------------------------


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token
app.jinja_env.globals["STATUS_LABELS"] = STATUS_LABELS


def _check_csrf():
    if not app.config.get("CSRF_ENABLED", True):
        return
    expected = session.get("_csrf_token", "")
    received = request.form.get("csrf_token", "")
    if not expected or not secrets.compare_digest(str(expected), str(received)):
        abort(400, description="Token CSRF inválido o vencido. Recargue la página.")


def _load_guide(guide_id):
    if not store.valid_id(guide_id):
        abort(404)
    guide = store.get_guide(guide_id)
    if guide is None:
        abort(404)
    return normalize_guide(guide)


def _page_context(guide_id, guide, active, **extra):
    validation = validate_guide(guide)
    nav = build_navigation(guide_id, guide, validation, active)
    context = {
        "guide": guide,
        "guide_id": guide_id,
        "validation": validation,
        "nav": nav,
        "summary": guide_summary(guide),
        "active": active,
    }
    context.update(extra)
    return context


def _persist(guide_id, guide, message="Cambios guardados.", category="ok"):
    store.save_guide(guide_id, normalize_guide(guide))
    flash(message, category)


def _notify_suggest():
    """Avisar cuando se pidió IA pero no hay proveedor disponible."""
    if not request.form.get("action", "").startswith("suggest"):
        return
    if str(request.form.get("usar_ia", "")).lower() not in ("on", "1", "true", "si", "sí"):
        return
    from services import llm

    if not llm.available():
        flash(
            "La IA está deshabilitada o sin clave configurada; se usaron las plantillas locales.",
            "warn",
        )


def _save_and_back(guide_id, guide, endpoint, message, **params):
    _notify_suggest()
    _persist(guide_id, guide, message)
    return redirect(url_for(endpoint, guide_id=guide_id, **params), code=303)


def _redirect_section(guide_id, section, moment_id=None):
    if moment_id:
        return redirect(
            url_for("guide_moment", guide_id=guide_id, moment_id=moment_id), code=303
        )
    return redirect(url_for(f"guide_{section}", guide_id=guide_id), code=303)


def _action_message(action):
    root = action.split(":", 1)[0]
    return {
        "add": "Elemento agregado. Complete la información y guarde.",
        "up": "Orden actualizado.",
        "down": "Orden actualizado.",
        "delete": "Elemento eliminado.",
        "suggest": "Contenido autocompletado. Revise y ajuste el texto.",
        "add_autor": "Autor agregado.",
        "delete_autor": "Autor eliminado.",
        "add_cambio": "Registro de cambio agregado.",
        "delete_cambio": "Registro de cambio eliminado.",
    }.get(root, "Cambios guardados.")


@app.template_filter("fecha")
def _fecha_filter(value):
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return text


@app.template_filter("horas")
def _horas_filter(value):
    try:
        return f"{float(value or 0):g}"
    except (TypeError, ValueError):
        return "0"


@app.template_filter("lineas")
def _lineas_filter(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value
    return "\n".join(str(item) for item in value)


# ---------------------------------------------------------------------------
# Tablero de guías
# ---------------------------------------------------------------------------


@app.get("/")
def index():
    guides = []
    for row in store.list_guides():
        guide = normalize_guide(row["guide"])
        validation = validate_guide(guide)
        guides.append(
            {
                "id": row["id"],
                "summary": guide_summary(guide),
                "validation": validation,
                "nav": build_navigation(row["id"], guide, validation, ""),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    return render_template("dashboard.html", guides=guides, app_config=public_config())


@app.post("/guias/nueva")
def guide_new():
    _check_csrf()
    guide = normalize_guide(empty_guide())
    parse_identification(request.form, guide)
    guide_id = store.create_guide(normalize_guide(guide))
    flash("Guía creada. Complete la identificación y avance por las secciones.", "ok")
    return redirect(url_for("guide_identificacion", guide_id=guide_id), code=303)


@app.post("/guias/importar")
def guide_import():
    _check_csrf()
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        flash("Seleccione un archivo DOCX, XLSX o PDF para importar.", "err")
        return redirect(url_for("index"), code=303)
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in (".docx", ".xlsx", ".xlsm", ".pdf"):
        flash("Formato no soportado. Use DOCX, XLSX o PDF.", "err")
        return redirect(url_for("index"), code=303)

    tmp = OUTPUT_DIR / f"_upload_{uuid.uuid4().hex}{suffix}"
    upload.save(str(tmp))
    try:
        result = import_file(str(tmp))
    except Exception as exc:
        flash(f"No fue posible importar el archivo: {exc}", "err")
        return redirect(url_for("index"), code=303)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass

    guide = normalize_guide(result.get("guide"))
    guide_id = store.create_guide(guide)
    flash("Documento importado. Revise y ajuste la información antes de generar.", "ok")
    for warning in (result.get("warnings") or [])[:4]:
        flash(warning, "warn")
    return redirect(url_for("guide_identificacion", guide_id=guide_id), code=303)


@app.post("/guias/<guide_id>/eliminar")
def guide_delete(guide_id):
    _check_csrf()
    if store.delete_guide(guide_id):
        flash("Guía eliminada.", "ok")
    else:
        flash("La guía no existe o ya fue eliminada.", "warn")
    return redirect(url_for("index"), code=303)


@app.get("/guias/<guide_id>")
def guide_root(guide_id):
    _load_guide(guide_id)
    return redirect(url_for("guide_identificacion", guide_id=guide_id), code=303)


# ---------------------------------------------------------------------------
# Secciones de la guía
# ---------------------------------------------------------------------------


@app.route("/guias/<guide_id>/identificacion", methods=["GET", "POST"])
def guide_identificacion(guide_id):
    guide = _load_guide(guide_id)
    if request.method == "POST":
        _check_csrf()
        parse_section(request.form, guide, "identificacion")
        return _save_and_back(
            guide_id,
            guide,
            "guide_identificacion",
            "Identificación guardada.",
        )
    return render_template(
        "identificacion.html",
        **_page_context(guide_id, guide, "identificacion"),
    )


@app.route("/guias/<guide_id>/presentacion", methods=["GET", "POST"])
def guide_presentacion(guide_id):
    guide = _load_guide(guide_id)
    if request.method == "POST":
        _check_csrf()
        action = request.form.get("action", "save")
        parse_section(request.form, guide, "presentacion")
        return _save_and_back(
            guide_id,
            guide,
            "guide_presentacion",
            _action_message(action),
        )
    return render_template(
        "presentacion.html",
        **_page_context(guide_id, guide, "presentacion"),
    )


@app.get("/guias/<guide_id>/momentos")
def guide_momentos(guide_id):
    guide = _load_guide(guide_id)
    return render_template(
        "momentos.html",
        **_page_context(guide_id, guide, "momentos"),
    )


@app.route("/guias/<guide_id>/momentos/<moment_id>", methods=["GET", "POST"])
def guide_moment(guide_id, moment_id):
    if moment_id not in MOMENT_ORDER:
        abort(404)
    guide = _load_guide(guide_id)
    if request.method == "POST":
        _check_csrf()
        action = request.form.get("action", "save")
        parse_section(request.form, guide, "momentos", moment_id)
        return _save_and_back(
            guide_id,
            guide,
            "guide_moment",
            _action_message(action),
            moment_id=moment_id,
        )
    return render_template(
        "momento.html",
        **_page_context(
            guide_id,
            guide,
            f"momentos/{moment_id}",
            moment_id=moment_id,
            moment=guide["momentos"][moment_id],
            moment_meta=MOMENTS[moment_id],
        ),
    )


@app.route("/guias/<guide_id>/glosario", methods=["GET", "POST"])
def guide_glosario(guide_id):
    guide = _load_guide(guide_id)
    if request.method == "POST":
        _check_csrf()
        action = request.form.get("action", "save")
        parse_section(request.form, guide, "glosario")
        return _save_and_back(
            guide_id, guide, "guide_glosario", _action_message(action)
        )
    return render_template(
        "glosario.html",
        **_page_context(guide_id, guide, "glosario"),
    )


@app.route("/guias/<guide_id>/referentes", methods=["GET", "POST"])
def guide_referentes(guide_id):
    guide = _load_guide(guide_id)
    if request.method == "POST":
        _check_csrf()
        action = request.form.get("action", "save")
        parse_section(request.form, guide, "referentes")
        return _save_and_back(
            guide_id, guide, "guide_referentes", _action_message(action)
        )
    return render_template(
        "referentes.html",
        **_page_context(guide_id, guide, "referentes"),
    )


@app.route("/guias/<guide_id>/control", methods=["GET", "POST"])
def guide_control(guide_id):
    guide = _load_guide(guide_id)
    if request.method == "POST":
        _check_csrf()
        action = request.form.get("action", "save")
        parse_section(request.form, guide, "control")
        return _save_and_back(guide_id, guide, "guide_control", _action_message(action))
    return render_template(
        "control.html",
        **_page_context(guide_id, guide, "control"),
    )


# ---------------------------------------------------------------------------
# Resumen y generación
# ---------------------------------------------------------------------------


@app.get("/guias/<guide_id>/resumen")
def guide_resumen(guide_id):
    guide = _load_guide(guide_id)
    context = _page_context(guide_id, guide, "resumen")
    context.update(
        {
            "archivo": request.args.get("archivo", ""),
            "docx": request.args.get("docx", ""),
            "es_pdf": request.args.get("pdf", "") == "1",
        }
    )
    return render_template("resumen.html", **context)


@app.post("/guias/<guide_id>/generar")
def guide_generate(guide_id):
    _check_csrf()
    guide = _load_guide(guide_id)
    fmt = (request.form.get("format") or "docx").lower()
    rae = guide["identificacion"].get("resultados_aprendizaje", "guia")
    code = safe_slug(rae, "guia")
    stamp = time.strftime("%Y%m%d%H%M%S")
    name = f"GA_{code}_{stamp}_{uuid.uuid4().hex[:6]}"
    docx_path = OUTPUT_DIR / f"{name}.docx"
    try:
        build_docx(guide, docx_path)
    except Exception as exc:
        flash(f"No fue posible generar el DOCX: {exc}", "err")
        return redirect(url_for("guide_resumen", guide_id=guide_id), code=303)

    if fmt == "pdf":
        conversion = convert_to_pdf(str(docx_path), str(OUTPUT_DIR))
        if not conversion["ok"]:
            flash(
                f"No se pudo exportar a PDF ({conversion['error']}). Se generó el DOCX.",
                "warn",
            )
            return redirect(
                url_for(
                    "guide_resumen",
                    guide_id=guide_id,
                    archivo=docx_path.name,
                    docx=docx_path.name,
                ),
                code=303,
            )
        pdf_path = Path(conversion["pdf"])
        flash("Documento PDF generado.", "ok")
        return redirect(
            url_for(
                "guide_resumen",
                guide_id=guide_id,
                archivo=pdf_path.name,
                docx=docx_path.name,
                pdf=1,
            ),
            code=303,
        )

    flash("Documento Word generado.", "ok")
    return redirect(
        url_for(
            "guide_resumen",
            guide_id=guide_id,
            archivo=docx_path.name,
            docx=docx_path.name,
        ),
        code=303,
    )


# ---------------------------------------------------------------------------
# Configuración de IA
# ---------------------------------------------------------------------------


@app.route("/configuracion", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        _check_csrf()
        update = {
            "enabled": bool(request.form.get("llm_enabled")),
            "base_url": (request.form.get("base_url") or "").strip(),
            "model": (request.form.get("model") or "").strip(),
        }
        api_key = (request.form.get("api_key") or "").strip()
        if api_key and api_key != "***":
            update["api_key"] = api_key
        save_config({"llm": update})
        flash("Configuración de IA guardada.", "ok")
        return redirect(url_for("settings"), code=303)
    return render_template(
        "configuracion.html",
        app_config=public_config(),
        active="configuracion",
    )


@app.post("/configuracion/probar")
def settings_test():
    _check_csrf()
    from services import llm

    if not llm.available():
        flash("La IA está deshabilitada o no tiene API key configurada.", "err")
        return redirect(url_for("settings"), code=303)
    try:
        reply = llm.chat(
            [{"role": "user", "content": "Responde únicamente con la palabra OK."}],
            temperature=0,
            timeout=20,
        )
    except Exception as exc:
        flash(f"No se pudo conectar con la IA: {exc}", "err")
        return redirect(url_for("settings"), code=303)
    flash(f"Conexión correcta. Respuesta: {str(reply)[:120]}", "ok")
    return redirect(url_for("settings"), code=303)


# ---------------------------------------------------------------------------
# API heredada (compatibilidad)
# ---------------------------------------------------------------------------


def _payload_guide():
    data = request.get_json(silent=True) or {}
    if "guide" in data:
        return normalize_guide(data["guide"])
    return normalize_guide(data)


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
