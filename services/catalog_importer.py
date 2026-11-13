import re
import unicodedata

from pypdf import PdfReader


def _strip_accents(text):
    t = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in t if not unicodedata.combining(c))


def _norm(text):
    t = _strip_accents(text)
    t = re.sub(r"Pagina\s*\d+\s*de\s*\d+.*", " ", t, flags=re.I)
    t = re.sub(r"^[ \t]*(LINEA TECNOLOGICA|RED TECNOLOGICA|RED DE CONOCIMIENTO).*$", " ", t, flags=re.I | re.M)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t


def _clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def _num(text):
    try:
        return float(str(text).replace(",", "."))
    except Exception:
        return 0.0


def _extract_basic(text):
    raw = text or ""
    data = {
        "denominacion": "", "codigo": "", "version": "", "vigencia": "",
        "horas_lectiva": 0.0, "horas_productiva": 0.0, "horas_total": 0.0,
        "tipo": "", "titulo_obtenido": "", "justificacion": "",
    }

    m = re.search(r"\n([A-ZÁÉÍÓÚÑ0-9][A-ZÁÉÍÓÚÑ0-9 .,/&()_-]{7,})\s*\n\s*1\.\s*INFORMACION", raw)
    if m:
        data["denominacion"] = _clean(m.group(1)).strip(" .:-")
    if not data["denominacion"]:
        m = re.search(r"1\.1\s*Denominaci[oó]n\s*(?:del\s*Programa:)?\s*(.*?)\s*1\.2", raw, re.S | re.I)
        if m:
            val = _clean(m.group(1))
            if "vigente" not in val.lower():
                data["denominacion"] = val.strip(" .:-")

    m = re.search(r"1\.2\.?\s*C[oó]digo\s*(?:\n)?Programa:(.{0,240})", raw, re.S | re.I)
    if m:
        cm = re.search(r"\b(\d{5,})\b", m.group(1))
        if cm:
            data["codigo"] = cm.group(1)
    if not data["codigo"]:
        cm = re.search(r"\b(\d{6,})\b", raw[:2500])
        if cm:
            data["codigo"] = cm.group(1)

    m = re.search(r"1\.3\.?\s*Versi[oó]n\s*(?:\n)?Programa:\s*([^\n]{1,80})", raw, re.I)
    if m:
        version = _clean(m.group(1))
        if re.fullmatch(r"\d{1,4}", version or ""):
            data["version"] = version

    m = re.search(r"(\d{2}/\d{2}/\d{4})\s*1\.4\.?\s*Vigencia", raw, re.S | re.I)
    if not m:
        m = re.search(r"1\.4\.?\s*Vigencia.*?(\d{2}/\d{2}/\d{4})", raw, re.S | re.I)
    if m:
        data["vigencia"] = m.group(1)

    m = re.search(r"(\d+)\s*horas\s*Etapa\s*Lectiva", raw, re.I)
    if m:
        data["horas_lectiva"] = _num(m.group(1))
    m = re.search(r"\(horas\)\s*(\d+)\s*horas", raw, re.S | re.I)
    if not m:
        m = re.search(r"Etapa\s*Productiva:.*?Total:\s*\d+\s*horas.*?(\d+)\s*horas", raw, re.S | re.I)
    if m:
        data["horas_productiva"] = _num(m.group(1))
    m = re.search(r"Total:\s*(\d+)\s*horas", raw, re.I)
    if m:
        data["horas_total"] = _num(m.group(1))

    m = re.search(r"1\.6\s*Tipo\s*de\s*programa\s*([^\n]+)", raw, re.I)
    if m:
        data["tipo"] = _clean(m.group(1)).strip(" .:-")
    m = re.search(r"1\.7\s*T[ií]tulo\s*o\s*certificado\s*que\s*obtendr[aá]\s*([^\n]+)", raw, re.S | re.I)
    if m:
        data["titulo_obtenido"] = _clean(m.group(1)).strip(" .:-")
    m = re.search(r"1\.8\s*Justificaci[oó]n\s*(.*?)(?:\nESTADO ACTUAL|\n2\.\s|\Z)", raw, re.S | re.I)
    if m:
        data["justificacion"] = _clean(m.group(1))[:6000]
    return data


def _extract_ambientes_materiales(full_text):
    t = _norm(full_text)
    ambientes = []
    materiales = []
    sec = re.search(
        r"3\.4\s*DOTACION\s*MINIMA\s*DE\s*AMBIENTES.*?(?=4\.\s*CONTENIDOS\s*CURRICULARES)",
        t,
        re.S | re.I,
    )
    if not sec:
        return ambientes, materiales
    s = sec.group(0)

    m = re.search(
        r"areas\s*de\s*conocimiento:\s*(.+?)(?:\.|OBSERVACIONES)",
        s,
        re.S | re.I,
    )
    if m:
        for area in re.split(r",|\by\b", _clean(m.group(1))):
            area = _clean(area).strip(" .:-")
            if area and len(area) > 2:
                ambientes.append({"categoria": "Área de conocimiento", "nombre": area})

    mapping = [
        ("3.4.2", r"Maquinaria\s+y\s+Equipo\s+Especializado", "Maquinaria y equipo"),
        ("3.4.3", r"Software\s+Especializado", "Software"),
        ("3.4.4", r"Herramientas\s+Especializadas", "Herramientas"),
        ("3.4.5", r"Simuladores\s+espec[ií]ficos\s+del\s+entorno", "Simuladores"),
        ("3.4.6", r"Muebles\s+colaborativos", "Muebles"),
        ("3.4.7", r"Tecnolog[ií]as\s+de\s+la\s+informaci[oó]n\s+y\s+las\s+comunicaciones", "TIC"),
        ("3.4.8", r"Elementos\s+y\s+condiciones\s+relacionadas\s+con\s+la\s+seguridad.*?ambiente:?", "Seguridad y salud"),
    ]
    for idx, (code, label, category) in enumerate(mapping):
        start = re.search(r"\b" + re.escape(code) + r"\b", s)
        if not start:
            continue
        nxt = mapping[idx + 1][0] if idx + 1 < len(mapping) else "4."
        end = re.search(r"\b" + re.escape(nxt) + r"\b", s[start.end():])
        body = s[start.end(): start.end() + end.start()] if end else s[start.end():]
        body = re.sub(r"^\s*" + label, "", body, flags=re.I | re.S)
        for line in body.split("\n"):
            line = _clean(line).strip(" .:;-•\t")
            if not line or len(line) < 3:
                continue
            if re.match(r"^(pagina|3\.4\.|4\.\s)", line, re.I):
                continue
            if re.match(r"^(linea|red)\s+(tecnologica|de conocimiento)", line, re.I):
                continue
            if line.lower() in {"especializado", "especializadas", "colaborativos"}:
                continue
            qty = re.match(r"^(\d+)\s+(.+)$", line)
            cantidad = qty.group(1) if qty else ""
            nombre = qty.group(2) if qty else line
            materiales.append({"categoria": category, "nombre": nombre, "cantidad": cantidad})

    def dedupe(items):
        seen = set()
        out = []
        for item in items:
            key = (item.get("categoria", ""), item.get("nombre", "").lower())
            if not item.get("nombre") or key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    return dedupe(ambientes), dedupe(materiales)


def _items_from_text(text):
    items = []
    for line in re.split(r"\n|•|;", text or ""):
        line = _clean(line).strip(" .:-•")
        if len(line) < 4:
            continue
        if re.match(r"^(4\.\d|pagina|denominacion|resultados de aprendizaje)", line, re.I):
            continue
        items.append(line)
    return items


def _parse_raes(sec):
    t = "\n".join(_clean(line) for line in (sec or "").splitlines() if _clean(line))
    idx = t.upper().find("DENOMINACION")
    if idx >= 0:
        t = t[idx + len("DENOMINACION"):]
    t = re.split(r"\b4\.6\b", t, maxsplit=1)[0]
    if not t.strip():
        return []

    chunks = []
    buffer = []
    for line in t.split("\n"):
        line = _clean(line)
        if not line:
            continue
        buffer.append(line)
        hm = re.search(r"(\d+(?:[.,]\d+)?)\s*H\b\.?\s*$", line, re.I)
        if hm:
            body = " ".join(buffer)
            duration = _num(hm.group(1))
            body = re.sub(r"\s*\d+(?:[.,]\d+)?\s*H\b\.?\s*$", "", body, flags=re.I)
            chunks.append((body, duration))
            buffer = []
    if buffer:
        chunks.append((" ".join(buffer), 0.0))

    results = []
    for body, duration in chunks:
        body = _clean(body).strip(" .:-")
        if not body:
            continue
        cm = re.match(r"(RAE\s*\d+)\s*[:\-]?\s*", body, re.I)
        code = ""
        if cm:
            code = re.sub(r"\s+", "", cm.group(1)).upper()
            body = body[cm.end():].strip(" .:-")
        if not body or body.upper() in {"DENOMINACION", "RESULTADOS DE APRENDIZAJE"}:
            continue
        results.append({"codigo": code, "denominacion": body, "duracion": duration})

    if results:
        return results

    for m in re.finditer(r"(RAE\s*\d+)\s*:\s*(.*?)(?=\s*(?:RAE\s*\d+\s*:|$))", t, re.S | re.I):
        code = re.sub(r"\s+", "", m.group(1)).upper()
        body = _clean(m.group(2))
        hm = re.search(r"(\d+(?:[.,]\d+)?)\s*H\b", body, re.I)
        duration = _num(hm.group(1)) if hm else 0.0
        denom = re.sub(r"\s*\d+(?:[.,]\d+)?\s*H\b\.?\s*$", "", body, flags=re.I).strip(" .:-")
        if denom:
            results.append({"codigo": code, "denominacion": denom, "duracion": duration})
    return results


def _split_by_rae(section_text):
    t = section_text or ""
    matches = list(re.finditer(r"\b(RAE\s*\d+)\s*:", t, re.I))
    if not matches:
        return [(None, t)]
    chunks = []
    pre = t[:matches[0].start()]
    if _clean(pre):
        chunks.append((None, pre))
    for i, m in enumerate(matches):
        code = re.sub(r"\s+", "", m.group(1)).upper()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(t)
        chunks.append((code, t[start:end]))
    return chunks


def _parse_competence_block(block, index):
    b = block
    warnings = []
    comp = {
        "codigo_norma": "", "nombre": "", "duracion": 0.0, "orden": index,
        "resultados": [], "conocimientos_proceso": [], "conocimientos_saber": [], "criterios": [],
    }
    m = re.search(r"(\d{7,12}(?:\.\d+)?)", b)
    if m:
        comp["codigo_norma"] = m.group(1)
    m = re.search(r"4\.3\s*NOMBRE\s*DE\s*LA\s*COMPETENCIA\s*(.*?)\s*4\.5", b, re.S | re.I)
    if m:
        comp["nombre"] = _clean(m.group(1)).strip(" .:")
    m = re.search(r"4\.4\s*DURACI[ÓO]N\s*M[ÁA]XIMA.*?\(Horas\)\s*([\d\.,]+)\s*horas", b, re.S | re.I)
    if m:
        comp["duracion"] = _num(m.group(1))

    m = re.search(r"4\.5\s*RESULTADOS\s*DE\s*APRENDIZAJE\s*(.*?)\s*4\.6", b, re.S | re.I)
    comp["resultados"] = _parse_raes(m.group(1) if m else "")

    m = re.search(r"4\.6\.1\s*CONOCIMIENTOS\s*DE\s*PROCESO\s*(.*?)\s*4\.6\.2", b, re.S | re.I)
    proc = m.group(1) if m else ""
    m = re.search(r"4\.6\.2\s*CONOCIMIENTOS\s*DEL\s*SABER\s*(.*?)\s*4\.7", b, re.S | re.I)
    if not m:
        m = re.search(r"4\.6\.2\s*CONOCIMIENTOS\s*DEL\s*SABER\s*(.*?)\s*4\.8", b, re.S | re.I)
    saber = m.group(1) if m else ""
    m = re.search(r"4\.7\s*CRITERIOS\s*DE\s*EVALUACI[ÓO]N\s*(.*?)\s*4\.8", b, re.S | re.I)
    if not m:
        m = re.search(r"4\.7\s*CRITERIOS\s*DE\s*EVALUACI[ÓO]N\s*(.*?)\s*(?:4\.9|4\.10|5\.|$)", b, re.S | re.I)
    crit = m.group(1) if m else ""

    for code, text in _split_by_rae(proc):
        for item in _items_from_text(text):
            comp["conocimientos_proceso"].append({"rae_codigo": code, "texto": item})
    for code, text in _split_by_rae(saber):
        for item in _items_from_text(text):
            comp["conocimientos_saber"].append({"rae_codigo": code, "texto": item})
    for code, text in _split_by_rae(crit):
        for item in _items_from_text(text):
            comp["criterios"].append({"rae_codigo": code, "texto": item})

    if not comp["nombre"]:
        warnings.append(f"Competencia {index + 1}: nombre no reconocido.")
    if not comp["resultados"]:
        warnings.append(f"Competencia {index + 1} ({comp['nombre'] or comp['codigo_norma']}): no se detectaron RAE.")
    rae_sum = sum(r.get("duracion", 0) or 0 for r in comp["resultados"])
    if comp["duracion"] and rae_sum and abs(comp["duracion"] - rae_sum) > 0.5:
        warnings.append(f"Competencia {index + 1} ({comp['nombre'][:60]}): horas competencia {comp['duracion']} vs suma RAE {rae_sum}.")
    for r in comp["resultados"]:
        if not r.get("duracion"):
            warnings.append(f"RAE {r.get('codigo') or '(sin código)'} sin horas en {comp['nombre'][:50]}.")
        if not r.get("codigo") and r.get("denominacion"):
            warnings.append(f"Resultado sin código RAE en {comp['nombre'][:50]}.")
    return comp, warnings


def parse_design_pdf(path):
    reader = PdfReader(str(path))
    pages = [p.extract_text() or "" for p in reader.pages]
    full = "\n".join(pages)
    norm_full = _norm(full)
    program = _extract_basic(pages[0] if pages else "")
    if not program.get("version"):
        program["version"] = "1"
    ambientes, materiales = _extract_ambientes_materiales(full)
    parts = re.split(r"4\.\s*CONTENIDOS\s*CURRICULARES\s*DE\s*LA\s*COMPETENCIA", norm_full, flags=re.I)
    competencias = []
    warnings = []
    for i, part in enumerate(parts[1:]):
        comp, w = _parse_competence_block(part, i)
        competencias.append(comp)
        warnings.extend(w)
    if not competencias:
        warnings.append("No se detectaron bloques de competencias en el PDF.")
    total_comp = sum(c.get("duracion", 0) or 0 for c in competencias)
    if program.get("horas_total") and abs(program["horas_total"] - total_comp) > 1:
        warnings.append(f"Horas totales del programa ({program['horas_total']}) difieren de la suma de competencias ({total_comp}).")
    result_count = sum(len(c.get("resultados", [])) for c in competencias)
    return {
        "programa": program,
        "competencias": competencias,
        "ambientes": ambientes,
        "materiales": materiales,
        "meta": {
            "source": str(path),
            "competencias_count": len(competencias),
            "resultados_count": result_count,
            "horas_competencias": total_comp,
        },
        "warnings": warnings[:80],
    }
