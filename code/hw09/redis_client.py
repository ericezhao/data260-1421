# small helper so we can talk to redis (or fakeredis if server is down)
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

from hw09.config import REDIS_DB, REDIS_HOST, REDIS_PORT


def get_redis(decode_responses=True):
    import redis

    # HW9_FAKE_REDIS=1 forces fakeredis (for offline smoke tests)
    if os.getenv("HW9_FAKE_REDIS") == "1":
        import fakeredis

        return fakeredis.FakeRedis(decode_responses=decode_responses)

    client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=decode_responses,
    )
    try:
        client.ping()
        return client
    except Exception as e:
        print(f"[redis] real server unavailable ({type(e).__name__}: {e})")
        print("[redis] falling back to fakeredis for this process")
        import fakeredis

        return fakeredis.FakeRedis(decode_responses=decode_responses)
