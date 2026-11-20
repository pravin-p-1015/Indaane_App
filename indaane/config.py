from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "store.db"
DEMO_DB = DATA / "demo.db"
BACKUPS = DATA / "backups"
DATA.mkdir(exist_ok=True)
BACKUPS.mkdir(exist_ok=True)
