from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3, qrcode, datetime, csv, io, os, base64

app = Flask(__name__)
app.secret_key = "secret123"

# Vercel-safe DB path
DB_PATH = "/tmp/attendance.db"

# ---------- DATABASE ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS admin(
        username TEXT,
        password TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS attendance(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll TEXT,
        name TEXT,
        date TEXT,
        time TEXT
    )""")

    c.execute("INSERT OR IGNORE INTO admin VALUES('admin','admin123')")
    conn.commit()
    conn.close()

init_db()

# ---------- ROUTES ----------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM admin WHERE username=? AND password=?", (u, p))
        if c.fetchone():
            session["admin"] = True
            return redirect("/admin")

    return render_template("index.html")

@app.route("/admin")
def admin():
    if "admin" not in session:
        return redirect("/")
    return render_template("admin.html")

@app.route("/generate")
def generate():
    if "admin" not in session:
        return redirect("/")

    expiry = (datetime.datetime.now() + datetime.timedelta(minutes=2)).strftime("%H:%M")
    url = f"{request.host_url}scan?exp={expiry}"

    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_base64 = base64.b64encode(buf.getvalue()).decode()

    return render_template(
        "admin.html",
        qr=True,
        expiry=expiry,
        qr_image=f"data:image/png;base64,{qr_base64}"
    )

@app.route("/scan", methods=["GET", "POST"])
def scan():
    exp = request.args.get("exp")
    now = datetime.datetime.now().strftime("%H:%M")

    if exp and now > exp:
        return "QR Expired ❌"

    if request.method == "POST":
        roll = request.form["roll"]
        name = request.form["name"]
        date = datetime.date.today().isoformat()
        time = datetime.datetime.now().strftime("%H:%M:%S")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("SELECT * FROM attendance WHERE roll=? AND date=?", (roll, date))
        if c.fetchone():
            return "Attendance Already Marked ⚠️"

        c.execute("INSERT INTO attendance VALUES(NULL,?,?,?,?)",
                  (roll, name, date, time))
        conn.commit()
        conn.close()

        return render_template("success.html")

    return render_template("scan.html")

@app.route("/view")
def view():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM attendance")
    data = c.fetchall()
    conn.close()
    return render_template("view.html", data=data)

@app.route("/export")
def export():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM attendance")
    data = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Roll", "Name", "Date", "Time"])
    writer.writerows(data)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="attendance.csv"
    )
