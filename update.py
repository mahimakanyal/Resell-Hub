import sqlite3

conn = sqlite3.connect('database.db')
c = conn.cursor()

# accepted offers se final price set karo
c.execute("SELECT product_id, offer_price FROM offers WHERE status='accepted'")
offers = c.fetchall()

for product_id, price in offers:
    c.execute("UPDATE products SET final_price=? WHERE id=?", (price, product_id))

# jinke paas offer nahi hai → original price hi final bana do
c.execute("UPDATE products SET final_price=price WHERE final_price IS NULL")

conn.commit()
conn.close()

print("DONE ✅")