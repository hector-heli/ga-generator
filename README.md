# GA Generator — Servidor web

Aplicación Flask multipágina para crear, revisar y generar guías de aprendizaje SENA con la plantilla `templates_ga/GA_GFPI-F-135_plantilla.docx`. Cada sección de la guía tiene su propia página y se guarda por separado; la barra lateral muestra el avance y los pendientes. También puede exportar a PDF si LibreOffice está instalado.

## Requisitos

- Python 3.12+ (probado con 3.13)
- LibreOffice (opcional, solo para exportar a PDF)

## Instalación

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Para desarrollo y pruebas:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Ejecutar

```powershell
.\.venv\Scripts\python.exe app.py
```

Abrir `http://127.0.0.1:5000`.

## Flujo de trabajo

1. **Panel de guías** (`/`): cree una guía desde cero o importe un DOCX/XLSX/PDF.
2. **Identificación**: programa, proyecto formativo, competencia, resultados y duración.
3. **Presentación**: bloques de párrafo, subtítulo o lista.
4. **Momentos**: reflexión inicial, contextualización, apropiación y transferencia. Cada momento admite varias actividades.
5. **Glosario**, **referentes** y **control del documento**.
6. **Resumen y generación**: validación completa, matriz de evidencias y descarga en Word o PDF.

Cada formulario se guarda con POST + redirección (patrón PRG). La barra lateral indica el estado de cada sección: completo, con pendientes o sin diligenciar.

## Actividades múltiples sin SPA

Cada momento se edita en un solo formulario. Los botones envían una acción junto con todos los campos visibles:

```text
action=save
action=add
action=delete:<uid>
action=up:<uid> / down:<uid>
action=suggest:<uid>
```

Así se conservan las ediciones sin guardar al agregar, eliminar, reordenar o autocompletar una actividad. Las actividades y los bloques de presentación tienen un `uid` estable que se guarda en el JSON de la guía.

## Persistencia

- Base de datos SQLite: `data/guides.sqlite3` (excluida de git).
- Cada guía se almacena como un documento JSON normalizado en la tabla `guides`, con `id`, `data_json`, `created_at` y `updated_at`.
- El JSON se mantiene compatible con `services/docx_builder.py`.
- La capa de acceso está aislada en `services/store.py` para migrar a PostgreSQL cuando se incorpore el catálogo curricular.

## Funciones

- Diligenciamiento por secciones con navegación de página completa.
- Importación de DOCX/XLSX/PDF para convertir un documento existente en guía editable.
- Autocompletado desde `data/content_bank/bank.json` (presentación, actividades, glosario y referentes).
- Validación por sección y validación completa en el resumen (horas, evidencias, campos requeridos).
- Matriz de evidencias derivada automáticamente de las actividades.
- Protección CSRF en todos los formularios web.
- Descarga en Word o PDF.

## Interfaz e identidad visual

La interfaz sigue el **Manual de Identidad Visual SENA 2024**:

- Paleta institucional: verde `#39A900`, verde oscuro `#007832`, azul oscuro `#00304D`, violeta `#71277A`, amarillo `#FDC300`, azul claro `#50E5F9` y gris `#F6F6F6`.
- Tipografía **Work Sans** (autoalojada en `static/fonts/`) para títulos, etiquetas y botones; **Calibri** como fuente secundaria para el cuerpo.
- Tema claro/oscuro con detección de `prefers-color-scheme`, alternancia manual y persistencia en `localStorage`.
- Barra lateral con estructura de la guía y estados de avance.
- Logosímbolo SENA en variantes verde y blanca, sin alterar su construcción ni proporciones.

## Inteligencia artificial (opcional)

El autocompletado puede usar un proveedor compatible con la API de OpenAI. Configúrelo desde **Configuración IA** (`/configuracion`) o editando `config.json`:

```json
{
  "llm": {
    "enabled": true,
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "api_key": "su-api-key"
  }
}
```

También puede definir la clave con la variable de entorno `GA_LLM_API_KEY` (tiene prioridad sobre `config.json`). Si la IA está deshabilitada, sin clave o falla, el sistema usa automáticamente las plantillas de `bank.json` y lo informa en la interfaz. `config.json` está excluido de git.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Las pruebas usan una base SQLite temporal por prueba y cubren, entre otros: guardado por secciones, CSRF, agregar/eliminar/reordenar actividades, glosario y generación de un DOCX con varias actividades de apropiación.

## Rutas web

- `GET /` — panel de guías
- `POST /guias/nueva` — crear guía
- `POST /guias/importar` — importar documento como guía
- `GET/POST /guias/<id>/identificacion`
- `GET/POST /guias/<id>/presentacion`
- `GET /guias/<id>/momentos` — vista general de los cuatro momentos
- `GET/POST /guias/<id>/momentos/<momento>`
- `GET/POST /guias/<id>/glosario`
- `GET/POST /guias/<id>/referentes`
- `GET/POST /guias/<id>/control`
- `GET /guias/<id>/resumen` — validación, matriz de evidencias y generación
- `POST /guias/<id>/generar` — generar DOCX/PDF
- `POST /guias/<id>/eliminar` — eliminar guía
- `GET/POST /configuracion` — configuración de IA
- `POST /configuracion/probar` — probar conexión con el proveedor
- `GET /download/<archivo>` — descarga

## API heredada

Se conserva para compatibilidad con clientes anteriores:

- `GET /api/health`
- `GET /api/config` / `POST /api/config` (la API key se enmascara)
- `POST /api/config/test`
- `POST /api/normalize`
- `POST /api/validate`
- `POST /api/suggest`
- `POST /api/import`
- `POST /api/generate`
- `POST /api/draft` / `GET /api/draft/<id>`

## PDF

Requiere LibreOffice instalado (ruta detectada en `config.py`). Sin LibreOffice, la generación devuelve el DOCX igualmente.

## Estructura

```
app.py                  Servidor Flask, rutas web y API heredada
config.py               Rutas, configuración y detección de LibreOffice
services/defaults.py    Modelo de datos, UIDs y normalización de la guía
services/store.py       Persistencia SQLite de guías
services/guide_forms.py Lectura de formularios y acciones repetibles
services/progress.py    Resumen, estados por sección y navegación
services/evidence.py    Derivación de la matriz de evidencias
services/validation.py  Reglas de validación por sección y globales
services/suggestions.py Autocompletado por plantillas
services/llm.py         Cliente de proveedor LLM compatible con OpenAI
services/docx_builder.py Generación del DOCX
services/importers/     Importadores DOCX/XLSX/PDF
templates/              Interfaz multipágina (base, panel, secciones)
static/css/style.css    Tokens SENA, temas y componentes
static/js/theme.js      Alternancia y persistencia del tema
static/img/             Logosímbolo SENA (verde y blanco)
static/fonts/           Work Sans autoalojada
data/content_bank/      Plantillas de contenido
tests/                  Pruebas con pytest
```
