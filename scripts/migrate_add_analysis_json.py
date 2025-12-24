import shutil, sqlite3
from pathlib import Path
import importlib.util, sys

# attempt to get DB_PATH from utils.database
DB_PATH = None
try:
    spec = importlib.util.spec_from_file_location("utils.database", Path(__file__).parents[1] / "utils" / "database.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    DB_PATH = getattr(mod, "DB_PATH", None)
except Exception:
    DB_PATH = None

# fallback candidates
if not DB_PATH:
    candidates = [
        Path(__file__).parents[1] / "data" / "app.db",
        Path(__file__).parents[1] / "app.db",
        Path(__file__).parents[1] / "database.db",
    ]
    DB_PATH = next((str(p) for p in candidates if p.exists()), None)

if not DB_PATH:
    raise SystemExit("DB file not found. Edit this script to set DB_PATH.")

DB_PATH = str(Path(DB_PATH).resolve())
shutil.copy2(DB_PATH, DB_PATH + ".bak")
print("Backup created:", DB_PATH + ".bak")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("PRAGMA foreign_keys=OFF;")
try:
    cur.execute("ALTER TABLE resume_analysis ADD COLUMN analysis_json TEXT;")
    conn.commit()
    print("Column analysis_json added to resume_analysis")
except sqlite3.OperationalError as e:
    print("ALTER failed:", e)
finally:
    cur.execute("PRAGMA foreign_keys=ON;")
    conn.close()