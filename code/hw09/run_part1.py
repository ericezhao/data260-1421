# Part 1 demo: hit the counter 25 times
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

from hw09.views_cache import InspectionDB


def main():
    print("Eric Zhao SID4=1421")
    print("=== Testing Counter ===\n")
    db = InspectionDB()
    iid = "ins-001"
    # reset redis key so the demo is repeatable
    db.redis_client.delete(db.views_key(iid))
    db.conn.execute("UPDATE inspections SET view_count = 0 WHERE id = ?", (iid,))
    db.conn.commit()

    for i in range(1, 26):
        total = db.increment_inspection_views(iid)
        print(f"Access #{i}: Total = {total}")
        db.log_sync_if_needed()

    print(f"\ndb view_count for {iid} = {db.get_db_view_count(iid)}")
    db.close()


if __name__ == "__main__":
    main()
