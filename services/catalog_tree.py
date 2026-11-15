"""Construcción del andamiaje de carpetas del catálogo de programas.

El andamiaje se entrega como un ZIP generado al vuelo. Incluye:

* una carpeta raíz ``[código]-[denominación]`` (con versión si existe);
* una carpeta por competencia;
* una carpeta por resultado de aprendizaje;
* los PDF de diseño curricular y proyecto formativo en la raíz;
* la guía de aprendizaje, la planeación pedagógica y el PTC RAE dentro de
  cada carpeta de resultado.
"""

from __future__ import annotations

import io
import re
import tempfile
import unicodedata
import zipfile
from pathlib import Path

from services import catalog_guides, catalog_store, planeacion_xlsx, ptc_xlsm

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")
_MAX_NAME = 90
_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_name(text, fallback="Sin nombre"):
    """Limpia un nombre para usarlo como carpeta o archivo en Windows/ZIP."""
    value = unicodedata.normalize("NFC", str(text or ""))
    value = _INVALID_CHARS.sub(" ", value)
    value = _WHITESPACE.sub(" ", value).strip(" .")
    if not value:
        value = fallback
    if value.upper() in _RESERVED_NAMES:
        value = f"_{value}"
    if len(value) > _MAX_NAME:
        value = value[:_MAX_NAME].rstrip(" .")
    return value or fallback


def _dedupe(name, seen):
    """Evita que dos hermanos terminen en la misma carpeta (Windows no distingue mayúsculas)."""
    candidate = name
    key = candidate.casefold()
    if key not in seen:
        seen.add(key)
        return candidate
    index = 2
    while True:
        candidate = f"{name} ({index})"
        key = candidate.casefold()
        if key not in seen:
            seen.add(key)
            return candidate
        index += 1


def programa_root(programa):
    codigo = str(programa.get("codigo") or "").strip() or "SinCodigo"
    denominacion = str(programa.get("denominacion") or "").strip()
    base = f"{codigo}-{denominacion}" if denominacion else codigo
    version = str(programa.get("version") or "").strip()
    if version:
        base = f"{base}-v{version}"
    return sanitize_name(base, "Programa")


def competencia_folder(competencia):
    codigo = str(competencia.get("codigo_norma") or "").strip()
    nombre = str(competencia.get("nombre") or "").strip()
    if codigo and nombre:
        return sanitize_name(f"{codigo} - {nombre}", "Competencia")
    return sanitize_name(nombre or codigo, "Competencia")


def resultado_folder(resultado):
    codigo = str(resultado.get("codigo") or "").strip()
    nombre = str(resultado.get("denominacion") or "").strip()
    if codigo and nombre:
        return sanitize_name(f"{codigo} - {nombre}", "RAE")
    return sanitize_name(nombre or codigo, "RAE")


def build_tree(programa):
    """Devuelve la estructura lógica que se mostrará y se escribirá en el ZIP."""
    root = programa_root(programa)
    competencias = []
    seen_comp = set()
    for competencia in programa.get("competencias") or []:
        comp_name = _dedupe(competencia_folder(competencia), seen_comp)
        resultados = []
        seen_rae = set()
        for resultado in competencia.get("resultados") or []:
            rae_name = _dedupe(resultado_folder(resultado), seen_rae)
            resultados.append(
                {
                    "name": rae_name,
                    "resultado": resultado,
                    "files": [
                        guide_filename(resultado),
                        planeacion_filename(resultado),
                        ptc_filename(resultado),
                    ],
                }
            )
        competencias.append(
            {
                "name": comp_name,
                "competencia": competencia,
                "resultados": resultados,
            }
        )
    return {"root": root, "competencias": competencias}


def _dataset_name(resultado):
    codigo = sanitize_name(resultado.get("codigo") or "RAE", "RAE")
    nombre = sanitize_name(resultado.get("denominacion") or "Resultado", "Resultado")
    return codigo, nombre


def guide_filename(resultado):
    codigo, nombre = _dataset_name(resultado)
    return f"{sanitize_name(f'GA - {codigo} - {nombre}', 'GA')}.docx"


def planeacion_filename(resultado):
    codigo, nombre = _dataset_name(resultado)
    return f"{sanitize_name(f'Planeacion pedagogica - {codigo} - {nombre}', 'Planeacion pedagogica')}.xlsx"


def ptc_filename(resultado):
    codigo, nombre = _dataset_name(resultado)
    return f"{sanitize_name(f'PTC RAE - {codigo} - {nombre}', 'PTC RAE')}.xlsm"


def zip_filename(programa):
    return f"{programa_root(programa)}.zip"


def _pdf_filename(original, prefix):
    name = Path(str(original or "")).name
    name = sanitize_name(name or f"{prefix}.pdf", f"{prefix}.pdf")
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return sanitize_name(f"{prefix} - {name}", f"{prefix}.pdf")


def build_zip(programa, pdf_diseno=None, pdf_proyecto=None, meta=None):
    """Construye el andamiaje completo en memoria y devuelve un ``BytesIO``.

    ``pdf_diseno`` y ``pdf_proyecto`` son tuplas ``(nombre_original, bytes)``.
    ``meta`` puede incluir ``equipo_curricular``, ``regional``, ``centro`` y
    ``fecha_elaboracion`` para prellenar la planeación pedagógica.
    """
    tree = build_tree(programa)
    root = tree["root"]
    meta = dict(meta or {})
    archive = io.BytesIO()

    with tempfile.TemporaryDirectory(prefix="andamiaje_") as tmp:
        work = Path(tmp)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{root}/", b"")
            if pdf_diseno and pdf_diseno[1]:
                zf.writestr(
                    f"{root}/{_pdf_filename(pdf_diseno[0], 'Diseño curricular')}",
                    pdf_diseno[1],
                )
            if pdf_proyecto and pdf_proyecto[1]:
                zf.writestr(
                    f"{root}/{_pdf_filename(pdf_proyecto[0], 'Proyecto formativo')}",
                    pdf_proyecto[1],
                )

            index = 0
            for competencia in tree["competencias"]:
                comp_path = f"{root}/{competencia['name']}"
                zf.writestr(f"{comp_path}/", b"")
                for rae in competencia["resultados"]:
                    rae_path = f"{comp_path}/{rae['name']}"
                    zf.writestr(f"{rae_path}/", b"")
                    resultado = rae["resultado"]
                    contexto = catalog_store.get_resultado_contexto(resultado.get("id")) or {}

                    index += 1
                    guide_path = work / f"guia_{index}.docx"
                    catalog_guides.build_guide_docx(
                        programa,
                        competencia["competencia"],
                        resultado,
                        contexto,
                        guide_path,
                    )
                    zf.write(guide_path, f"{rae_path}/{guide_filename(resultado)}")

                    planeacion_path = work / f"planeacion_{index}.xlsx"
                    planeacion_xlsx.build_planeacion_xlsx(
                        programa,
                        competencia["competencia"],
                        resultado,
                        contexto,
                        meta,
                        planeacion_path,
                    )
                    zf.write(
                        planeacion_path,
                        f"{rae_path}/{planeacion_filename(resultado)}",
                    )

                    ptc_path = work / f"ptc_{index}.xlsm"
                    ptc_xlsm.build_ptc_xlsm(
                        programa,
                        competencia["competencia"],
                        resultado,
                        ptc_path,
                    )
                    zf.write(ptc_path, f"{rae_path}/{ptc_filename(resultado)}")

    archive.seek(0)
    return archive
