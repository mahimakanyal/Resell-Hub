import sqlite3

conn = sqlite3.connect('database.db')
c = conn.cursor()

try:
    c.execute("ALTER TABLE products ADD COLUMN final_price INTEGER")
    print("✅ final_price column added")
except:
    print("⚠️ Column already exists")

conn.commit()
conn.close()