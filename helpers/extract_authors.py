import sqlite3, json, os
from dotenv import load_dotenv

load_dotenv()
conn = sqlite3.connect(os.getenv("CACHE_DB_PATH", "cache.db"))
rows = conn.execute("SELECT data FROM cache WHERE key LIKE 'openalex:top_authors:%'").fetchall()
conn.close()

seen, names = set(), []
for row in rows:
    for a in json.loads(row[0]).get("items", []):
        if a.get("id") not in seen:
            seen.add(a["id"])
            names.append(a.get("name", ""))

names.sort()
with open("authors_list.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(names))
print(f"Saved {len(names)} authors to authors_list.txt")