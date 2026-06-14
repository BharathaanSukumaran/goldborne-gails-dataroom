from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
INBOX_DIR = DATA_DIR / "inbox"
PROCESSED_DIR = DATA_DIR / "processed"
NORMALIZED_DIR = DATA_DIR / "normalized"
REPORTS_DIR = PROJECT_ROOT / "reports"
MANIFEST_PATH = DATA_DIR / "source_manifest.json"
SEED_PATH = DATA_DIR / "seed" / "gails_seed.json"
DB_PATH = NORMALIZED_DIR / "dataroom.sqlite"
