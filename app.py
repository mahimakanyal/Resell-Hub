from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from werkzeug.utils import secure_filename

# ML imports
import pandas as pd
from sklearn.linear_model import LinearRegression

app = Flask(__name__)
app.secret_key = "resellhub_secret_key"
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------------- ML MODEL ----------------
data = pd.read_csv('data.csv')
X = data[['original_price', 'age']]
y = data['depreciation']

model = LinearRegression()
model.fit(X, y)



# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price TEXT,
        description TEXT,
        image TEXT,
        seller TEXT,
        category TEXT,
        contact TEXT,
        status TEXT DEFAULT 'available'
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        buyer TEXT,
        offer_price TEXT,
        status TEXT DEFAULT 'pending'
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        receiver TEXT,
        product_id INTEGER,
        message TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        is_read INTEGER DEFAULT 0
    )
    ''')

    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       user TEXT,
       product_id INTEGER,
       date TEXT
    )
    """)

  
    conn.commit()
    conn.close()

init_db()

# ---------------- UNREAD COUNT ----------------
def get_unread_count(user):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM messages WHERE receiver=? AND is_read=0", (user,))
    count = c.fetchone()[0]

    conn.close()
    return count

# ---------------- HOME ----------------
@app.route('/')
def home():
    if 'user' not in session:
        return render_template("welcome.html")

    count = get_unread_count(session['user'])
    return render_template("home.html", unread=count)

# ---------------- AUTH ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        r = request.form['role']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        try:
            c.execute("INSERT INTO users VALUES(NULL,?,?,?)",(u,p,r))
            conn.commit()
        except:
            return "User already exists!"

        conn.close()
        return redirect('/login')

    return render_template("register.html")

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        r = request.form['role']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=? AND password=? AND role=?",(u,p,r))
        user = c.fetchone()
        conn.close()

        if user:
            session['user'] = u
            session['role'] = r
            return redirect('/')
        else:
            return "Invalid credentials!"

    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ---------------- PRODUCTS ----------------
@app.route('/products')
def products():
    if 'user' not in session:
        return redirect('/login')

    search = request.args.get('search')
    category = request.args.get('category')
    sort = request.args.get('sort')   # 🔥 NEW
    location = request.args.get('location')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search:
        query += " AND name LIKE ?"
        params.append('%' + search + '%')

    if category:
        query += " AND category=?"
        params.append(category)

    if location:
        query += " AND location LIKE ?"
        params.append('%' + location + '%')    

    # 🔽 SORT LOGIC
    if sort == "low":
        query += " ORDER BY price ASC"
    elif sort == "high":
        query += " ORDER BY price DESC"

    c.execute(query, params)

    data = c.fetchall()
    conn.close()

    return render_template("products.html", products=data)

# ---------------- SELL (ML PREDICTION) ----------------

@app.route('/sell', methods=['GET','POST'])
def sell():
    if 'user' not in session or session['role'] != 'seller':
        return redirect('/login')

    predicted = None

    if request.method == 'POST':
        original = float(request.form['original_price'])
        age = float(request.form['age'])

        dep = model.predict([[original, age]])[0]

        # 🔥 FIX
        if dep <= 0:
            dep = 0.2

        dep = min(dep, 0.9)

        predicted = round(original * (1 - dep), 2)

    return render_template("sell.html", predicted=predicted)
# ---------------- SUBMIT PRODUCT ----------------
@app.route('/submit', methods=['POST'])
def submit():
    name = request.form['name']
    price = request.form['price']
    desc = request.form['description']
    category = request.form['category']
    contact = request.form['contact']
    location = request.form['location']

    image = request.files['image']
    filename = secure_filename(image.filename)
    image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("""
    INSERT INTO products (name,price,description,image,seller,category,contact,location,status)
    VALUES (?,?,?,?,?,?,?,?,?)
    """,(name,price,desc,filename,session['user'],category,contact,location,'available'))

    conn.commit()
    conn.close()

    return redirect('/products')

# ---------------- MY PRODUCTS ----------------
@app.route('/my_products')
def my_products():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE seller=?", (session['user'],))
    data = c.fetchall()
    conn.close()

    return render_template("my_products.html", products=data)

# ----------
@app.route('/edit_product/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    if 'user' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        desc = request.form['description']
        category = request.form['category']
        contact = request.form['contact']
        status = request.form['status']
        location = request.form['location']
    

        c.execute("""
        UPDATE products 
        SET name=?, price=?, description=?, category=?, contact=?, status=?, location=?
        WHERE id=?
        """, (name, price, desc, category, contact, status, location, id))

        conn.commit()
        conn.close()

        return redirect('/my_products')

    # GET request (form open karne ke liye)
    c.execute("SELECT * FROM products WHERE id=?", (id,))
    product = c.fetchone()
    conn.close()

    return render_template("edit_product.html", p=product)


# ---------------- your_offers -----------------
@app.route('/your_offers')
def your_offers():
    if 'user' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("""
    SELECT offers.*, products.name 
    FROM offers
    JOIN products ON offers.product_id = products.id
    WHERE offers.buyer=?
    """, (session['user'],))

    data = c.fetchall()
    conn.close()

    return render_template("your_offers.html", offers=data)

# ---------------- MARK SOLD ----------------
@app.route('/mark_sold/<int:id>')
def mark_sold(id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE products SET status='sold' WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect('/my_products')

# ---------------- MAKE OFFER ----------------
@app.route('/offer/<int:id>', methods=['POST'])
def offer(id):
    price = request.form['offer_price']

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("""
    INSERT INTO offers (product_id, buyer, offer_price, status)
    VALUES (?,?,?,?)
    """,(id, session['user'], price, 'pending'))

    conn.commit()
    conn.close()

    return redirect('/products')

# ---------------- SELLER OFFERS ----------------
@app.route('/seller_offers')
def seller_offers():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("""
    SELECT offers.*, products.name 
    FROM offers 
    JOIN products ON offers.product_id = products.id 
    WHERE products.seller=?
    """,(session['user'],))

    data = c.fetchall()
    conn.close()

    return render_template("seller_offers.html", offers=data)

# ---------------- ACCEPT OFFER ----------------
@app.route('/accept_offer/<int:id>')
def accept_offer(id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # 🔹 offer details lo (product_id + buyer + price)
    c.execute("SELECT product_id, buyer, offer_price FROM offers WHERE id=?", (id,))
    data = c.fetchone()

    product_id = data[0]
    buyer = data[1]
    offer_price = data[2]   # 🔥 NEW

    # 🔹 accept this offer
    c.execute("UPDATE offers SET status='accepted' WHERE id=?", (id,))

    # 🔹 reject other offers
    c.execute("UPDATE offers SET status='rejected' WHERE product_id=? AND id!=?", (product_id, id))

    # 🔹 mark product as sold + SAVE FINAL PRICE 🔥
    c.execute("""
    UPDATE products 
    SET status='sold', final_price=? 
    WHERE id=?
    """, (offer_price, product_id))

    # 🔹 order insert
    c.execute("""
    INSERT INTO orders (user, product_id, date)
    VALUES (?, ?, datetime('now'))
    """, (buyer, product_id))

    conn.commit()
    conn.close()

    return redirect('/seller_offers')

# ---------------- RATING ----------------
@app.route('/rate/<int:product_id>', methods=['POST'])
def rate(product_id):
    if 'user' not in session:
        return redirect('/login')

    rating = request.form.get('rating')

    # 🔥 FIX
    if not rating:
        return redirect(f'/product/{product_id}')

    rating = int(rating)

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("INSERT INTO reviews (product_id, user, rating) VALUES (?, ?, ?)",
              (product_id, session['user'], rating))

    conn.commit()
    conn.close()

    return redirect(f'/product/{product_id}')

# ---------------- PURCHASES (RECEIPT) ----------------
@app.route('/purchases')
def purchases():
    if 'user' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("""
SELECT products.*, offers.offer_price, products.seller
FROM products
JOIN offers ON products.id = offers.product_id
WHERE offers.buyer=? AND offers.status='accepted'
""", (session['user'],))

    data = c.fetchall()
    conn.close()

    return render_template("purchases.html", items=data)

# ---------------- PRODUCT DETAILS ----------------
@app.route('/product/<int:id>')
def product_details(id):
    if 'user' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # product fetch
    c.execute("SELECT * FROM products WHERE id=?", (id,))
    product = c.fetchone()

    # avg rating
    c.execute("SELECT AVG(rating) FROM reviews WHERE product_id=?", (id,))
    avg = c.fetchone()[0]

    # check if user purchased
    c.execute("""
    SELECT * FROM orders 
    WHERE product_id=? AND user=?
    """, (id, session['user']))

    purchased = c.fetchone() is not None

    # 🔥 NEW: check if user purchased
    c.execute("""
    SELECT rating FROM reviews 
    WHERE product_id=? AND user=?
    """, (id, session['user']))

    user_rating = c.fetchone()

    conn.close()

    return render_template(
    "product_details.html",
    product=product,
    avg=avg,
    purchased=purchased,
    user_rating=user_rating
    ) # 🔥 pass this
    

# ---------------- CHAT ----------------
@app.route('/chat/<int:pid>/<user>', methods=['GET','POST'])
def chat(pid, user):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("""
    UPDATE messages 
    SET is_read=1 
    WHERE receiver=? AND sender=? AND product_id=?
    """,(session['user'], user, pid))

    if request.method == 'POST':
        msg = request.form['message']

        c.execute("""
        INSERT INTO messages (sender, receiver, product_id, message, is_read)
        VALUES (?,?,?,?,0)
        """,(session['user'], user, pid, msg))

        conn.commit()

    c.execute("""
    SELECT * FROM messages
    WHERE product_id=? AND 
    ((sender=? AND receiver=?) OR (sender=? AND receiver=?))
    ORDER BY timestamp
    """,(pid,session['user'],user,user,session['user']))

    msgs = c.fetchall()
    conn.close()

    return render_template("chat.html", messages=msgs, other=user, pid=pid)

# ---------------- INBOX ----------------
@app.route('/inbox')
def inbox():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("""
    SELECT DISTINCT product_id, sender FROM messages WHERE receiver=?
    """,(session['user'],))

    chats = c.fetchall()
    conn.close()

    return render_template("inbox.html", chats=chats)

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)