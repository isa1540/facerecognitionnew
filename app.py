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
from sqlalchemy import func
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
@app.route("/api/karyawan", methods=["GET"])
def api_karyawan():

    employees = Employee.query.all()

    hasil = []

    for e in employees:

        face = FaceEncoding.query.filter_by(employee_id=e.id).first()

        hasil.append({
            "id": e.id,
            "kode": e.kode,
            "nama": e.nama,
            "email": e.email,
            "shift_id": e.shift_id,
            "aktif": e.aktif,
            "dibuat": e.dibuat.isoformat() if e.dibuat else None,
            "face_registered": face is not None
        })

    return jsonify({
        "success": True,
        "data": hasil
    })

@app.route("/api/karyawan", methods=["POST"])
def api_create_employee():

    nama = request.form.get("nama")
    email = request.form.get("email")
    shift_id = request.form.get("shift_id")

    if not nama:
        return jsonify({
            "success": False,
            "message": "Nama wajib diisi"
        }), 400

    kode = str(uuid.uuid4())[:8].upper()

    employee = Employee(
        kode=kode,
        nama=nama,
        email=email if email else None,
        shift_id=int(shift_id) if shift_id else None,
        aktif=True
    )

    db.session.add(employee)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Karyawan berhasil ditambahkan",
        "kode": kode,
        "id": employee.id
    })

@app.route("/api/karyawan/<int:id>", methods=["PUT"])
def api_update_employee(id):

    emp = Employee.query.get_or_404(id)

    data = request.json

    emp.nama = data.get("nama")
    emp.email = data.get("email")
    emp.shift_id = data.get("shift_id")
    emp.aktif = data.get("aktif", True)

    db.session.commit()

    return jsonify({
        "success": True
    })

@app.route("/api/karyawan/<int:id>", methods=["DELETE"])
def api_delete_employee(id):

    emp = Employee.query.get_or_404(id)

    emp.aktif = False

    db.session.commit()

    return jsonify({
        "success": True
    })

@app.route("/api/karyawan-with-face-status")
def api_face_status():

    employees = Employee.query.all()

    data = []

    for e in employees:

        registered = FaceEncoding.query.filter_by(
            employee_id=e.id
        ).first() is not None

        data.append({
            "id": e.id,
            "kode": e.kode,
            "nama": e.nama,
            "email": e.email,
            "shift_id": e.shift_id,
            "aktif": e.aktif,
            "dibuat": e.dibuat.isoformat() if e.dibuat else None,
            "face_registered": registered
        })

    return jsonify({
        "success": True,
        "data": data
    })

@app.route("/api/face-cache-stats")
def api_face_cache():

    total_employee = Employee.query.count()

    total_face = FaceEncoding.query.count()

    rate = 0

    if total_employee > 0:
        rate = round(total_face / total_employee * 100)

    return jsonify({
        "success": True,
        "stats": {
            "total_cached_faces": total_face,
            "employees_with_face": total_face,
            "registration_rate": rate
        }
    })


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
# FACE ENCODING - JSON SUPPORT
# ===============================
@app.route("/face/register-json/<int:employee_id>", methods=["POST"])
def register_face_json(employee_id):
    """Register face using JSON with base64 images (for webcam capture)"""
    try:
        data = request.json
        images = data.get('images', [])
        
        if not images or len(images) < 3:
            return jsonify({
                "error": f"Minimal 3 gambar diperlukan. Dikirim: {len(images)}"
            }), 400
        
        # Get employee
        employee = Employee.query.get(employee_id)
        if not employee:
            return jsonify({"error": "Karyawan tidak ditemukan"}), 404
        
        # Process images for face detection
        import base64
        import cv2
        import numpy as np
        
        valid_images = []
        for img_data in images:
            try:
                if img_data.startswith('data:image'):
                    img_data = img_data.split(',')[1]
                
                img_bytes = base64.b64decode(img_data)
                nparr = np.frombuffer(img_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if img is not None:
                    valid_images.append(img)
            except Exception as e:
                print(f"Error processing image: {e}")
                continue
        
        if len(valid_images) < 3:
            return jsonify({
                "error": f"Hanya {len(valid_images)} gambar valid. Minimal 3 gambar diperlukan."
            }), 400
        
        # Use face engine for encoding
        from face_engine import get_face_engine
        engine = get_face_engine()
        
        # Try to extract face encoding from each image
        best_encoding = None
        for img in valid_images:
            success, img_encoded = cv2.imencode('.jpg', img)
            if not success:
                continue
            
            encoding = engine.extract_face_encoding(img_encoded.tobytes())
            if encoding is not None:
                best_encoding = encoding
                break
        
        if best_encoding is None:
            return jsonify({"error": "Tidak dapat mendeteksi wajah pada gambar"}), 422
        
        # Save to database
        FaceEncoding.query.filter_by(employee_id=employee_id).delete()
        
        face_encoding = FaceEncoding(
            employee_id=employee_id,
            encoding=best_encoding
        )
        db.session.add(face_encoding)
        db.session.commit()
        
        # Add to engine cache
        engine.add_face_encoding(employee_id, best_encoding)
        
        return jsonify({
            "message": "Wajah berhasil diregistrasi",
            "employee_id": employee_id,
            "images_processed": len(valid_images)
        }), 200
        
    except Exception as e:
        print(f"Error in register_face_json: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ===============================
# REGISTRATIONS HISTORY (SIMPLE)
# ===============================
@app.route("/api/registrations", methods=["GET"])
def get_registrations_api():
    """Get recent face registrations history"""
    try:
        # Get employees that have face encoding
        employees_with_face = db.session.query(Employee).join(
            FaceEncoding, Employee.id == FaceEncoding.employee_id
        ).order_by(
            FaceEncoding.dibuat.desc()
        ).limit(10).all()
        
        result = []
        for employee in employees_with_face:
            face = FaceEncoding.query.filter_by(employee_id=employee.id).first()
            if face:
                result.append({
                    'employee_id': employee.id,
                    'employee_name': employee.nama,
                    'timestamp': face.dibuat.isoformat(),
                    'images_count': 3
                })
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        print(f"Error in get_registrations_api: {e}")
        return jsonify({
            'success': False,
            'data': []
        }), 500

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

# ===============================
# LAPORAN API
# ===============================
@app.route("/api/laporan")
def api_laporan():
    return jsonify({
        "success": True,
        "message": "Export belum dibuat"
    })
    
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

@app.route("/register-face")
def register_face_page():
    """Face registration page"""
    return render_template("register_face.html")


# ===============================
# LOCAL ONLY
# ===============================
if __name__ == "__main__":
    app.run(debug=True)

# ===============================
# SEED DATA (Auto-run jika kosong)
# ===============================
def seed_employees():
    """Seed initial employee data if table is empty"""
    if Employee.query.count() == 0:
        print("📦 Seeding initial employee data...")
        
        employees = [
            Employee(
                kode="EMP001",
                nama="Budi Santoso",
                email="budi.santoso@company.com",
                shift_id=None,
                aktif=True
            ),
            Employee(
                kode="EMP002",
                nama="Siti Rahayu",
                email="siti.rahayu@company.com",
                shift_id=None,
                aktif=True
            ),
            Employee(
                kode="EMP003",
                nama="Ahmad Fauzi",
                email="ahmad.fauzi@company.com",
                shift_id=None,
                aktif=True
            ),
            Employee(
                kode="EMP004",
                nama="Dewi Anggraini",
                email="dewi.anggraini@company.com",
                shift_id=None,
                aktif=True
            ),
            Employee(
                kode="EMP005",
                nama="Rudi Hermawan",
                email="rudi.hermawan@company.com",
                shift_id=None,
                aktif=True
            ),
            Employee(
                kode="EMP006",
                nama="Maya Sari",
                email="maya.sari@company.com",
                shift_id=None,
                aktif=True
            ),
            Employee(
                kode="EMP007",
                nama="Andi Wijaya",
                email="andi.wijaya@company.com",
                shift_id=None,
                aktif=True
            ),
            Employee(
                kode="EMP008",
                nama="Nina Kurniawati",
                email="nina.kurniawati@company.com",
                shift_id=None,
                aktif=True
            )
        ]
        
        for emp in employees:
            db.session.add(emp)
        
        db.session.commit()
        print(f"✅ {len(employees)} employees seeded successfully!")
    else:
        print(f"✅ Employees already exist: {Employee.query.count()} records")

# Panggil fungsi setelah db.init_app
with app.app_context():
    db.create_all()
    seed_employees()  # <-- Tambahkan ini