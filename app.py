# ===============================
# RAILWAY + GUNICORN SAFE BOOT
# ===============================
import os


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

    # Validate shift_id if provided
    if shift_id:
        shift = ShiftSetting.query.get(int(shift_id))
        if not shift:
            return jsonify({
                "success": False,
                "message": "Shift tidak ditemukan"
            }), 400

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
    """Register face using JSON with base64 images"""
    try:
        import base64
        import numpy as np
        
        # Log request
        print(f"📥 Received request for employee {employee_id}")
        print(f"📦 Content-Type: {request.headers.get('Content-Type')}")
        
        # Check if request has JSON
        if not request.is_json:
            print("❌ Request is not JSON")
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.get_json(silent=True)
        
        if not data:
            print("❌ No data received")
            return jsonify({"error": "No data received"}), 400
        
        images = data.get('images', [])
        print(f"📸 Images count: {len(images)}")
        
        if not images:
            print("❌ No images in request")
            return jsonify({
                "error": "Tidak ada gambar yang dikirim"
            }), 400
        
        if len(images) < 3:
            print(f"❌ Only {len(images)} images, need at least 3")
            return jsonify({
                "error": f"Minimal 3 gambar diperlukan. Dikirim: {len(images)}"
            }), 400
        
        # Get employee
        employee = Employee.query.get(employee_id)
        if not employee:
            print(f"❌ Employee {employee_id} not found")
            return jsonify({"error": "Karyawan tidak ditemukan"}), 404
        
        print(f"✅ Employee found: {employee.nama} (ID: {employee.id})")
        
        # Get face engine
        try:
            from face_engine import get_face_engine
            engine = get_face_engine()
        except Exception as e:
            print(f"❌ Error loading face engine: {e}")
            return jsonify({"error": f"Face engine error: {str(e)}"}), 500
        
        if engine is None:
            print("❌ Face engine not available")
            return jsonify({"error": "Face engine not available"}), 500
        
        valid_encodings = []
        failed_images = []
        
        for idx, img_data in enumerate(images):
            try:
                # Check if it's a data URL
                if img_data.startswith('data:image'):
                    img_data = img_data.split(',')[1]
                
                # Check if it's valid base64
                try:
                    img_bytes = base64.b64decode(img_data)
                    print(f"📸 Image {idx+1}: Decoded {len(img_bytes)} bytes")
                except Exception as e:
                    print(f"❌ Image {idx+1}: Invalid base64 - {e}")
                    failed_images.append(idx + 1)
                    continue
                
                # Try to extract encoding
                encoding = engine.extract_face_encoding(img_bytes)
                
                if encoding is not None and len(encoding) > 0:
                    valid_encodings.append(encoding)
                    print(f"✅ Image {idx+1}: Face encoded successfully (dimensions: {len(encoding)})")
                else:
                    print(f"⚠️ Image {idx+1}: No face detected")
                    failed_images.append(idx + 1)
                    
            except Exception as e:
                print(f"❌ Error processing image {idx+1}: {e}")
                failed_images.append(idx + 1)
                continue
        
        print(f"📊 Summary: {len(valid_encodings)} valid faces, {len(failed_images)} failed")
        
        if len(valid_encodings) < 3:
            return jsonify({
                "error": f"Hanya {len(valid_encodings)} wajah valid dari {len(images)} gambar. Minimal 3 diperlukan.",
                "details": {
                    "valid": len(valid_encodings),
                    "total": len(images),
                    "failed": failed_images
                }
            }), 400
        
        # Use average encoding
        try:
            avg_encoding = np.mean(valid_encodings, axis=0).tolist()
            print(f"✅ Created average encoding from {len(valid_encodings)} faces")
        except Exception as e:
            print(f"❌ Error creating average encoding: {e}")
            return jsonify({"error": f"Error creating average encoding: {str(e)}"}), 500
        
        # Save to database
        try:
            FaceEncoding.query.filter_by(employee_id=employee_id).delete()
            
            face_encoding = FaceEncoding(
                employee_id=employee_id,
                encoding=avg_encoding
            )
            db.session.add(face_encoding)
            db.session.commit()
            print(f"💾 Saved face encoding to database for employee {employee_id}")
        except Exception as e:
            print(f"❌ Error saving to database: {e}")
            db.session.rollback()
            return jsonify({"error": f"Database error: {str(e)}"}), 500
        
        # Add to engine cache
        try:
            engine.add_face_encoding(employee_id, avg_encoding)
            print(f"💾 Added face encoding to cache for employee {employee_id}")
        except Exception as e:
            print(f"⚠️ Error adding to cache: {e}")
        
        return jsonify({
            "message": f"Wajah berhasil diregistrasi dengan {len(valid_encodings)} gambar",
            "employee_id": employee_id,
            "images_processed": len(valid_encodings),
            "total_images": len(images),
            "failed_images": failed_images
        }), 200
        
    except Exception as e:
        print(f"❌ Error in register_face_json: {e}")
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

@app.route("/register")
def register_page():
    """Halaman pendaftaran karyawan baru"""
    return render_template("register.html")

# ===============================
# DASHBOARD API
# ===============================
@app.route("/api/dashboard-stats", methods=["GET"])
def api_dashboard_stats():
    """Get dashboard statistics"""
    try:
        # Total employees
        total_employees = Employee.query.count()
        
        # Active employees
        active_employees = Employee.query.filter_by(aktif=True).count()
        
        # Face registered
        face_registered = FaceEncoding.query.count()
        
        # Today's attendance
        today = date.today()
        today_attendance = Attendance.query.filter_by(tanggal=today).count()
        
        # Today's check-in count
        today_checkin = Attendance.query.filter(
            Attendance.tanggal == today,
            Attendance.check_in.isnot(None)
        ).count()
        
        # Today's check-out count
        today_checkout = Attendance.query.filter(
            Attendance.tanggal == today,
            Attendance.check_out.isnot(None)
        ).count()
        
        # This month attendance
        first_day = date(today.year, today.month, 1)
        month_attendance = Attendance.query.filter(
            Attendance.tanggal >= first_day,
            Attendance.tanggal <= today
        ).count()
        
        return jsonify({
            'success': True,
            'data': {
                'total_employees': total_employees,
                'active_employees': active_employees,
                'face_registered': face_registered,
                'face_registration_rate': round((face_registered / total_employees * 100) if total_employees > 0 else 0, 1),
                'today_attendance': today_attendance,
                'today_checkin': today_checkin,
                'today_checkout': today_checkout,
                'month_attendance': month_attendance,
                'registration_trend': [
                    {'label': 'Terdaftar', 'value': face_registered},
                    {'label': 'Belum', 'value': total_employees - face_registered}
                ]
            }
        })
    except Exception as e:
        print(f"Error in dashboard_stats: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route("/api/attendance-today", methods=["GET"])
def api_attendance_today():
    """Get today's attendance list"""
    try:
        today = date.today()
        
        # Get all employees with their attendance today
        employees = Employee.query.filter_by(aktif=True).all()
        
        result = []
        for emp in employees:
            # Check if employee has attendance today
            attendance = Attendance.query.filter_by(
                employee_id=emp.id,
                tanggal=today
            ).first()
            
            # Check if employee has face registered
            has_face = FaceEncoding.query.filter_by(employee_id=emp.id).first() is not None
            
            status = 'BELUM ABSEN'
            check_in = None
            check_out = None
            
            if attendance:
                if attendance.check_in:
                    check_in = attendance.check_in.strftime('%H:%M') if attendance.check_in else None
                    status = 'HADIR'
                if attendance.check_out:
                    check_out = attendance.check_out.strftime('%H:%M') if attendance.check_out else None
                    status = 'PULANG'
            
            # Safe shift name access
            shift_name = None
            if emp.shift_id:
                shift = ShiftSetting.query.get(emp.shift_id)
                if shift:
                    shift_name = shift.nama
            
            result.append({
                'id': emp.id,
                'nama': emp.nama,
                'kode': emp.kode,
                'status': status,
                'check_in': check_in,
                'check_out': check_out,
                'has_face': has_face,
                'shift': shift_name
            })
        
        # Sort: HADIR first, then PULANG, then BELUM ABSEN
        status_order = {'HADIR': 0, 'PULANG': 1, 'BELUM ABSEN': 2}
        result.sort(key=lambda x: status_order.get(x['status'], 3))
        
        return jsonify({
            'success': True,
            'data': result,
            'summary': {
                'total': len(result),
                'hadir': sum(1 for r in result if r['status'] == 'HADIR'),
                'pulang': sum(1 for r in result if r['status'] == 'PULANG'),
                'belum': sum(1 for r in result if r['status'] == 'BELUM ABSEN')
            }
        })
    except Exception as e:
        print(f"Error in attendance_today: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route("/api/attendance-recent", methods=["GET"])
def api_attendance_recent():
    """Get recent attendance records"""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        recent = Attendance.query.order_by(
            Attendance.dibuat.desc()
        ).limit(limit).all()
        
        result = []
        for att in recent:
            employee = Employee.query.get(att.employee_id)
            result.append({
                'id': att.id,
                'employee_name': employee.nama if employee else 'Unknown',
                'employee_kode': employee.kode if employee else 'Unknown',
                'tanggal': att.tanggal.strftime('%Y-%m-%d'),
                'check_in': att.check_in.strftime('%H:%M') if att.check_in else None,
                'check_out': att.check_out.strftime('%H:%M') if att.check_out else None,
                'status': att.status,
                'similarity': att.similarity
            })
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        print(f"Error in attendance_recent: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route("/api/dashboard/late-today", methods=["GET"])
def api_late_today():
    """Get late employees today"""
    try:
        today = date.today()
        
        # Get all attendance today
        attendances = Attendance.query.filter_by(tanggal=today).all()
        
        late_employees = []
        for att in attendances:
            if att.status == 'TERLAMBAT':
                employee = Employee.query.get(att.employee_id)
                if employee:
                    late_employees.append({
                        'id': employee.id,
                        'nama': employee.nama,
                        'kode': employee.kode,
                        'check_in': att.check_in.strftime('%H:%M') if att.check_in else None,
                        'status': att.status
                    })
        
        return jsonify({
            'success': True,
            'data': late_employees,
            'total': len(late_employees)
        })
    except Exception as e:
        print(f"Error in late_today: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
# ===============================
# LOCAL ONLY
# ===============================
if __name__ == "__main__":
    app.run(debug=True)

# ===============================
# SEED DATA (Auto-run jika kosong)
# ===============================
def seed_employees():
    """Seed initial employee and shift data if table is empty"""
    
    # Seed shifts first
    if ShiftSetting.query.count() == 0:
        print("📦 Seeding shift data...")
        shifts = [
            ShiftSetting(
                nama="PAGI",
                jam_masuk=time(8, 0, 0),
                jam_pulang=time(16, 0, 0),
                toleransi_menit=15,
                aktif=True
            ),
            ShiftSetting(
                nama="SIANG",
                jam_masuk=time(13, 0, 0),
                jam_pulang=time(21, 0, 0),
                toleransi_menit=15,
                aktif=True
            )
        ]
        for shift in shifts:
            db.session.add(shift)
        db.session.commit()
        print(f"✅ {len(shifts)} shifts seeded!")
    
    # Then seed employees
    if Employee.query.count() == 0:
        print("📦 Seeding initial employee data...")
        
        # Get shift IDs
        shift_pagi = ShiftSetting.query.filter_by(nama="PAGI").first()
        shift_siang = ShiftSetting.query.filter_by(nama="SIANG").first()
        
        employees = [
            Employee(kode="EMP001", nama="Budi Santoso", email="budi.santoso@company.com", shift_id=shift_pagi.id if shift_pagi else None, aktif=True),
            Employee(kode="EMP002", nama="Siti Rahayu", email="siti.rahayu@company.com", shift_id=shift_pagi.id if shift_pagi else None, aktif=True),
            Employee(kode="EMP003", nama="Ahmad Fauzi", email="ahmad.fauzi@company.com", shift_id=shift_siang.id if shift_siang else None, aktif=True),
            Employee(kode="EMP004", nama="Dewi Anggraini", email="dewi.anggraini@company.com", shift_id=shift_pagi.id if shift_pagi else None, aktif=True),
            Employee(kode="EMP005", nama="Rudi Hermawan", email="rudi.hermawan@company.com", shift_id=shift_siang.id if shift_siang else None, aktif=True),
            Employee(kode="EMP006", nama="Maya Sari", email="maya.sari@company.com", shift_id=shift_pagi.id if shift_pagi else None, aktif=True),
            Employee(kode="EMP007", nama="Andi Wijaya", email="andi.wijaya@company.com", shift_id=shift_siang.id if shift_siang else None, aktif=True),
            Employee(kode="EMP008", nama="Nina Kurniawati", email="nina.kurniawati@company.com", shift_id=shift_pagi.id if shift_pagi else None, aktif=True)
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