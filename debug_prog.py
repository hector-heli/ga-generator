import sys
sys.path.insert(0, r"D:\PROJECTS\ga-generator")

from pathlib import Path
import pdfplumber
import unicodedata
import re

def norm(text):
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"\(cid:\d+\)", " ", t, flags=re.I)
    t = re.sub(r"\(cid:\d+\s*\)", " ", t, flags=re.I)
    t = re.sub(r"cid:\d+", " ", t, flags=re.I)
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

# Check what the program basic extraction would see
print("=== Checking program extraction patterns ===")

# 1. Código
m = re.search(r"\b(\d{5,})\b", n[:3000])
print(f"Código match: {m.group(1) if m else 'None'} (from first 3000 chars)")

# 2. Versión
m = re.search(r"1\.3\.?\s*Versi[oó]n\s*(?:\n)?Programa:\s*([^\n]{1,80})", n, re.I)
print(f"Versión match: {m.group(1) if m else 'None'}")

# 3. Denominación - try the first pattern
m = re.search(r"\n([A-ZÁÉÍÓÚÑ0-9][A-ZÁÉÍÓÚÑ0-9 .,/&()_-]{7,})\s*\n\s*1\.\s*INFORMACION", full)
print(f"Denominación patrón 1: {m.group(1) if m else 'None'}")

# 4. Denominación - try the 1.1 pattern
m = re.search(r"1\.1\s*Denominaci[oó]n[:\s]*(.+?)\s*1\.2", n, re.S | re.I)
print(f"Denominación patrón 2: {m.group(1) if m else 'None'}")

# 5. Horas
m = re.search(r"Total:\s*(\d+)\s*horas", n, re.I)
print(f"Total horas: {m.group(1) if m else 'None'}")

# 6. Tipo
m = re.search(r"1\.6\s*Tipo\s*de\s*programa\s*([^\n]+)", n, re.I)
print(f"Tipo: {m.group(1) if m else 'None'}")

# 7. Título
m = re.search(r"1\.7\s*T[ií]tulo\s*o\s*certificado\s*que\s*obtendr[aá]\s*([^\n]+)", n, re.S | re.I)
print(f"Título: {m.group(1) if m else 'None'}")