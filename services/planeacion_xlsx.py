"""Planeación pedagógica prediligenciada (formato GFPI-F-134 versión 05).

El formato oficial contiene logos e imágenes incrustadas. ``openpyxl`` elimina
los dibujos al guardar, por lo que el archivo se construye reescribiendo
directamente el XML de la hoja ``FASE`` dentro del XLSX. Así se conservan
imágenes, estilos, combinaciones de celdas y configuración de impresión.
"""

from __future__ import annotations

import re
import zipfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

import config

TEMPLATE_PATH = config.BASE_DIR / "templates_ga" / "GPFI-F-134V05Formatoplaneacionpedagogica.xlsx"
SHEET_XML = "xl/worksheets/sheet2.xml"

_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _text(value):
    return str(value or "").strip()


def _clean(value):
    return _ILLEGAL_XML.sub("", _text(value))


def _label(codigo, nombre, fallback=""):
    codigo, nombre = _text(codigo), _text(nombre)
    if codigo and nombre:
        return f"{codigo} - {nombre}"
    return nombre or codigo or fallback


def _items_for(items, resultado_id, key="texto"):
    """Textos de saberes/criterios aplicables a un RAE.

    Los ítems sin ``resultado_id`` aplican a toda la competencia; los ítems de
    otro resultado se excluyen.
    """
    texts = []
    for item in items or []:
        if isinstance(item, dict):
            rid = _text(item.get("resultado_id"))
            if rid and resultado_id and rid != str(resultado_id):
                continue
            value = item.get(key)
        else:
            value = item
        value = _text(value)
        if value:
            texts.append(value)
    return "\n".join(texts)


def _format_date(value):
    value = _text(value)
    if not value:
        return date.today().strftime("%d/%m/%Y")
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if match:
        return f"{match.group(3)}/{match.group(2)}/{match.group(1)}"
    return value


def _regional_centro(contexto, meta):
    explicit = _text(meta.get("regional_centro"))
    if explicit:
        return explicit
    partes = []
    regional = _text(contexto.get("proyecto_regional"))
    centro = _text(contexto.get("proyecto_centro"))
    if regional:
        partes.append(f"Regional: {regional}")
    if centro:
        partes.append(f"Centro: {centro}")
    return " - ".join(partes)


def _header_values(programa, competencia, resultado, contexto, meta):
    contexto = contexto or {}
    codigo = _text(programa.get("codigo"))
    version = _text(programa.get("version"))
    codigo_version = codigo
    if codigo and version:
        codigo_version = f"{codigo} - V{version}"
    elif version:
        codigo_version = f"V{version}"

    return {
        "E9": _format_date(meta.get("fecha_elaboracion")),
        "E10": _text(programa.get("denominacion")),
        "E11": _text(programa.get("tipo")),
        "E12": codigo_version,
        "E13": _text(contexto.get("proyecto_nombre")),
        "E14": _text(contexto.get("proyecto_codigo")),
        "E15": _text(meta.get("equipo_curricular")),
        "K15": _regional_centro(contexto, meta),
    }


def _row_values(programa, competencia, resultado, contexto, meta):
    contexto = contexto or {}
    resultado_id = resultado.get("id")
    ambientes = [
        _text(item.get("nombre") if isinstance(item, dict) else item)
        for item in programa.get("ambientes") or []
    ]
    materiales = []
    for item in programa.get("materiales") or []:
        if isinstance(item, dict):
            nombre = _text(item.get("nombre"))
            cantidad = _text(item.get("cantidad"))
            if nombre:
                materiales.append(f"{nombre} - {cantidad}" if cantidad else nombre)
        elif _text(item):
            materiales.append(_text(item))

    hours = resultado.get("duracion")
    try:
        hours = float(hours or 0)
    except (TypeError, ValueError):
        hours = 0

    return {
        "A18": _text(contexto.get("fase_nombre")),
        "B18": _text(contexto.get("actividad_nombre")),
        "C18": _label(competencia.get("codigo_norma"), competencia.get("nombre")),
        "D18": _label(resultado.get("codigo"), resultado.get("denominacion")),
        "E18": _items_for(competencia.get("conocimientos_saber"), resultado_id),
        "F18": _items_for(competencia.get("conocimientos_proceso"), resultado_id),
        "G18": _items_for(competencia.get("criterios"), resultado_id),
        "M18": "\n".join(name for name in ambientes if name),
        "N18": "\n".join(materiales),
    }, {"I18": hours if hours > 0 else None}


def _cell_pattern(coord):
    return re.compile(
        r'<c\b[^>]*?\br="%s"[^>]*?(?:/>|>.*?</c>)' % re.escape(coord),
        re.S,
    )


def _set_cell(xml, coord, value, numeric=False):
    """Reemplaza el contenido de una celda conservando su estilo."""
    pattern = _cell_pattern(coord)
    match = pattern.search(xml)
    if not match:
        return xml
    tag = match.group(0)
    style = re.search(r'\bs="(\d+)"', tag)
    style_attr = f' s="{style.group(1)}"' if style else ""

    if value is None or value == "":
        replacement = f'<c r="{coord}"{style_attr}/>'
    elif numeric:
        replacement = f'<c r="{coord}"{style_attr}><v>{value:g}</v></c>'
    else:
        replacement = (
            f'<c r="{coord}"{style_attr} t="inlineStr">'
            f'<is><t xml:space="preserve">{escape(_clean(value))}</t></is></c>'
        )
    return xml[: match.start()] + replacement + xml[match.end():]


def fill_sheet_xml(xml, values, numbers=None):
    """Aplica los valores a la hoja ``FASE`` y devuelve el XML resultante."""
    for coord, value in values.items():
        xml = _set_cell(xml, coord, value)
    for coord, value in (numbers or {}).items():
        xml = _set_cell(xml, coord, value, numeric=True)
    return xml


def build_planeacion_xlsx(programa, competencia, resultado, contexto, meta, output_path):
    """Genera una planeación pedagógica para un resultado de aprendizaje."""
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"No se encontró la plantilla: {TEMPLATE_PATH}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    meta = dict(meta or {})
    values = _header_values(programa, competencia, resultado, contexto, meta)
    row_values, numbers = _row_values(programa, competencia, resultado, contexto, meta)
    values.update(row_values)

    with zipfile.ZipFile(TEMPLATE_PATH) as source:
        sheet = source.read(SHEET_XML).decode("utf-8")
        sheet = fill_sheet_xml(sheet, values, numbers)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                data = sheet.encode("utf-8") if info.filename == SHEET_XML else source.read(info.filename)
                target.writestr(info, data)
    return output_path
