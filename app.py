# ===============================
# RAILWAY + GUNICORN SAFE BOOT
# ===============================
import os
os.environ["MEDIAPIPE_DISABLE_GPU"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

# ===============================
# BASIC IMPORT
# ===============================
from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    flash,
    session
)
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, time
import uuid

from config import Config
from models import (
    db,
    User,
    Employee,
    Attendance,
    ShiftSetting,
    FaceEncoding,
    LeaveRequest
)

# ===============================
# APP FACTORY
# ===============================
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY

    app.config["SQLALCHEMY_DATABASE_URI"] = Config.build_database_uri()
    print("DATABASE URI:")
    print(app.config["SQLALCHEMY_DATABASE_URI"])
    db.init_app(app)
    migrate.init_app(app, db)

    # penting!
    Config.init_app(app)
    
    return app

app = create_app()

# ===============================
# LAZY FACE ENGINE
# ===============================
_face_engine = None

def get_face_engine_safe():
    global _face_engine
    if _face_engine is None:
        from face_engine import get_face_engine
        _face_engine = get_face_engine()
    return _face_engine

# ===============================
# HEALTH CHECK
# ===============================
@app.route("/health")
def health():
    return {
        "status": "ok",
        "db": app.config["SQLALCHEMY_DATABASE_URI"].split("://")[0],
        "time": datetime.utcnow().isoformat()
    }

# ===============================
# AUTH
# ===============================
@app.route("/auth/register", methods=["POST"])
def register():
    data = request.json
    if not data or "email" not in data or "password" not in data:
        return {"error": "Invalid payload"}, 400

    if User.query.filter_by(email=data["email"]).first():
        return {"error": "Email already registered"}, 409

    user = User(
        email=data["email"],
        password_hash=generate_password_hash(data["password"]),
        role="OWNER"
    )
    db.session.add(user)
    db.session.commit()
    return {"message": "User created"}, 201

@app.route("/auth/login", methods=["POST"])
def login_api():
    data = request.get_json(silent=True) or request.form  # ✅ FIX

    if not data:
        return {"error": "Invalid payload"}, 400

    user = User.query.filter_by(email=data.get("email")).first()

    if not user or not check_password_hash(user.password_hash, data.get("password")):
        flash("Email atau password salah.", "error")
        return redirect(url_for("login_page"))

    session["user_id"] = user.id
    session["role"] = user.role

    flash("Login berhasil.", "success")
    return redirect(url_for("dashboard_page"))

# ===============================
# EMPLOYEE
# ===============================
@app.route("/employees", methods=["POST"])
def create_employee():
    data = request.json
    emp = Employee(
        kode=str(uuid.uuid4())[:8],
        nama=data["nama"],
        email=data.get("email"),
        shift_id=data.get("shift_id"),
        aktif=True
    )
    db.session.add(emp)
    db.session.commit()
    return jsonify({"id": emp.id})

@app.route("/employees", methods=["GET"])
def list_employees():
    employees = Employee.query.all()
    return jsonify([
        {
            "id": e.id,
            "kode": e.kode,
            "nama": e.nama,
            "email": e.email,
            "aktif": e.aktif
        } for e in employees
    ])

# ===============================
# SHIFT
# ===============================
@app.route("/shifts", methods=["POST"])
def create_shift():
    data = request.json
    shift = ShiftSetting(
        nama=data["nama"],
        jam_masuk=time.fromisoformat(data["jam_masuk"]),
        jam_pulang=time.fromisoformat(data["jam_pulang"]),
        toleransi_menit=data.get("toleransi_menit", 5)
    )
    db.session.add(shift)
    db.session.commit()
    return {"id": shift.id}

# ===============================
# FACE ENCODING
# ===============================
@app.route("/face/register/<int:employee_id>", methods=["POST"])
def register_face(employee_id):
    if "file" not in request.files:
        return {"error": "No image"}, 400

    image_bytes = request.files["file"].read()
    engine = get_face_engine_safe()
    encoding = engine.extract_face_encoding(image_bytes)

    if not encoding:
        return {"error": "Face not detected"}, 422

    FaceEncoding.query.filter_by(employee_id=employee_id).delete()
    db.session.add(FaceEncoding(
        employee_id=employee_id,
        encoding=encoding
    ))
    db.session.commit()

    engine.add_face_encoding(employee_id, encoding)
    return {"message": "Face registered"}

# ===============================
# ATTENDANCE
# ===============================
@app.route("/attendance", methods=["POST"])
def attendance():
    if "file" not in request.files:
        return {"error": "No image"}, 400

    import numpy as np
    import cv2

    image_bytes = request.files["file"].read()
    engine = get_face_engine_safe()

    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    result = engine.process_attendance(img)

    if not result.get("employee_id"):
        return {"error": "Face not recognized"}, 403

    today = date.today()
    now = datetime.utcnow()

    existing = Attendance.query.filter_by(
        employee_id=result["employee_id"],
        tanggal=today
    ).first()

    if existing:
        existing.check_out = now
    else:
        db.session.add(Attendance(
            employee_id=result["employee_id"],
            tanggal=today,
            check_in=now,
            status="HADIR",
            similarity=result.get("similarity", 0),
            liveness_ok=result.get("liveness_ok", False)
        ))

    db.session.commit()
    return result

# ===============================
# LEAVE REQUEST
# ===============================
@app.route("/leave", methods=["POST"])
def leave():
    data = request.json
    req = LeaveRequest(
        employee_id=data["employee_id"],
        alasan=data["alasan"],
        tanggal_mulai=data["tanggal_mulai"],
        tanggal_selesai=data["tanggal_selesai"]
    )
    db.session.add(req)
    db.session.commit()
    return {"id": req.id}

@app.route("/")
def index():
    return render_template("login.html")

@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


@app.route("/karyawan")
def karyawan_page():
    return render_template("karyawan.html")


@app.route("/shift")
def shift_page():
    return render_template("shift.html")


@app.route("/absen")
def absen_page():
    return render_template("absen.html")


@app.route("/laporan")
def laporan_page():
    return render_template("laporan.html")


@app.route("/izin")
def izin_page():
    return render_template("izin.html")


@app.route("/register")
def register_page():
    return render_template("register.html")


@app.route("/register-face")
def register_face_page():
    return render_template("register_face_general.html")

# ===============================
# LOCAL ONLY
# ===============================
if __name__ == "__main__":
    app.run(debug=True)
