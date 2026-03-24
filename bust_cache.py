import sqlite3

with sqlite3.connect('cache.db') as conn:
    deleted = conn.execute("DELETE FROM cache WHERE key LIKE '%top_authors%'")
    conn.commit()
    print(f'Deleted {deleted.rowcount} cache entries')