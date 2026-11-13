(function () {
  const root = document.getElementById("catalog-prefill");
  if (!root) return;
  const prog = document.getElementById("cat-programa");
  const proj = document.getElementById("cat-proyecto");
  const fase = document.getElementById("cat-fase");
  const act = document.getElementById("cat-actividad");
  const comp = document.getElementById("cat-competencia");
  const raes = document.getElementById("cat-raes");
  const apply = document.getElementById("cat-apply");
  const clear = document.getElementById("cat-clear");
  const status = document.getElementById("cat-status");

  let programas = [];
  let proyectos = [];
  let proyecto = null;
  let currentRaes = [];

  const field = (name) => document.querySelector(`[name="${name}"]`);
  const hidden = (id) => document.getElementById(id);

  function opt(value, label) {
    const o = document.createElement("option");
    o.value = value;
    o.textContent = label;
    return o;
  }
  function setStatus(msg) { if (status) status.textContent = msg || ""; }
  function reset(select, label) {
    select.innerHTML = "";
    select.appendChild(opt("", label));
  }
  async function getJSON(url) {
    const res = await fetch(url, { headers: { "Accept": "application/json" } });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }
  function programById(id) { return programas.find((p) => p.id === id); }

  function programRaes(programa) {
    const out = [];
    (programa && programa.competencias || []).forEach((c) => {
      (c.resultados || []).forEach((r) => out.push({
        ...r,
        competencia_id: c.id,
        competencia_nombre: c.nombre,
        codigo_norma: c.codigo_norma,
      }));
    });
    return out;
  }

  function projectRaes(detail) {
    const out = [];
    (detail && detail.fases || []).forEach((f) => {
      (f.actividades || []).forEach((a) => {
        (a.resultados || []).forEach((r) => out.push({
          ...r,
          competencia_nombre: r.competencia_nombre,
          codigo_norma: r.codigo_norma,
          fase_nombre: f.nombre,
          actividad_nombre: a.nombre,
        }));
      });
    });
    return out;
  }

  function setRaes(list, label) {
    currentRaes = list || [];
    const selectedComp = comp.value;
    raes.innerHTML = "";
    if (!currentRaes.length) {
      raes.appendChild(opt("", label || "Sin RAE disponibles"));
      return;
    }
    currentRaes
      .filter((r) => !selectedComp || r.competencia_id === selectedComp)
      .forEach((r) => {
        const labelText = (r.codigo ? r.codigo + ": " : "") + (r.denominacion || "") + (r.duracion ? ` (${r.duracion} h)` : "");
        raes.appendChild(opt(r.id, labelText));
      });
    if (!raes.options.length) raes.appendChild(opt("", "Sin RAE para esta competencia"));
  }

  function setCompetencias(list) {
    const current = comp.value;
    reset(comp, "Todas las del programa");
    list.forEach((c) => comp.appendChild(opt(c.id, c.nombre || c.codigo_norma || "(competencia)")));
    if (current && list.some((c) => c.id === current)) comp.value = current;
  }

  function uniqueCompetencias(list) {
    const seen = new Set();
    const out = [];
    list.forEach((r) => {
      const id = r.competencia_id || r.id;
      if (id && !seen.has(id)) {
        seen.add(id);
        out.push({ id, nombre: r.competencia_nombre || r.codigo_norma || "(competencia)" });
      }
    });
    return out;
  }

  async function loadProgramas() {
    try {
      const json = await getJSON(root.dataset.programasUrl);
      programas = json.programas || [];
      reset(prog, "Seleccione un programa…");
      programas.forEach((p) => prog.appendChild(opt(p.id, (p.codigo ? p.codigo + " - " : "") + (p.denominacion || "(sin nombre)"))));
      if (!programas.length) setStatus("No hay programas en el catálogo.");
    } catch (e) {
      setStatus("No se pudo cargar el catálogo de programas.");
    }
  }

  async function onPrograma() {
    const p = programById(prog.value);
    proyecto = null;
    reset(proj, "Seleccione un proyecto…");
    reset(fase, "Seleccione un proyecto");
    reset(act, "Seleccione una fase");
    setCompetencias(p ? (p.competencias || []).map((c) => ({ id: c.id, nombre: c.nombre })) : []);
    setRaes(p ? programRaes(p) : [], "Seleccione un programa");
    proyectos = [];
    if (!p) return;
    try {
      const json = await getJSON(root.dataset.proyectosUrl.replace("__PROGRAMA__", encodeURIComponent(p.id)));
      proyectos = json.proyectos || [];
      proyectos.forEach((x) => proj.appendChild(opt(x.id, (x.codigo_sofia ? x.codigo_sofia + " - " : "") + (x.nombre || "(sin nombre)"))));
      if (!proyectos.length) setStatus("El programa no tiene proyectos formativos. Puede seleccionar RAE directamente.");
    } catch (e) {
      setStatus("No se pudieron cargar los proyectos del programa.");
    }
  }

  async function onProyecto() {
    proyecto = null;
    reset(fase, "Seleccione una fase");
    reset(act, "Seleccione una fase");
    if (!proj.value) {
      const p = programById(prog.value);
      setCompetencias(p ? (p.competencias || []).map((c) => ({ id: c.id, nombre: c.nombre })) : []);
      setRaes(p ? programRaes(p) : [], "Seleccione un programa");
      return;
    }
    try {
      const json = await getJSON(root.dataset.proyectoUrl.replace("__PROYECTO__", encodeURIComponent(proj.value)));
      proyecto = json.proyecto || null;
      if (!proyecto) return;
      (proyecto.fases || []).forEach((f) => fase.appendChild(opt(f.id, f.nombre || "(fase)")));
      const list = projectRaes(proyecto);
      setCompetencias(uniqueCompetencias(list));
      setRaes(list, "Seleccione una actividad o RAE");
    } catch (e) {
      setStatus("No se pudo cargar el proyecto formativo.");
    }
  }

  function onFase() {
    reset(act, "Seleccione una actividad");
    if (!proyecto || !fase.value) {
      setRaes(proyecto ? projectRaes(proyecto) : [], "Seleccione una actividad o RAE");
      return;
    }
    const f = (proyecto.fases || []).find((x) => x.id === fase.value);
    (f && f.actividades || []).forEach((a) => act.appendChild(opt(a.id, a.nombre || "(actividad)")));
    const list = [];
    (f && f.actividades || []).forEach((a) => (a.resultados || []).forEach((r) => list.push({ ...r, fase_nombre: f.nombre, actividad_nombre: a.nombre })));
    setCompetencias(uniqueCompetencias(list));
    setRaes(list, "Seleccione una actividad o RAE");
  }

  function onActividad() {
    if (!proyecto) return;
    if (!act.value) {
      onFase();
      return;
    }
    const f = (proyecto.fases || []).find((x) => x.id === fase.value);
    const a = f && (f.actividades || []).find((x) => x.id === act.value);
    const list = (a && a.resultados || []).map((r) => ({ ...r, fase_nombre: f.nombre, actividad_nombre: a.nombre }));
    setCompetencias(uniqueCompetencias(list));
    setRaes(list, "Sin RAE en la actividad");
  }

  function onCompetencia() {
    const list = act.value ? currentRaes : (proyecto ? projectRaes(proyecto) : (programById(prog.value) ? programRaes(programById(prog.value)) : []));
    setRaes(list, "Sin RAE");
  }

  function applyPrefill() {
    const p = programById(prog.value);
    if (!p) { setStatus("Seleccione un programa."); return; }
    const ids = Array.from(raes.selectedOptions).map((o) => o.value).filter(Boolean);
    if (!ids.length) { setStatus("Seleccione al menos un RAE."); return; }
    const picked = ids.map((id) => currentRaes.find((r) => r.id === id)).filter(Boolean);
    if (!picked.length) { setStatus("No se encontraron los RAE seleccionados."); return; }

    const fields = ["programa", "codigo_programa", "proyecto_formativo", "fase", "actividad_proyecto", "competencia", "resultados_aprendizaje"];
    const hasContent = fields.some((name) => { const el = field(name); return el && el.value && el.value.trim(); });
    if (hasContent && !window.confirm("Los campos de identificación ya tienen contenido. ¿Desea sobrescribirlos con los datos del catálogo?")) return;

    const faseSel = (proyecto && (proyecto.fases || []).find((f) => f.id === fase.value)) || null;
    const actSel = (faseSel && (faseSel.actividades || []).find((a) => a.id === act.value)) || null;

    if (field("programa")) field("programa").value = p.denominacion || "";
    if (field("codigo_programa")) field("codigo_programa").value = p.codigo || "";
    if (field("proyecto_formativo") && proyecto) field("proyecto_formativo").value = proyecto.nombre || "";
    if (field("fase") && faseSel) field("fase").value = faseSel.nombre || "";
    if (field("actividad_proyecto") && actSel) field("actividad_proyecto").value = actSel.nombre || "";

    const compNames = [];
    const seen = new Set();
    picked.forEach((r) => {
      const name = r.competencia_nombre || "";
      if (name && !seen.has(name)) { seen.add(name); compNames.push(name); }
    });
    if (field("competencia")) field("competencia").value = compNames.join("\n");

    const lines = picked.map((r) => (r.codigo ? r.codigo + ": " : "") + (r.denominacion || ""));
    if (field("resultados_aprendizaje")) field("resultados_aprendizaje").value = lines.join("\n");
    const total = picked.reduce((sum, r) => sum + (parseFloat(r.duracion) || 0), 0);
    if (field("duracion_horas")) field("duracion_horas").value = total || "";

    hidden("ident-programa-id").value = p.id;
    hidden("ident-proyecto-id").value = proyecto ? proyecto.id : "";
    hidden("ident-fase-id").value = faseSel ? faseSel.id : "";
    hidden("ident-actividad-id").value = actSel ? actSel.id : "";
    hidden("ident-resultados-ids").value = picked.map((r) => r.id).join(",");

    const missing = picked.filter((r) => !r.duracion).length;
    const multiComp = seen.size > 1;
    let msg = `Aplicados ${picked.length} RAE.`;
    if (missing) msg += ` ${missing} RAE sin horas.`;
    if (multiComp) msg += " Se seleccionaron RAE de distintas competencias.";
    setStatus(msg);
  }

  function clearSelection() {
    reset(prog, "Seleccione un programa…");
    reset(proj, "Seleccione un programa");
    reset(fase, "Seleccione un proyecto");
    reset(act, "Seleccione una fase");
    reset(comp, "Todas las del programa");
    reset(raes, "Seleccione un programa");
    proyecto = null;
    currentRaes = [];
    ["ident-programa-id", "ident-proyecto-id", "ident-fase-id", "ident-actividad-id", "ident-resultados-ids"].forEach((id) => { const el = hidden(id); if (el) el.value = ""; });
    setStatus("Selección limpiada.");
  }

  function markManual() {
    ["ident-programa-id", "ident-proyecto-id", "ident-fase-id", "ident-actividad-id", "ident-resultados-ids"].forEach((id) => { const el = hidden(id); if (el) el.value = ""; });
    setStatus("Edición manual: se limpiaron los identificadores del catálogo.");
  }

  prog.addEventListener("change", onPrograma);
  proj.addEventListener("change", onProyecto);
  fase.addEventListener("change", onFase);
  act.addEventListener("change", onActividad);
  comp.addEventListener("change", onCompetencia);
  if (apply) apply.addEventListener("click", applyPrefill);
  if (clear) clear.addEventListener("click", clearSelection);
  ["programa", "proyecto_formativo", "fase", "actividad_proyecto", "competencia", "resultados_aprendizaje"].forEach((name) => {
    const el = field(name);
    if (el) el.addEventListener("input", markManual);
  });
  loadProgramas();
})();
