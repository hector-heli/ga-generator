"""Guías de aprendizaje prediligenciadas desde el catálogo de programas.

Cada resultado de aprendizaje del catálogo produce una guía editable en DOCX
que usa la plantilla oficial ``GA_GFPI-F-135_plantilla.docx``. La guía se
prellena con programa, competencia, resultado y, cuando existe, el contexto del
proyecto formativo (proyecto, fase y actividad).
"""

from __future__ import annotations

from pathlib import Path

from services.defaults import empty_guide
from services.docx_builder import build_docx


def _text(value):
    return str(value or "").strip()


def _label(codigo, nombre, fallback=""):
    codigo = _text(codigo)
    nombre = _text(nombre)
    if codigo and nombre:
        return f"{codigo} - {nombre}"
    return nombre or codigo or fallback


def build_guide(programa, competencia, resultado, contexto=None):
    """Devuelve el diccionario de una guía mínima prellenada para un RAE."""
    contexto = contexto or {}
    guide = empty_guide()
    identification = guide["identificacion"]

    identification["programa"] = _text(programa.get("denominacion"))
    identification["codigo_programa"] = _text(programa.get("codigo"))
    identification["proyecto_formativo"] = _text(contexto.get("proyecto_nombre"))
    identification["fase"] = _text(contexto.get("fase_nombre"))
    identification["actividad_proyecto"] = _text(contexto.get("actividad_nombre"))
    identification["competencia"] = _label(
        competencia.get("codigo_norma"),
        competencia.get("nombre"),
    )
    identification["resultados_aprendizaje"] = _label(
        resultado.get("codigo"),
        resultado.get("denominacion"),
        "Resultado de aprendizaje",
    )
    identification["duracion_horas"] = float(resultado.get("duracion") or 0)
    identification["programa_id"] = _text(programa.get("id"))
    identification["proyecto_id"] = _text(contexto.get("proyecto_id"))
    identification["fase_id"] = _text(contexto.get("fase_id"))
    identification["actividad_id"] = _text(contexto.get("actividad_id"))
    identification["resultados_ids"] = [
        item for item in [_text(resultado.get("id"))] if item
    ]

    centro = _text(contexto.get("proyecto_centro"))
    if centro:
        guide["control_documento"]["autores"][0]["dependencia"] = centro

    return guide


def build_guide_docx(programa, competencia, resultado, contexto, output_path):
    """Genera el DOCX de la guía para un resultado de aprendizaje."""
    output_path = Path(output_path)
    guide = build_guide(programa, competencia, resultado, contexto)
    return build_docx(guide, output_path)
