from pathlib import Path
from services import catalog_importer
import sys

p = Path(r"formats\224312 AUTOMATIZACION DE SISTEMAS MECATRONICOS.pdf")
d = catalog_importer.parse_design_pdf(p)
prog = d["programa"]
print("programa codigo:", prog["codigo"])
print("programa horas_total:", prog["horas_total"])
print("num competencias:", len(d["competencias"]))
print("warnings:", d["warnings"][:10])