import json
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates_ga" / "GA_GFPI-F-135_plantilla.docx"
OUTPUT_DIR = BASE_DIR / "output"
DRAFT_DIR = BASE_DIR / "data" / "drafts"
CONTENT_BANK_DIR = BASE_DIR / "data" / "content_bank"
SAMPLE_PATH = BASE_DIR / "data" / "sample_rae23.json"
CONFIG_PATH = BASE_DIR / "config.json"
TEMP_DIR = BASE_DIR / "data" / "tmp"

SOFFICE_CANDIDATES = [
    Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files\LibreOffice\program\soffice.com"),
]

for folder in (OUTPUT_DIR, DRAFT_DIR, TEMP_DIR, CONTENT_BANK_DIR):
    folder.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "llm": {
        "enabled": False,
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key": "",
    },
    "generation": {
        "output_dir": str(OUTPUT_DIR),
        "convert_pdf": True,
        "filename_pattern": "GA_{rae}_{programa}",
    },
}


def find_soffice():
    for candidate in SOFFICE_CANDIDATES:
        if candidate.exists():
            return candidate
    found = shutil.which("soffice")
    if found:
        return Path(found)
    return None


def load_config():
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if CONFIG_PATH.exists():
        try:
            stored = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            for key, value in stored.items():
                if isinstance(value, dict) and key in config:
                    config[key].update(value)
                else:
                    config[key] = value
        except (json.JSONDecodeError, OSError):
            pass
    if not config["generation"].get("output_dir"):
        config["generation"]["output_dir"] = str(OUTPUT_DIR)
    return config


def save_config(config):
    merged = load_config()
    for key, value in config.items():
        if isinstance(value, dict) and key in merged:
            merged[key].update(value)
        else:
            merged[key] = value
    CONFIG_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def public_config(config=None):
    config = config or load_config()
    safe = json.loads(json.dumps(config))
    key = safe.get("llm", {}).get("api_key", "")
    safe["llm"]["api_key"] = "***" if key else ""
    safe["llm"]["has_api_key"] = bool(key)
    safe["environment"] = {
        "template": TEMPLATE_PATH.exists(),
        "soffice": str(find_soffice()) if find_soffice() else None,
    }
    return safe
