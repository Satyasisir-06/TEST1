from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
import datetime
import csv
import io
import base64

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)

app.secret_key = "super-secret-key-123"

# Vercel-safe SQLite path
DB_PATH = "/tmp/attendance.db"


# ---------------- HEALTH CHECK ----------------
@app.route("/health")
def health():
    return "OK"


# ---------------- DATABASE INIT ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            username TEXT,
            password TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll TEXT,
            name TEXT,
            date TEXT,
            time TEXT
        )
    """)

    c.execute(
        "INSERT OR IGNORE INTO admin VALUES (?, ?)",
        ("admin", "admin123")
    )

    conn.commit()
    conn.close()


# Safe init (prevents silent crash)
try:
    init_db()
except Exception as e:
    print("DB INIT ERROR:", e)


# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute(
            "SELECT * FROM admin WHERE username=? AND password=?",
            (u, p)
        )
        if c.fetchone():
            session["admin"] = True
            return redirect("/admin")

    return render_template("index.html")


# ---------------- ADMIN ----------------
@app.route("/admin")
def admin():
    if "admin" not in session:
        return redirect("/")
    return render_template("admin.html")


# ---------------- GENERATE QR ----------------
@app.route("/generate")
def generate():
    if "admin" not in session:
        return redirect("/")

    import qrcode
    import time

    # Current UTC timestamp
    now_utc = int(time.time())

    # Expiry = 2 minutes from now
    expiry_ts = now_utc + 120

    # Convert to IST (UTC + 5:30)
    ist_offset = 5 * 3600 + 30 * 60
    expiry_ist = expiry_ts + ist_offset

    url = f"{request.host_url}scan?exp={expiry_ts}"

    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    qr_base64 = base64.b64encode(buf.getvalue()).decode()

    expiry_readable = datetime.datetime.fromtimestamp(
        expiry_ist
    ).strftime("%H:%M:%S")

    return render_template(
        "admin.html",
        qr=True,
        expiry=expiry_readable,
        qr_image="data:image/png;base64," + qr_base64
    )




# ---------------- SCAN & MARK ----------------
@app.route("/scan", methods=["GET", "POST"])
def scan():
    import time

    exp = request.args.get("exp")
    if exp and time.time() > int(exp):
        return "QR Expired ❌ Please ask admin to generate again."

    if request.method == "POST":
        roll = request.form["roll"]
        name = request.form["name"]
        date = datetime.date.today().isoformat()
        time_now = datetime.datetime.now().strftime("%H:%M:%S")

        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()

        c.execute(
            "SELECT * FROM attendance WHERE roll=? AND date=?",
            (roll, date)
        )
        if c.fetchone():
            return "Attendance Already Marked ⚠️"

        c.execute(
            "INSERT INTO attendance VALUES (NULL, ?, ?, ?, ?)",
            (roll, name, date, time_now)
        )

        conn.commit()
        conn.close()

        return render_template("success.html")

    return render_template("scan.html")



# ---------------- VIEW ----------------
@app.route("/view")
def view():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT * FROM attendance")
    data = c.fetchall()
    conn.close()
    return render_template("view.html", data=data)


# ---------------- EXPORT CSV ----------------
@app.route("/export")
def export():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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



