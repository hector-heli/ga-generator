import sys
sys.path.insert(0, r"D:\PROJECTS\ga-generator")

from pathlib import Path
from services import catalog_importer
import json

p = Path(r"formats\224312 AUTOMATIZACION DE SISTEMAS MECATRONICOS.pdf")
d = catalog_importer.parse_design_pdf(p)
prog = d["programa"]
print("programa codigo:", prog["codigo"])
print("programa horas_total:", prog["horas_total"])
print("num competencias:", len(d["competencias"]))
total = sum(len(c.get("resultados", [])) for c in d["competencias"])
print("total RAE:", total)
print("warnings count:", len(d["warnings"]))
for j, c in enumerate(d["competencias"][:5]):
    code = c["codigo_norma"]
    name = c["nombre"][:45] if c["nombre"] else "(sin nombre)"
    rae = len(c["resultados"])
    print(f"  comp {j+1}: code={code!r:12} name={name!r} rae={rae}")

# Check specific known issues
# 1. competencia 999999999 should have a name
for c in d["competencias"]:
    if c["codigo_norma"] == "999999999":
        print(f"\nCompetencia especial: code={c['codigo_norma']!r} name={c['nombre']!r}")

# 2. codigo_norma 210201501 should NOT concatenate as 2102015014.2
for c in d["competencias"]:
    if c["codigo_norma"] and "210201501" in c["codigo_norma"]:
        print(f"\nCuidado: codigo_norma parececoncatentado: {c['codigo_norma']!r}")

# 3. Total de competencias >= 10
print(f"\nCompetencias >= 10: {len(d['competencias']) >= 10}")

# 4. Al menos algunos conocimientos/criterios extraídos
has_know = any(c.get("conocimientos_proceso") or c.get("conocimientos_saber") for c in d["competencias"])
print(f"Hay conocimientos/proceso: {has_know}")