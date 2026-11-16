import sys
sys.path.insert(0, r"D:\PROJECTS\ga-generator")

from services.pdf_layout import extract_pdf_text_tables
from pathlib import Path
import re

p = Path(r"formats\224312 AUTOMATIZACION DE SISTEMAS MECATRONICOS.pdf")
raw = extract_pdf_text_tables(str(p))

print("Pages:", len(raw.get("pages", [])))
if raw.get("pages"):
    pg = raw["pages"][0]
    print("Page 0 tables:", len(pg.get("tables", [])))
    for ti, tbl in enumerate(pg.get("tables", [])):
        print(f"\nTable {ti}: {len(tbl)} rows")
        for ri, row in enumerate(tbl[:6]):
            print(f"  Row {ri}: {row}")
        # Check if any row has "1.2" in label
        for row in tbl:
            if row and len(row) >= 2:
                label = row[0].strip() if row[0] else ""
                val = row[1].strip() if row[1] else ""
                label_f = label.replace("\n", " ").strip()
                print(f"    Label: {label_f!r} -> Value: {val!r}")