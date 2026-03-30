import os
from flask import Flask, render_template, request, redirect, session
import sqlite3
import pandas as pd
from PIL import Image
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret"
app.config["UPLOAD_FOLDER"] = os.path.join("static", "images")
DB_NAME = "shop.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT,
        role TEXT,
        full_name TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        artikul TEXT,
        name TEXT,
        unit TEXT,
        category TEXT,
        description TEXT,
        manufacturer TEXT,
        supplier TEXT,
        price REAL,
        discount REAL,
        quantity INTEGER,
        image TEXT
    )""")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artikul TEXT,
            order_date DATE,
            delivery_date DATE,
            pup_address INTEGER,
            fullname TEXT,
            code INTEGER,
            status TEXT
        )
        """)

    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()
    cursor = conn.cursor()

    df = pd.read_excel("Tovar.xlsx")

    cursor.execute("SELECT * FROM products")
    count_tovar = cursor.fetchall()

    if not count_tovar:
        df_renamed = df.rename(
            columns={
                "Артикул": "artikul",
                "Наименование товара": "name",
                "Единица измерения": "unit",
                "Категория товара": "category",
                "Описание товара": "description",
                "Производитель": "manufacturer",
                "Поставщик": "supplier",
                "Цена": "price",
                "Действующая скидка": "discount",
                "Кол-во на складе": "quantity",
                "Фото": "image",
            }
        )

        df_renamed.to_sql("products", conn, index=False, if_exists="append")
    else:
        pass

    df = pd.read_excel("user_import.xlsx")

    cursor.execute("SELECT * FROM users")
    count_users = cursor.fetchall()

    if not count_users:
        df_renamed = df.rename(
            columns={
                "Роль сотрудника": "role",
                "ФИО": "full_name",
                "Логин": "username",
                "Пароль": "password",
            }
        )

        df_renamed.to_sql("users", conn, index=False, if_exists="append")
    else:
        pass

    df = pd.read_excel("Заказ_import.xlsx")

    cursor.execute("SELECT * FROM orders")
    count_users = cursor.fetchall()
    if not count_users:
        df_renamed = df.rename(
            columns={
                "Артикул заказа": "artikul",
                "Дата заказа": "order_date",
                "Дата доставки": "delivery_date",
                "Адрес пункта выдачи": "pup_address",
                "ФИО авторизированного клиента": "fullname",
                "Код для получения": "code",
                "Статус заказа": "status",
            }
        )

        df_renamed = df_renamed.drop(columns=["Номер заказа"], errors="ignore")

        df_renamed.to_sql("orders", conn, index=False, if_exists="append")
    else:
        pass

    conn.commit()
    conn.close()


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT username, password, role, full_name FROM users
            WHERE username = ? AND password=?""",
            (username, password),
        )
        user = cursor.fetchone()
        if user:
            session["username"] = user[0]
            session["password"] = user[1]
            session["role"] = user[2]
            session["full_name"] = user[3]
            return redirect("/products")

    return render_template("login.html")


@app.route("/products")
def products():
    stock = request.args.get("stock", "")
    quantity = request.args.get("quantity", "")
    supplier = request.args.get("supplier", "")
    search = request.args.get("search", "")
    query = "SELECT * FROM products WHERE 1=1"

    params = []

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT supplier FROM products")
    suppliers = [row[0] for row in cursor.fetchall()]

    if search:
        query += """
                AND (
                    name LIKE ?
                    OR description LIKE ?
                    OR category LIKE ?
                    OR manufacturer LIKE ?
                    OR supplier LIKE ?
                    OR artikul LIKE ?
                )
                """
        like = f"%{search}%"
        params.extend([like, like, like, like, like, like])

    if stock == "in":
        query += " AND quantity > 0"
    elif stock == "out":
        query += " AND quantity = 0"
    elif stock == "":
        query += ""

    if supplier:
        query += " AND supplier = ?"
        params.append(supplier)

    if quantity == "asc":
        query += " ORDER BY quantity ASC"
    elif quantity == "desc":
        query += " ORDER BY quantity DESC"

    print(query)

    cursor.execute(query, params)
    items = cursor.fetchall()
    print(items)
    conn.close()

    return render_template(
        "product.html",
        search=search,
        suppliers=suppliers,
        items=items,
        name=session.get("full_name"),
        role=session.get("role"),
    )


@app.route("/guest")
def guest():
    session["role"] = "guest"
    session["username"] = "guest"
    return redirect("/products")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/add_product", methods=["GET", "POST"])
def add_product():
    if session.get("role") != "Администратор":
        return "Access Denied"

    if request.method == "POST":
        data = (
            request.form["artikul"],
            request.form["name"],
            request.form["unit"],
            request.form["category"],
            request.form["description"],
            request.form["manufacturer"],
            request.form["supplier"],
            request.form["price"],
            request.form["discount"],
            request.form["quantity"],
        )

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
                    INSERT INTO products
                    (artikul, name, unit, category, description,
                    manufacturer, supplier, price, discount, quantity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            data,
        )

        conn.commit()
        conn.close()

        return redirect("/products")

    return render_template("add_product.html")


@app.route("/edit_product/<int:id>", methods=["GET", "POST"])
def edit_product(id):
    conn = get_db()
    cursor = conn.cursor()

    message = None

    cursor.execute("SELECT * FROM products WHERE id=?", (id,))
    if request.method == "POST":
        image = request.files.get("image")

        if image and image.filename != "":
            filename = secure_filename(image.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

            image.save(filepath)

            img = Image.open(filepath)
            img = img.resize((300, 200))
            img.save(filepath)

        try:
            price = float(request.form["price"])
            discount = float(request.form["discount"])
            quantity = int(request.form["quantity"])
        except ValueError:
            message = "Некорректный формат числового поля."
            return render_template("edit_product.html", p=request.form, message=message)

        if price < 0:
            message = "Цена должна быть положительной!"
        elif discount < 0 or discount > 100:
            message = "Скидка должна быть от 0 до 100!"
        elif quantity < 0:
            message = "Количество не может быть отрицательным!"

        data = (
            request.form["artikul"],
            request.form["name"],
            request.form["unit"],
            request.form["category"],
            request.form["description"],
            request.form["manufacturer"],
            request.form["supplier"],
            request.form["price"],
            request.form["discount"],
            request.form["quantity"],
            image.filename,
            id,
        )

        if message:
            cursor.execute("SELECT * FROM products WHERE id = ?", (id,))
            product = cursor.fetchone()
            return render_template("edit_product.html", p=product, message=message)

        cursor.execute(
            """
                UPDATE products SET
                    artikul=?, name=?, unit=?, category=?, description=?,
                    manufacturer=?, supplier=?, price=?, discount=?, quantity=?, image=?
                WHERE id=?
            """,
            data,
        )
        conn.commit()
        conn.close()
        return redirect("/products")

    cursor.execute("SELECT * FROM products WHERE id = ?", (id,))
    product = cursor.fetchone()
    conn.close()

    return render_template("edit_product.html", p=product)


# @app.route("/delete_product/<int:product_id>", methods=["POST"])
# def delete_product(product_id):
#     conn = get_db()
#     cursor = conn.cursor()
#     cursor.execute("DELETE FROM products WHERE id=?", (product_id,))
#     conn.commit()
#     return redirect("/products")


@app.route("/orders", methods=["POST", "GET"])
def order():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders")
    items = cursor.fetchall()

    conn.close()

    return render_template("orders.html", items=items, role=session.get("role"))


@app.route("/add_order", methods=["GET", "POST"])
def add_order():
    if session.get("role") != "Администратор":
        return "Access Denied"

    if request.method == "POST":
        artikul = request.form["artikul"]
        status = request.form["status"]
        pup_address = request.form["pup_address"]
        order_date = request.form["order_date"]
        delivery_date = request.form["delivery_date"]
        fullname = request.form["fullname"]
        code = request.form["code"]

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO orders (artikul, status, pup_address,
            order_date, delivery_date, fullname, code)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (artikul, status, pup_address, order_date, delivery_date, fullname, code),
        )
        conn.commit()
        conn.close()
        return redirect("/orders")

    return render_template("orders.html", items=None, role=session.get("role"))


@app.route("/edit_order/<int:order_id>", methods=["GET", "POST"])
def edit_order(order_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id=?", (order_id,))
    order = cursor.fetchone()

    if request.method == "POST":
        artikul = request.form["artikul"]
        status = request.form["status"]
        pup_address = request.form["pup_address"]
        order_date = request.form["order_date"]
        delivery_date = request.form["delivery_date"]
        fullname = request.form["fullname"]
        code = request.form["code"]

        cursor.execute(
            """
            UPDATE orders
            SET artikul=?, status=?, pup_address=?,
            order_date=?, delivery_date=?, fullname=?, code=?   
            WHERE id=?
        """,
            (
                artikul,
                status,
                pup_address,
                order_date,
                delivery_date,
                fullname,
                code,
                order_id,
            ),
        )
        conn.commit()
        conn.close()
        return redirect("/orders")

    conn.close()
    return render_template("add_edit_order.html", order=order)


@app.route(
    "/delete_product/<int:product_id>", methods=["POST"], endpoint="delete_product_safe"
)
def delete_product(product_id):
    if session.get("role") != "Администратор":
        return "Access Denied"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT artikul FROM products WHERE id=?", (product_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return "Товар не найден"

    artikul = row["artikul"]

    # Проверяем, есть ли этот артикул в заказах
    cursor.execute("SELECT COUNT(*) FROM orders WHERE artikul=?", (artikul,))
    count = cursor.fetchone()[0]

    if count > 0:
        conn.close()
        return "Невозможно удалить товар: он присутствует в заказах."

    # Если нет заказов, удаляем товар
    cursor.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()
    return redirect("/products")


if __name__ == "__main__":
    init_db()
    seed_db()
    app.run(debug=True)
