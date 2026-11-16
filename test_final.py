import sys
sys.path.insert(0, r"D:\PROJECTS\ga-generator")
from services import catalog_importer
from pathlib import Path

p = Path(r"formats\224312 AUTOMATIZACION DE SISTEMAS MECATRONICOS.pdf")
d = catalog_importer.parse_design_pdf(p)

print("=== PROGRAMA ===")
print("codigo:", d["programa"]["codigo"])
print("horas_total:", d["programa"]["horas_total"])
print("version:", d["programa"].get("version"))
print("tipo:", d["programa"].get("tipo"))
print("titulo_obtenido:", d["programa"].get("titulo_obtenido"))

print("\n=== COMPETENCIAS ===")
print("Numero de competencias:", len(d["competencias"]))
total_rae = 0
for i, c in enumerate(d["competencias"]):
    code = c["codigo_norma"]
    name = c["nombre"][:50] if c["nombre"] else "(sin nombre)"
    rae = len(c["resultados"])
    total_rae += rae
    has_code = any(r.get("codigo") for r in c["resultados"])
    print(f"  {i+1}: code={code!r:12} name={name!r} rae={rae} codigo_resultado={has_code}")

print(f"\nTotal RAE: {total_rae}")

print("\n=== COMPETENCIA 999999999 ===")
for c in d["competencias"]:
    if c["codigo_norma"] == "999999999":
        print(f"nombre: {c['nombre']!r}")
        print(f"resultados: {c['resultados']}")

print("\n=== EXPECTATIONS ===")
print(f"Competencias >= 10: {len(d['competencias']) >= 10}")
print(f"Total RAE >= 40: {total_rae >= 40}")
has_proceso = any(c.get("conocimientos_proceso") for c in d["competencias"])
has_saber = any(c.get("conocimientos_saber") for c in d["competencias"])
print(f"Hay conocimientos_proceso: {has_proceso}")
print(f"Hay conocimientos_saber: {has_saber}")

print("\n=== WARNINGS (primeras 15) ===")
for w in d["warnings"][:15]:
    print(f"  - {w}")