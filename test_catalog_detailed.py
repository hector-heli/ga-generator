import sys
sys.path.insert(0, r"D:\PROJECTS\ga-generator")

from pathlib import Path
from services import catalog_importer

p = Path(r"formats\224312 AUTOMATIZACION DE SISTEMAS MECATRONICOS.pdf")
d = catalog_importer.parse_design_pdf(p)
prog = d["programa"]
print("=== PROGRAMA ===")
print("codigo:", prog["codigo"])
print("horas_total:", prog["horas_total"])
print("version:", prog.get("version"))
print("tipo:", prog.get("tipo"))
print("titulo_obtenido:", prog.get("titulo_obtenido"))

print("\n=== COMPETENCIAS ===")
print(f"Numero de competencias: {len(d['competencias'])}")
total_rae = 0
for i, c in enumerate(d["competencias"]):
    code = c["codigo_norma"]
    name = c["nombre"][:50] if c["nombre"] else "(sin nombre)"
    rae = len(c["resultados"])
    total_rae += rae
    has_code = any(r.get("codigo") for r in c["resultados"])
    print(f"  {i+1}: code={code!r:12} name={name!r} rae={rae} rae_con_codigo={has_code}")

print(f"\nTotal RAE: {total_rae}")

# Check the 999999999 competency
for c in d["competencias"]:
    if c["codigo_norma"] == "999999999":
        print(f"\n=== COMPETENCIA 999999999 ===")
        print(f"nombre: {c['nombre']!r}")
        print(f"resultados: {c['resultados']}")

# Check expectations from checkpoint
print(f"\n=== EXPECTATIONS ===")
print(f"Competencias >= 10: {len(d['competencias']) >= 10}")
print(f"Total RAE >= 40: {total_rae >= 40}")

# Check for conocimientos/proceso/saber
has_proceso = any(c.get("conocimientos_proceso") for c in d["competencias"])
has_saber = any(c.get("conocimientos_saber") for c in d["competencias"])
print(f"Hay conocimientos_proceso: {has_proceso}")
print(f"Hay conocimientos_saber: {has_saber}")

# Warnings
print(f"\nWarnings ({len(d['warnings'])}):")
for w in d["warnings"][:15]:
    print(f"  - {w}")