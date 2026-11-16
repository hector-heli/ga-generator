import pdfplumber
from pathlib import Path
import re, unicodedata

def norm(text):
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"Pagina\s*\d+\s*de\s*\d+.*", " ", t, flags=re.I)
    t = re.sub(r"^[ \t]*(LINEA TECNOLOGICA|RED TECNOLOGICA|RED DE CONOCIMIENTO).*$", " ", t, flags=re.I | re.M)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t

p = Path(r"formats\224312 AUTOMATIZACION DE SISTEMAS MECATRONICOS.pdf")
with pdfplumber.open(str(p)) as pdf:
    pages_text = [p.extract_text() or "" for p in pdf.pages]
full = "\n".join(pages_text)
n = norm(full)

# Check for the marker
marker = re.compile(r"4\.\s*CONTENIDOS CURRICULARES DE LA COMPETENCIA", re.I)
matches = list(marker.finditer(n))
print(f"Marker matches: {len(matches)}")
for m in matches[:3]:
    start = max(0, m.start() - 60)
    end = min(len(n), m.end() + 60)
    print(f"  Page pos {m.start()}: ...{n[start:end]}...")

# Also check original text
print(f"\nOriginal has marker: {bool(re.search(marker, full))}")