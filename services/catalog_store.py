import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import config

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS programas (
    id TEXT PRIMARY KEY,
    denominacion TEXT NOT NULL DEFAULT '',
    codigo TEXT NOT NULL DEFAULT '',
    version TEXT NOT NULL DEFAULT '',
    vigencia TEXT NOT NULL DEFAULT '',
    horas_lectiva REAL NOT NULL DEFAULT 0,
    horas_productiva REAL NOT NULL DEFAULT 0,
    horas_total REAL NOT NULL DEFAULT 0,
    tipo TEXT NOT NULL DEFAULT '',
    titulo_obtenido TEXT NOT NULL DEFAULT '',
    justificacion TEXT NOT NULL DEFAULT '',
    fuente TEXT NOT NULL DEFAULT '',
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL,
    UNIQUE(codigo, version)
);
CREATE TABLE IF NOT EXISTS competencias (
    id TEXT PRIMARY KEY,
    programa_id TEXT NOT NULL,
    codigo_norma TEXT NOT NULL DEFAULT '',
    nombre TEXT NOT NULL DEFAULT '',
    duracion REAL NOT NULL DEFAULT 0,
    orden INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (programa_id) REFERENCES programas(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS resultados (
    id TEXT PRIMARY KEY,
    competencia_id TEXT NOT NULL,
    codigo TEXT NOT NULL DEFAULT '',
    denominacion TEXT NOT NULL DEFAULT '',
    duracion REAL NOT NULL DEFAULT 0,
    orden INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (competencia_id) REFERENCES competencias(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS conocimientos (
    id TEXT PRIMARY KEY,
    competencia_id TEXT NOT NULL,
    resultado_id TEXT,
    tipo TEXT NOT NULL DEFAULT '',
    texto TEXT NOT NULL DEFAULT '',
    orden INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (competencia_id) REFERENCES competencias(id) ON DELETE CASCADE,
    FOREIGN KEY (resultado_id) REFERENCES resultados(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS criterios (
    id TEXT PRIMARY KEY,
    competencia_id TEXT NOT NULL,
    resultado_id TEXT,
    texto TEXT NOT NULL DEFAULT '',
    orden INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (competencia_id) REFERENCES competencias(id) ON DELETE CASCADE,
    FOREIGN KEY (resultado_id) REFERENCES resultados(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS ambientes (
    id TEXT PRIMARY KEY,
    programa_id TEXT NOT NULL,
    categoria TEXT NOT NULL DEFAULT '',
    nombre TEXT NOT NULL DEFAULT '',
    orden INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (programa_id) REFERENCES programas(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS materiales (
    id TEXT PRIMARY KEY,
    programa_id TEXT NOT NULL,
    categoria TEXT NOT NULL DEFAULT '',
    nombre TEXT NOT NULL DEFAULT '',
    cantidad TEXT NOT NULL DEFAULT '',
    orden INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (programa_id) REFERENCES programas(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS proyectos_formativos (
    id TEXT PRIMARY KEY,
    programa_id TEXT NOT NULL,
    codigo_sofia TEXT NOT NULL DEFAULT '',
    nombre TEXT NOT NULL DEFAULT '',
    centro_formacion TEXT NOT NULL DEFAULT '',
    regional TEXT NOT NULL DEFAULT '',
    tiempo_meses REAL NOT NULL DEFAULT 0,
    empresas TEXT NOT NULL DEFAULT '',
    palabras_clave TEXT NOT NULL DEFAULT '',
    total_resultados INTEGER NOT NULL DEFAULT 0,
    planteamiento TEXT NOT NULL DEFAULT '',
    justificacion TEXT NOT NULL DEFAULT '',
    objetivo_general TEXT NOT NULL DEFAULT '',
    objetivos_especificos TEXT NOT NULL DEFAULT '',
    alcance TEXT NOT NULL DEFAULT '',
    innovacion TEXT NOT NULL DEFAULT '',
    valoracion TEXT NOT NULL DEFAULT '',
    fuente TEXT NOT NULL DEFAULT '',
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL,
    FOREIGN KEY (programa_id) REFERENCES programas(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS fases_proyecto (
    id TEXT PRIMARY KEY,
    proyecto_id TEXT NOT NULL,
    nombre TEXT NOT NULL DEFAULT '',
    productos TEXT NOT NULL DEFAULT '',
    orden INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (proyecto_id) REFERENCES proyectos_formativos(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS actividades_proyecto (
    id TEXT PRIMARY KEY,
    fase_id TEXT NOT NULL,
    nombre TEXT NOT NULL DEFAULT '',
    descripcion TEXT NOT NULL DEFAULT '',
    orden INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (fase_id) REFERENCES fases_proyecto(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS actividad_resultados (
    actividad_id TEXT NOT NULL,
    resultado_id TEXT NOT NULL,
    PRIMARY KEY (actividad_id, resultado_id),
    FOREIGN KEY (actividad_id) REFERENCES actividades_proyecto(id) ON DELETE CASCADE,
    FOREIGN KEY (resultado_id) REFERENCES resultados(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_competencias_programa ON competencias(programa_id, orden);
CREATE INDEX IF NOT EXISTS idx_resultados_competencia ON resultados(competencia_id, orden);
CREATE INDEX IF NOT EXISTS idx_conocimientos_competencia ON conocimientos(competencia_id, resultado_id, orden);
CREATE INDEX IF NOT EXISTS idx_criterios_competencia ON criterios(competencia_id, resultado_id, orden);
CREATE INDEX IF NOT EXISTS idx_ambientes_programa ON ambientes(programa_id, orden);
CREATE INDEX IF NOT EXISTS idx_materiales_programa ON materiales(programa_id, orden);
CREATE INDEX IF NOT EXISTS idx_proyectos_programa ON proyectos_formativos(programa_id, nombre);
CREATE INDEX IF NOT EXISTS idx_fases_proyecto ON fases_proyecto(proyecto_id, orden);
CREATE INDEX IF NOT EXISTS idx_actividades_fase ON actividades_proyecto(fase_id, orden);
CREATE INDEX IF NOT EXISTS idx_actividad_resultados ON actividad_resultados(actividad_id, resultado_id);
"""

_INITIALIZED = set()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def database_path():
    return Path(config.CATALOG_DB)


def _connect():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = str(path)
    if key not in _INITIALIZED:
        conn = sqlite3.connect(path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()
        _INITIALIZED.add(key)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def _db():
    conn = _connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def valid_id(value):
    return bool(_ID_RE.fullmatch(str(value or "")))


def _new_id():
    return uuid.uuid4().hex


def _as_float(value):
    try:
        if value is None or value == "":
            return 0.0
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _as_text(value):
    return str(value or "").strip()


def init_db():
    with _db():
        pass


def list_programas(query=""):
    q = f"%{(query or '').strip()}%"
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT p.*, COUNT(DISTINCT c.id) AS competencias_count, COUNT(DISTINCT r.id) AS resultados_count
            FROM programas p
            LEFT JOIN competencias c ON c.programa_id = p.id
            LEFT JOIN resultados r ON r.competencia_id = c.id
            WHERE ? = '%%' OR p.denominacion LIKE ? OR p.codigo LIKE ?
            GROUP BY p.id
            ORDER BY p.actualizado_en DESC
            """,
            (q, q, q),
        ).fetchall()
    return [dict(r) for r in rows]


def get_programa(programa_id):
    if not valid_id(programa_id):
        return None
    with _db() as conn:
        row = conn.execute("SELECT * FROM programas WHERE id = ?", (programa_id,)).fetchone()
    return dict(row) if row else None


def find_programa(codigo="", version=""):
    codigo = _as_text(codigo)
    version = _as_text(version)
    if not codigo:
        return None
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM programas WHERE codigo = ? AND version = ? ORDER BY actualizado_en DESC LIMIT 1",
            (codigo, version),
        ).fetchone()
        if not row and not version:
            row = conn.execute(
                "SELECT * FROM programas WHERE codigo = ? ORDER BY actualizado_en DESC LIMIT 1",
                (codigo,),
            ).fetchone()
    return dict(row) if row else None


def get_programa_detalle(programa_id):
    programa = get_programa(programa_id)
    if not programa:
        return None
    with _db() as conn:
        competencias = [dict(r) for r in conn.execute(
            "SELECT * FROM competencias WHERE programa_id = ? ORDER BY orden, rowid", (programa_id,)).fetchall()]
        comp_ids = [c["id"] for c in competencias]
        if comp_ids:
            marks = ",".join("?" for _ in comp_ids)
            resultados = [dict(r) for r in conn.execute(
                f"SELECT * FROM resultados WHERE competencia_id IN ({marks}) ORDER BY orden, rowid", comp_ids).fetchall()]
            conocimientos = [dict(r) for r in conn.execute(
                f"SELECT * FROM conocimientos WHERE competencia_id IN ({marks}) ORDER BY orden, rowid", comp_ids).fetchall()]
            criterios = [dict(r) for r in conn.execute(
                f"SELECT * FROM criterios WHERE competencia_id IN ({marks}) ORDER BY orden, rowid", comp_ids).fetchall()]
        else:
            resultados = conocimientos = criterios = []
        ambientes = [dict(r) for r in conn.execute(
            "SELECT * FROM ambientes WHERE programa_id = ? ORDER BY orden, rowid", (programa_id,)).fetchall()]
        materiales = [dict(r) for r in conn.execute(
            "SELECT * FROM materiales WHERE programa_id = ? ORDER BY orden, rowid", (programa_id,)).fetchall()]
    # group
    res_by_c, proc_by_c, sab_by_c, crit_by_c = {}, {}, {}, {}
    for r in resultados:
        res_by_c.setdefault(r["competencia_id"], []).append(r)
    for k in conocimientos:
        key = (k["competencia_id"], "proceso" if k["tipo"] == "proceso" else "saber")
        (proc_by_c if key[1]=="proceso" else sab_by_c).setdefault(k["competencia_id"], []).append(k)
    for c in criterios:
        crit_by_c.setdefault(c["competencia_id"], []).append(c)
    for c in competencias:
        c["resultados"] = res_by_c.get(c["id"], [])
        c["conocimientos_proceso"] = proc_by_c.get(c["id"], [])
        c["conocimientos_saber"] = sab_by_c.get(c["id"], [])
        c["criterios"] = crit_by_c.get(c["id"], [])
    programa["competencias"] = competencias
    programa["ambientes"] = ambientes
    programa["materiales"] = materiales
    return programa


def _upsert_programa(conn, data, programa_id=None):
    if isinstance(data, dict) and isinstance(data.get("programa"), dict):
        data = data["programa"]
    data = data or {}
    now = _now()
    fields = (
        _as_text(data.get("denominacion")), _as_text(data.get("codigo")), _as_text(data.get("version")),
        _as_text(data.get("vigencia")), _as_float(data.get("horas_lectiva")), _as_float(data.get("horas_productiva")),
        _as_float(data.get("horas_total")), _as_text(data.get("tipo")), _as_text(data.get("titulo_obtenido")),
        _as_text(data.get("justificacion")), _as_text(data.get("fuente")),
    )
    if programa_id:
        conn.execute(
            """UPDATE programas SET denominacion=?,codigo=?,version=?,vigencia=?,horas_lectiva=?,horas_productiva=?,
               horas_total=?,tipo=?,titulo_obtenido=?,justificacion=?,fuente=?,actualizado_en=? WHERE id=?""",
            (*fields, now, programa_id),
        )
        return programa_id
    programa_id = _new_id()
    conn.execute(
        """INSERT INTO programas(id,denominacion,codigo,version,vigencia,horas_lectiva,horas_productiva,horas_total,
           tipo,titulo_obtenido,justificacion,fuente,creado_en,actualizado_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (programa_id, *fields, now, now),
    )
    return programa_id


def _insert_children(conn, programa_id, data):
    for ci, comp in enumerate(data.get("competencias") or []):
        cid = _new_id()
        conn.execute(
            "INSERT INTO competencias(id,programa_id,codigo_norma,nombre,duracion,orden) VALUES (?,?,?,?,?,?)",
            (cid, programa_id, _as_text(comp.get("codigo_norma")), _as_text(comp.get("nombre")), _as_float(comp.get("duracion")), ci),
        )
        rae_ids = {}
        for ri, rae in enumerate(comp.get("resultados") or []):
            rid = _new_id()
            code = _as_text(rae.get("codigo"))
            conn.execute(
                "INSERT INTO resultados(id,competencia_id,codigo,denominacion,duracion,orden) VALUES (?,?,?,?,?,?)",
                (rid, cid, code, _as_text(rae.get("denominacion")), _as_float(rae.get("duracion")), ri),
            )
            if code:
                rae_ids[code.upper()] = rid
        def _insert_items(items, tipo, table):
            for ii, item in enumerate(items or []):
                if isinstance(item, str):
                    item = {"texto": item}
                rid = None
                code = _as_text(item.get("rae_codigo")).upper()
                if code:
                    rid = rae_ids.get(code)
                conn.execute(
                    f"INSERT INTO {table}(id,competencia_id,resultado_id,{'tipo,' if table=='conocimientos' else ''}texto,orden) VALUES (?,?,?,?,{ '?,?' if table=='conocimientos' else '?'} )" if False else None
                )
        # conocimientos
        for ii, item in enumerate(comp.get("conocimientos_proceso") or []):
            it = {"texto": item} if isinstance(item, str) else item
            rid = rae_ids.get(_as_text(it.get("rae_codigo")).upper()) if _as_text(it.get("rae_codigo")) else None
            conn.execute("INSERT INTO conocimientos(id,competencia_id,resultado_id,tipo,texto,orden) VALUES (?,?,?,?,?,?)",
                         (_new_id(), cid, rid, "proceso", _as_text(it.get("texto")), ii))
        for ii, item in enumerate(comp.get("conocimientos_saber") or []):
            it = {"texto": item} if isinstance(item, str) else item
            rid = rae_ids.get(_as_text(it.get("rae_codigo")).upper()) if _as_text(it.get("rae_codigo")) else None
            conn.execute("INSERT INTO conocimientos(id,competencia_id,resultado_id,tipo,texto,orden) VALUES (?,?,?,?,?,?)",
                         (_new_id(), cid, rid, "saber", _as_text(it.get("texto")), ii))
        for ii, item in enumerate(comp.get("criterios") or []):
            it = {"texto": item} if isinstance(item, str) else item
            rid = rae_ids.get(_as_text(it.get("rae_codigo")).upper()) if _as_text(it.get("rae_codigo")) else None
            conn.execute("INSERT INTO criterios(id,competencia_id,resultado_id,texto,orden) VALUES (?,?,?,?,?)",
                         (_new_id(), cid, rid, _as_text(it.get("texto")), ii))
    for i, amb in enumerate(data.get("ambientes") or []):
        it = {"nombre": amb} if isinstance(amb, str) else amb
        conn.execute("INSERT INTO ambientes(id,programa_id,categoria,nombre,orden) VALUES (?,?,?,?,?)",
                     (_new_id(), programa_id, _as_text(it.get("categoria")), _as_text(it.get("nombre")), i))
    for i, mat in enumerate(data.get("materiales") or []):
        it = {"nombre": mat} if isinstance(mat, str) else mat
        conn.execute("INSERT INTO materiales(id,programa_id,categoria,nombre,cantidad,orden) VALUES (?,?,?,?,?,?)",
                     (_new_id(), programa_id, _as_text(it.get("categoria")), _as_text(it.get("nombre")), _as_text(it.get("cantidad")), i))


def create_programa(data):
    with _db() as conn:
        pid = _upsert_programa(conn, data)
        _insert_children(conn, pid, data)
        return pid


def replace_programa(programa_id, data):
    if not valid_id(programa_id):
        raise ValueError("Identificador de programa inválido.")
    with _db() as conn:
        pid = _upsert_programa(conn, data, programa_id=programa_id)
        conn.execute("DELETE FROM competencias WHERE programa_id = ?", (programa_id,))
        conn.execute("DELETE FROM ambientes WHERE programa_id = ?", (programa_id,))
        conn.execute("DELETE FROM materiales WHERE programa_id = ?", (programa_id,))
        _insert_children(conn, pid, data)
        return pid


def delete_programa(programa_id):
    if not valid_id(programa_id):
        return False
    with _db() as conn:
        cur = conn.execute("DELETE FROM programas WHERE id = ?", (programa_id,))
        return cur.rowcount > 0


def save_programa_basico(programa_id, data):
    if not valid_id(programa_id):
        raise ValueError("Identificador de programa inválido.")
    with _db() as conn:
        _upsert_programa(conn, data, programa_id=programa_id)
    return programa_id


def add_competencia(programa_id, data):
    with _db() as conn:
        row = conn.execute("SELECT COALESCE(MAX(orden),-1)+1 AS n FROM competencias WHERE programa_id=?", (programa_id,)).fetchone()
        cid = _new_id()
        conn.execute("INSERT INTO competencias(id,programa_id,codigo_norma,nombre,duracion,orden) VALUES (?,?,?,?,?,?)",
                     (cid, programa_id, _as_text(data.get("codigo_norma")), _as_text(data.get("nombre")), _as_float(data.get("duracion")), row["n"]))
        return cid


def delete_competencia(comp_id):
    with _db() as conn:
        return conn.execute("DELETE FROM competencias WHERE id=?", (comp_id,)).rowcount > 0


def add_resultado(comp_id, data):
    with _db() as conn:
        row = conn.execute("SELECT COALESCE(MAX(orden),-1)+1 AS n FROM resultados WHERE competencia_id=?", (comp_id,)).fetchone()
        rid = _new_id()
        conn.execute("INSERT INTO resultados(id,competencia_id,codigo,denominacion,duracion,orden) VALUES (?,?,?,?,?,?)",
                     (rid, comp_id, _as_text(data.get("codigo")), _as_text(data.get("denominacion")), _as_float(data.get("duracion")), row["n"]))
        return rid


def delete_resultado(res_id):
    with _db() as conn:
        return conn.execute("DELETE FROM resultados WHERE id=?", (res_id,)).rowcount > 0


def add_conocimiento(comp_id, data):
    with _db() as conn:
        row = conn.execute("SELECT COALESCE(MAX(orden),-1)+1 AS n FROM conocimientos WHERE competencia_id=?", (comp_id,)).fetchone()
        kid = _new_id()
        conn.execute("INSERT INTO conocimientos(id,competencia_id,resultado_id,tipo,texto,orden) VALUES (?,?,?,?,?,?)",
                     (kid, comp_id, data.get("resultado_id") or None, _as_text(data.get("tipo")) or "proceso", _as_text(data.get("texto")), row["n"]))
        return kid


def delete_conocimiento(kid):
    with _db() as conn:
        return conn.execute("DELETE FROM conocimientos WHERE id=?", (kid,)).rowcount > 0


def add_criterio(comp_id, data):
    with _db() as conn:
        row = conn.execute("SELECT COALESCE(MAX(orden),-1)+1 AS n FROM criterios WHERE competencia_id=?", (comp_id,)).fetchone()
        cid = _new_id()
        conn.execute("INSERT INTO criterios(id,competencia_id,resultado_id,texto,orden) VALUES (?,?,?,?,?)",
                     (cid, comp_id, data.get("resultado_id") or None, _as_text(data.get("texto")), row["n"]))
        return cid


def delete_criterio(cid):
    with _db() as conn:
        return conn.execute("DELETE FROM criterios WHERE id=?", (cid,)).rowcount > 0


def add_ambiente(programa_id, data):
    with _db() as conn:
        row = conn.execute("SELECT COALESCE(MAX(orden),-1)+1 AS n FROM ambientes WHERE programa_id=?", (programa_id,)).fetchone()
        aid = _new_id()
        conn.execute("INSERT INTO ambientes(id,programa_id,categoria,nombre,orden) VALUES (?,?,?,?,?)",
                     (aid, programa_id, _as_text(data.get("categoria")), _as_text(data.get("nombre")), row["n"]))
        return aid


def delete_ambiente(aid):
    with _db() as conn:
        return conn.execute("DELETE FROM ambientes WHERE id=?", (aid,)).rowcount > 0


def add_material(programa_id, data):
    with _db() as conn:
        row = conn.execute("SELECT COALESCE(MAX(orden),-1)+1 AS n FROM materiales WHERE programa_id=?", (programa_id,)).fetchone()
        mid = _new_id()
        conn.execute("INSERT INTO materiales(id,programa_id,categoria,nombre,cantidad,orden) VALUES (?,?,?,?,?,?)",
                     (mid, programa_id, _as_text(data.get("categoria")), _as_text(data.get("nombre")), _as_text(data.get("cantidad")), row["n"]))
        return mid


def delete_material(mid):
    with _db() as conn:
        return conn.execute("DELETE FROM materiales WHERE id=?", (mid,)).rowcount > 0


def update_competencia(comp_id, data):
    with _db() as conn:
        cur = conn.execute(
            "UPDATE competencias SET codigo_norma=?, nombre=?, duracion=? WHERE id=?",
            (_as_text(data.get("codigo_norma")), _as_text(data.get("nombre")), _as_float(data.get("duracion")), comp_id),
        )
        return cur.rowcount > 0


def update_resultado(res_id, data):
    with _db() as conn:
        cur = conn.execute(
            "UPDATE resultados SET codigo=?, denominacion=?, duracion=? WHERE id=?",
            (_as_text(data.get("codigo")), _as_text(data.get("denominacion")), _as_float(data.get("duracion")), res_id),
        )
        return cur.rowcount > 0


def update_conocimiento(kid, data):
    with _db() as conn:
        cur = conn.execute(
            "UPDATE conocimientos SET tipo=?, texto=?, resultado_id=? WHERE id=?",
            (_as_text(data.get("tipo")) or "proceso", _as_text(data.get("texto")), data.get("resultado_id") or None, kid),
        )
        return cur.rowcount > 0


def update_criterio(cid, data):
    with _db() as conn:
        cur = conn.execute(
            "UPDATE criterios SET texto=?, resultado_id=? WHERE id=?",
            (_as_text(data.get("texto")), data.get("resultado_id") or None, cid),
        )
        return cur.rowcount > 0


def update_ambiente(aid, data):
    with _db() as conn:
        cur = conn.execute(
            "UPDATE ambientes SET categoria=?, nombre=? WHERE id=?",
            (_as_text(data.get("categoria")), _as_text(data.get("nombre")), aid),
        )
        return cur.rowcount > 0


def update_material(mid, data):
    with _db() as conn:
        cur = conn.execute(
            "UPDATE materiales SET categoria=?, nombre=?, cantidad=? WHERE id=?",
            (_as_text(data.get("categoria")), _as_text(data.get("nombre")), _as_text(data.get("cantidad")), mid),
        )
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Proyectos formativos
# ---------------------------------------------------------------------------

def _proyecto_fields(data):
    return (
        _as_text(data.get("programa_id")), _as_text(data.get("codigo_sofia")), _as_text(data.get("nombre")),
        _as_text(data.get("centro_formacion")), _as_text(data.get("regional")), _as_float(data.get("tiempo_meses")),
        _as_text(data.get("empresas")), _as_text(data.get("palabras_clave")),
        int(_as_float(data.get("total_resultados"))), _as_text(data.get("planteamiento")),
        _as_text(data.get("justificacion")), _as_text(data.get("objetivo_general")),
        _as_text(data.get("objetivos_especificos")), _as_text(data.get("alcance")),
        _as_text(data.get("innovacion")), _as_text(data.get("valoracion")), _as_text(data.get("fuente")),
    )


def list_proyectos(query="", programa_id=""):
    q = f"%{(query or '').strip()}%"
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT p.*, pr.denominacion AS programa_denominacion, pr.codigo AS programa_codigo,
                   COUNT(DISTINCT f.id) AS fases_count,
                   COUNT(DISTINCT a.id) AS actividades_count,
                   COUNT(DISTINCT ar.resultado_id) AS resultados_count
            FROM proyectos_formativos p
            LEFT JOIN programas pr ON pr.id = p.programa_id
            LEFT JOIN fases_proyecto f ON f.proyecto_id = p.id
            LEFT JOIN actividades_proyecto a ON a.fase_id = f.id
            LEFT JOIN actividad_resultados ar ON ar.actividad_id = a.id
            WHERE (? = '%%' OR p.nombre LIKE ? OR p.codigo_sofia LIKE ? OR pr.denominacion LIKE ?)
              AND (? = '' OR p.programa_id = ?)
            GROUP BY p.id
            ORDER BY p.actualizado_en DESC
            """,
            (q, q, q, q, _as_text(programa_id), _as_text(programa_id)),
        ).fetchall()
    return [dict(r) for r in rows]


def get_proyecto(proyecto_id):
    if not valid_id(proyecto_id):
        return None
    with _db() as conn:
        row = conn.execute("SELECT * FROM proyectos_formativos WHERE id = ?", (proyecto_id,)).fetchone()
    return dict(row) if row else None


def get_proyecto_detalle(proyecto_id):
    proyecto = get_proyecto(proyecto_id)
    if not proyecto:
        return None
    with _db() as conn:
        fases = [dict(r) for r in conn.execute(
            "SELECT * FROM fases_proyecto WHERE proyecto_id=? ORDER BY orden, rowid", (proyecto_id,)).fetchall()]
        fase_ids = [f["id"] for f in fases]
        actividades = []
        if fase_ids:
            marks = ",".join("?" for _ in fase_ids)
            actividades = [dict(r) for r in conn.execute(
                f"SELECT * FROM actividades_proyecto WHERE fase_id IN ({marks}) ORDER BY orden, rowid", fase_ids).fetchall()]
        act_ids = [a["id"] for a in actividades]
        links = []
        if act_ids:
            marks = ",".join("?" for _ in act_ids)
            links = [dict(r) for r in conn.execute(
                f"""SELECT ar.actividad_id, r.id, r.codigo, r.denominacion, r.duracion, r.competencia_id,
                           c.nombre AS competencia_nombre, c.codigo_norma
                    FROM actividad_resultados ar
                    JOIN resultados r ON r.id = ar.resultado_id
                    JOIN competencias c ON c.id = r.competencia_id
                    WHERE ar.actividad_id IN ({marks})
                    ORDER BY c.orden, r.orden, r.rowid""", act_ids).fetchall()]
    by_act = {}
    for link in links:
        by_act.setdefault(link.pop("actividad_id"), []).append(link)
    by_fase = {}
    for a in actividades:
        a["resultados"] = by_act.get(a["id"], [])
        by_fase.setdefault(a["fase_id"], []).append(a)
    for f in fases:
        f["actividades"] = by_fase.get(f["id"], [])
    proyecto["fases"] = fases
    return proyecto


def get_proyecto_api(proyecto_id):
    return get_proyecto_detalle(proyecto_id)


def create_proyecto(data):
    with _db() as conn:
        pid = _new_id()
        now = _now()
        conn.execute(
            """INSERT INTO proyectos_formativos(id,programa_id,codigo_sofia,nombre,centro_formacion,regional,
               tiempo_meses,empresas,palabras_clave,total_resultados,planteamiento,justificacion,objetivo_general,
               objetivos_especificos,alcance,innovacion,valoracion,fuente,creado_en,actualizado_en)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pid, *_proyecto_fields(data), now, now),
        )
        return pid


def update_proyecto(proyecto_id, data):
    if not valid_id(proyecto_id):
        raise ValueError("Identificador de proyecto inválido.")
    with _db() as conn:
        conn.execute(
            """UPDATE proyectos_formativos SET programa_id=?,codigo_sofia=?,nombre=?,centro_formacion=?,regional=?,
               tiempo_meses=?,empresas=?,palabras_clave=?,total_resultados=?,planteamiento=?,justificacion=?,
               objetivo_general=?,objetivos_especificos=?,alcance=?,innovacion=?,valoracion=?,fuente=?,
               actualizado_en=? WHERE id=?""",
            (*_proyecto_fields(data), _now(), proyecto_id),
        )
    return proyecto_id


def delete_proyecto(proyecto_id):
    if not valid_id(proyecto_id):
        return False
    with _db() as conn:
        return conn.execute("DELETE FROM proyectos_formativos WHERE id=?", (proyecto_id,)).rowcount > 0


def add_fase(proyecto_id, data):
    with _db() as conn:
        row = conn.execute("SELECT COALESCE(MAX(orden),-1)+1 AS n FROM fases_proyecto WHERE proyecto_id=?", (proyecto_id,)).fetchone()
        fid = _new_id()
        conn.execute("INSERT INTO fases_proyecto(id,proyecto_id,nombre,productos,orden) VALUES (?,?,?,?,?)",
                     (fid, proyecto_id, _as_text(data.get("nombre")), _as_text(data.get("productos")), row["n"]))
        return fid


def update_fase(fase_id, data):
    with _db() as conn:
        return conn.execute("UPDATE fases_proyecto SET nombre=?, productos=? WHERE id=?",
                            (_as_text(data.get("nombre")), _as_text(data.get("productos")), fase_id)).rowcount > 0


def delete_fase(fase_id):
    with _db() as conn:
        return conn.execute("DELETE FROM fases_proyecto WHERE id=?", (fase_id,)).rowcount > 0


def add_actividad(fase_id, data):
    with _db() as conn:
        row = conn.execute("SELECT COALESCE(MAX(orden),-1)+1 AS n FROM actividades_proyecto WHERE fase_id=?", (fase_id,)).fetchone()
        aid = _new_id()
        conn.execute("INSERT INTO actividades_proyecto(id,fase_id,nombre,descripcion,orden) VALUES (?,?,?,?,?)",
                     (aid, fase_id, _as_text(data.get("nombre")), _as_text(data.get("descripcion")), row["n"]))
        return aid


def update_actividad(actividad_id, data):
    with _db() as conn:
        return conn.execute("UPDATE actividades_proyecto SET nombre=?, descripcion=? WHERE id=?",
                            (_as_text(data.get("nombre")), _as_text(data.get("descripcion")), actividad_id)).rowcount > 0


def delete_actividad(actividad_id):
    with _db() as conn:
        return conn.execute("DELETE FROM actividades_proyecto WHERE id=?", (actividad_id,)).rowcount > 0


def set_actividad_resultados(actividad_id, resultado_ids):
    ids = [str(x) for x in (resultado_ids or []) if valid_id(str(x))]
    with _db() as conn:
        conn.execute("DELETE FROM actividad_resultados WHERE actividad_id=?", (actividad_id,))
        for rid in dict.fromkeys(ids):
            conn.execute("INSERT OR IGNORE INTO actividad_resultados(actividad_id,resultado_id) VALUES (?,?)", (actividad_id, rid))
    return actividad_id


def get_actividad(actividad_id):
    with _db() as conn:
        row = conn.execute("SELECT * FROM actividades_proyecto WHERE id=?", (actividad_id,)).fetchone()
    return dict(row) if row else None


def get_actividad_resultados(actividad_id):
    with _db() as conn:
        rows = conn.execute(
            """SELECT r.id, r.codigo, r.denominacion, r.duracion, r.competencia_id,
                      c.nombre AS competencia_nombre, c.codigo_norma
               FROM actividad_resultados ar
               JOIN resultados r ON r.id = ar.resultado_id
               JOIN competencias c ON c.id = r.competencia_id
               WHERE ar.actividad_id=? ORDER BY c.orden, r.orden, r.rowid""",
            (actividad_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_programa_resultados(programa_id):
    with _db() as conn:
        rows = conn.execute(
            """SELECT r.id, r.codigo, r.denominacion, r.duracion, r.competencia_id,
                      c.nombre AS competencia_nombre, c.codigo_norma, c.orden AS competencia_orden
               FROM resultados r JOIN competencias c ON c.id=r.competencia_id
               WHERE c.programa_id=? ORDER BY c.orden, r.orden, r.rowid""",
            (programa_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_programa_api(programa_id):
    d = get_programa_detalle(programa_id)
    if not d:
        return None
    for c in d["competencias"]:
        c["resultados"] = [
            {k: r[k] for k in ("id","codigo","denominacion","duracion","orden","competencia_id")} for r in c.get("resultados", [])
        ]
    return d


def get_competencia(comp_id):
    with _db() as conn:
        row = conn.execute("SELECT * FROM competencias WHERE id=?", (comp_id,)).fetchone()
    return dict(row) if row else None


def get_resultado(res_id):
    with _db() as conn:
        row = conn.execute("SELECT r.*, c.programa_id, c.nombre AS competencia_nombre FROM resultados r JOIN competencias c ON c.id=r.competencia_id WHERE r.id=?", (res_id,)).fetchone()
    return dict(row) if row else None
