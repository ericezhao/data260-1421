# Part 1: redis view counter for inspections (primary domain entity)
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

from hw09.config import PREFIX
from hw09.redis_client import get_redis


class InspectionDB:
    """sqlite + redis. only one new method needed for the homework:
    increment_inspection_views(inspection_id)
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or str(ROOT / "reports" / "hw09" / "raw" / "inspections_hw09.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        # assignment demo uses redis_client.incr(...)
        self.redis_client = get_redis()
        self._setup()

    def _setup(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS inspections (
                id TEXT PRIMARY KEY,
                restaurant_name TEXT NOT NULL,
                cuisine TEXT NOT NULL,
                score INTEGER NOT NULL,
                view_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # tiny relation table used later for stale-cache demo (Part 3.5)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS s1421_rel (
                inspection_id TEXT PRIMARY KEY,
                grade_label TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        cur.execute("SELECT COUNT(*) FROM inspections")
        if cur.fetchone()[0] == 0:
            rows = [
                ("ins-001", "Blue Sushi", "Japanese", 95, 0),
                ("ins-002", "Taco Spot", "Mexican", 88, 0),
                ("ins-003", "Green Bowl", "Cafe", 91, 0),
            ]
            cur.executemany(
                "INSERT INTO inspections (id, restaurant_name, cuisine, score, view_count) "
                "VALUES (?, ?, ?, ?, ?)",
                rows,
            )
            cur.execute(
                "INSERT INTO s1421_rel (inspection_id, grade_label, version) VALUES (?, ?, ?)",
                ("ins-001", "A", 1),
            )
            self.conn.commit()
            print("seeded 3 inspections + one s1421_rel row")

    def views_key(self, inspection_id):
        return f"{PREFIX}:views:inspection:{inspection_id}"

    def increment_inspection_views(self, inspection_id):
        # 1) incr in redis (assignment: self.redis_client.incr(key))
        key = self.views_key(inspection_id)
        count = int(self.redis_client.incr(key))

        # 2) every 10 hits, write to sqlite
        self._pending_sync_log = None
        if count % 10 == 0:
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE inspections SET view_count = ? WHERE id = ?",
                (count, inspection_id),
            )
            self.conn.commit()
            # caller prints Access line first, then log_sync_if_needed()
            # so the terminal matches the HW9 expected output order
            self._pending_sync_log = "✓ Synced views to database"

        return count

    def log_sync_if_needed(self):
        msg = getattr(self, "_pending_sync_log", None)
        if msg:
            print(msg)
            self._pending_sync_log = None
            return True
        return False

    def get_db_view_count(self, inspection_id):
        cur = self.conn.cursor()
        cur.execute("SELECT view_count FROM inspections WHERE id = ?", (inspection_id,))
        row = cur.fetchone()
        return int(row["view_count"]) if row else None

    def get_rel(self, inspection_id):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT inspection_id, grade_label, version FROM s1421_rel WHERE inspection_id = ?",
            (inspection_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def update_rel_grade(self, inspection_id, grade_label):
        # bump version so cache can invalidate
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE s1421_rel SET grade_label = ?, version = version + 1 WHERE inspection_id = ?",
            (grade_label, inspection_id),
        )
        self.conn.commit()
        return self.get_rel(inspection_id)

    def close(self):
        self.conn.close()
