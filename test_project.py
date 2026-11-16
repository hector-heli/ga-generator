import sys
sys.path.insert(0, r"D:\PROJECTS\ga-generator")
from services import project_importer
from pathlib import Path

p = Path(r"formats\Reporte Proyecto Formativo - 2343811 - AUTOMATIZACIÓN Y OPTIMIZACIÓN .pdf")
d = project_importer.parse_project_pdf(str(p))

print("=== PROYECTO ===")
print("codigo_sofia:", d["proyecto"].get("codigo_sofia"))
print("programa_codigo:", d["proyecto"].get("programa_codigo"))
print("programa_version:", d["proyecto"].get("programa_version"))
print("nombre:", d["proyecto"].get("nombre"))
print("centro_formacion:", d["proyecto"].get("centro_formacion"))
print("regional:", d["proyecto"].get("regional"))
print("tiempo_meses:", d["proyecto"].get("tiempo_meses"))
print("total_resultados:", d["proyecto"].get("total_resultados"))
print()

print("=== FASES ===")
for i, f in enumerate(d["fases"][:3]):
    print(f"Fase {i+1}: {f['nombre']}")
    print(f"  actividad: {f['actividad'][:50] if f.get('actividad') else None}")
    print(f"  resultado_codigo: {f.get('resultado_codigo')}")
    print(f"  resultado_label: {f.get('resultado_label')}")
    print(f"  duracion: {f.get('duracion')}")
    print(f"  competencia_codigo: {f.get('competencia_codigo')}")
    print(f"  competencia_nombre: {f.get('competencia_nombre')[:30] if f.get('competencia_nombre') else None}")
    print()

print("Meta:", d["meta"])
print("Warnings:", d["warnings"][:10])