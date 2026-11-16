import sys
sys.path.insert(0, r"D:\PROJECTS\ga-generator")
from services.pdf_layout import extract_pdf_text_tables
from pathlib import Path
import re

p = Path(r"formats\224312 AUTOMATIZACION DE SISTEMAS MECATRONICOS.pdf")
raw = extract_pdf_text_tables(str(p))

print("=== TABLES PAGE 1 ===")
tables = raw["pages"][0]["tables"]
for ti, row in enumerate(tables):
    if ti < 3:
        print(f"Row {ti}: {row}")

# Now try the _extract_program_basic logic
print("\n=== Testing program basic extraction ===")
tables = raw["pages"][0]["tables"]
for row in tables:
    if not row or len(row) < 2:
        continue
    label = row[0].strip() if row[0] else ""
    value = row[1].strip() if row[1] else ""
    label_f = label.replace("\n", " ").strip()
    print(f"Label: {label_f!r} -> Value: {value!r}")