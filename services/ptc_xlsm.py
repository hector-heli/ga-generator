"""Copia del formato PTC RAE con prellenado parcial.

La plantilla ``PTC  RAE xxx.xlsm`` contiene macros y nueve hojas con datos de
ficha, aprendices, horarios y cinco actividades/evidencias que el catálogo no
posee. Solo es posible prellenar el programa, la competencia y el resultado de
aprendizaje; el resto lo completa el instructor.

La edición se hace sobre el XML interno para conservar ``vbaProject.bin``,
imágenes, estilos y fórmulas. Si la transformación falla, se copia la plantilla
tal cual para no entregar un archivo incompleto.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import config

TEMPLATE_PATH = config.BASE_DIR / "templates_ga" / "PTC  RAE xxx.xlsm"
SHEET_XML = "xl/worksheets/sheet1.xml"

# Datos de ejemplo de la plantilla que no aplican al programa del catálogo.
_SAMPLE_CELLS = ("O6", "AD6", "O7", "AD7", "O8", "AD8", "O9", "O11", "E12")

_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _text(value):
    return str(value or "").strip()


def _label(codigo, nombre, fallback=""):
    codigo, nombre = _text(codigo), _text(nombre)
    if codigo and nombre:
        return f"{codigo} - {nombre}"
    return nombre or codigo or fallback


def _cell_pattern(coord):
    return re.compile(
        r'<c\b[^>]*?\br="%s"[^>]*?(?:/>|>.*?</c>)' % re.escape(coord),
        re.S,
    )


def _set_cell(xml, coord, value):
    pattern = _cell_pattern(coord)
    match = pattern.search(xml)
    if not match:
        return xml
    tag = match.group(0)
    style = re.search(r'\bs="(\d+)"', tag)
    style_attr = f' s="{style.group(1)}"' if style else ""
    value = _ILLEGAL_XML.sub("", _text(value))
    if value:
        replacement = (
            f'<c r="{coord}"{style_attr} t="inlineStr">'
            f'<is><t xml:space="preserve">{escape(value)}</t></is></c>'
        )
    else:
        replacement = f'<c r="{coord}"{style_attr}/>'
    return xml[: match.start()] + replacement + xml[match.end():]


def fill_sheet_xml(xml, programa, competencia, resultado):
    values = {
        "E7": _text(programa.get("denominacion")),
        "E8": _label(competencia.get("codigo_norma"), competencia.get("nombre")),
        "E11": _label(resultado.get("codigo"), resultado.get("denominacion")),
    }
    for coord in _SAMPLE_CELLS:
        xml = _set_cell(xml, coord, "")
    for coord, value in values.items():
        xml = _set_cell(xml, coord, value)
    return xml


def build_ptc_xlsm(programa, competencia, resultado, output_path):
    """Crea el PTC RAE con programa, competencia y RAE prellenados."""
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"No se encontró la plantilla: {TEMPLATE_PATH}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(TEMPLATE_PATH) as source:
            sheet = source.read(SHEET_XML).decode("utf-8")
            sheet = fill_sheet_xml(sheet, programa, competencia, resultado)
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as target:
                for info in source.infolist():
                    data = (
                        sheet.encode("utf-8")
                        if info.filename == SHEET_XML
                        else source.read(info.filename)
                    )
                    target.writestr(info, data)
    except Exception:
        shutil.copyfile(TEMPLATE_PATH, output_path)
    return output_path
