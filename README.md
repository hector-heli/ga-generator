# GA Generator — Servidor web

Formulario Flask para crear/editar guías de aprendizaje SENA y generar el DOCX con la plantilla `templates_ga/GA_GFPI-F-135_plantilla.docx`. También puede exportar a PDF si LibreOffice está instalado.

## Requisitos

- Python 3.12+ (probado con 3.14)
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

## Funciones

- Diligenciamiento directo por el usuario en el navegador o importación de DOCX/XLSX/PDF.
- Autocompletado sugerido desde `data/content_bank/bank.json` (presentación, actividades, glosario y referentes).
- Validación en vivo (horas, evidencias, campos requeridos) y descarga en Word o PDF.
- Borradores persistentes en `data/drafts/`.

## Interfaz e identidad visual

La interfaz sigue el **Manual de Identidad Visual SENA 2024**:

- Paleta institucional: verde `#39A900`, verde oscuro `#007832`, azul oscuro `#00304D`, violeta `#71277A`, amarillo `#FDC300`, azul claro `#50E5F9` y gris `#F6F6F6`.
- Tipografía **Work Sans** (autoalojada en `static/fonts/`) para títulos, etiquetas y botones; **Calibri** como fuente secundaria para el cuerpo.
- Tema claro/oscuro con detección de `prefers-color-scheme`, alternancia manual y persistencia en `localStorage`.
- Logosímbolo SENA en variantes verde y blanca, sin alterar su construcción ni proporciones.

## Inteligencia artificial (opcional)

El autocompletado puede usar un proveedor compatible con la API de OpenAI. Configúrelo desde la sección **Configuración de IA** del formulario o editando `config.json`:

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

## Script de muestra

Genera `data/sample_rae23.json` y un DOCX a partir de una guía existente. Las rutas son configurables:

```powershell
.\.venv\Scripts\python.exe scripts\make_sample.py --source "ruta\guia.docx" --sample "data\sample.json" --output "output\muestra.docx"
```

## Endpoints

- `GET /` — formulario
- `GET /api/health` — estado del servicio
- `GET /api/config` / `POST /api/config` — leer/guardar configuración (la API key se enmascara)
- `POST /api/config/test` — probar conexión con el proveedor LLM
- `POST /api/normalize` — normalizar una guía
- `POST /api/validate` — validación
- `POST /api/suggest` — autocompletado (`use_llm: true` para usar IA)
- `POST /api/import` — importar documento
- `POST /api/generate` — generar DOCX/PDF
- `GET /download/<archivo>` — descarga
- `POST /api/draft` / `GET /api/draft/<id>` — borradores

## PDF

Requiere LibreOffice instalado (ruta detectada en `config.py`). Sin LibreOffice, la generación devuelve el DOCX igualmente.

## Estructura

```
app.py                 Servidor Flask y endpoints
config.py              Rutas, configuración y detección de LibreOffice
services/defaults.py   Modelo de datos y normalización de la guía
services/evidence.py   Derivación de la matriz de evidencias (fuente única)
services/validation.py Reglas de validación
services/suggestions.py Autocompletado por plantillas
services/llm.py        Cliente de proveedor LLM compatible con OpenAI
services/docx_builder.py Generación del DOCX
services/importers/    Importadores DOCX/XLSX/PDF
templates/             Interfaz web
static/css/style.css   Tokens SENA, temas claro/oscuro y componentes
static/js/theme.js     Alternancia y persistencia del tema
static/img/            Logosímbolo SENA (verde y blanco)
static/fonts/          Work Sans autoalojada
data/content_bank/     Plantillas de contenido
tests/                 Pruebas con pytest
```
