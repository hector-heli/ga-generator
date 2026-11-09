import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.defaults import total_hours
from services.docx_builder import build_docx
from services.importers.docx_importer import import_docx

DEFAULT_SOURCE = ROOT.parent / "RAE23 SISTEMAS EMBEBIDOS - ASM" / "GA_ RAE23_ SISTEMAS EMBEBIDOS.docx"


def main():
    parser = argparse.ArgumentParser(description="Genera un JSON de muestra y un DOCX a partir de una guía existente.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Guía DOCX de origen.")
    parser.add_argument("--sample", type=Path, default=ROOT / "data" / "sample_rae23.json", help="Ruta del JSON de salida.")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "GA_RAE23_muestra.docx", help="Ruta del DOCX generado.")
    args = parser.parse_args()

    if not args.source.exists():
        parser.error(f"No se encontró el archivo de origen: {args.source}")

    result = import_docx(args.source)
    guide = result["guide"]
    args.sample.parent.mkdir(parents=True, exist_ok=True)
    args.sample.write_text(json.dumps(guide, ensure_ascii=False, indent=2), encoding="utf-8")
    build_docx(guide, args.output)

    print("warnings:")
    for warning in result["warnings"]:
        print(" -", warning)
    print("programa:", guide["identificacion"]["programa"])
    print("codigo:", guide["identificacion"]["codigo_programa"])
    print("duracion:", guide["identificacion"]["duracion_horas"], "suma:", total_hours(guide))
    for moment_id, moment in guide["momentos"].items():
        print(moment_id, len(moment["actividades"]))
        for activity in moment["actividades"]:
            print("   -", activity["titulo"], activity["duracion_horas"], "h", len(activity["evidencias"]), "ev")
    print("glosario:", len(guide["glosario"]), "referencias:", len(guide["referencias"]))
    print("output:", args.output)


if __name__ == "__main__":
    main()
