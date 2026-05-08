import sqlite3

conn = sqlite3.connect('database.db')
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    user TEXT,
    rating INTEGER
)
""")

conn.commit()
conn.close()

print("Reviews table created ✅")