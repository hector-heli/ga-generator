import pdfplumber
from pathlib import Path

p = Path(r"formats\224312 AUTOMATIZACION DE SISTEMAS MECATRONICOS.pdf")
with pdfplumber.open(str(p)) as pdf:
    # Check pages 13-16 where the competencies start
    for i in range(12, 17):
        page = pdf.pages[i]
        txt = page.extract_text() or ""
        # Find "CONTENIDOS" in the text
        if "CONTENIDOS" in txt.upper():
            print(f"=== PAGE {i+1} ===")
            # Print portion around "4. CONTENIDOS"
            idx = txt.upper().find("CONTENIDOS")
            if idx >= 0:
                print(f"  Around CONTENIDOS: {repr(txt[max(0,idx-50):idx+100])})")
            # Also check for the exact marker
            if "4." in txt and "COMPETENCIA" in txt.upper():
                idx2 = txt.find("4.")
                if idx2 >= 0:
                    print(f"  Around '4.': {repr(txt[max(0,idx2-20):idx2+80])})")