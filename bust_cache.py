import sqlite3, os
from dotenv import load_dotenv

load_dotenv()
db = os.getenv("CACHE_DB_PATH", "cache.db")
conn = sqlite3.connect(db)
count = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
conn.execute("DELETE FROM cache")
conn.commit()
conn.close()
print(f"Cleared {count} entries from {db}")