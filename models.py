from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(191), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('OWNER'), default='OWNER', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ShiftSetting(db.Model):
    __tablename__ = 'shift_settings'
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.Enum('PAGI', 'SIANG'), nullable=False) 
    jam_masuk = db.Column(db.Time, nullable=False)
    jam_pulang = db.Column(db.Time, nullable=False)
    toleransi_menit = db.Column(db.Integer, default=5)
    aktif = db.Column(db.Boolean, default=True)
    dibuat = db.Column(db.DateTime, default=datetime.utcnow)

class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    kode = db.Column(db.String(64), unique=True, nullable=False)
    nama = db.Column(db.String(191), nullable=False)
    email = db.Column(db.String(191))
    shift_id = db.Column(db.Integer, db.ForeignKey('shift_settings.id'))
    aktif = db.Column(db.Boolean, default=True)
    foto_profil = db.Column(db.String(255))
    dibuat = db.Column(db.DateTime, default=datetime.utcnow)

class FaceEncoding(db.Model):
    __tablename__ = 'face_encodings'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), unique=True, nullable=False)
    encoding = db.Column(db.JSON, nullable=False)
    dibuat = db.Column(db.DateTime, default=datetime.utcnow)

class Attendance(db.Model):
    __tablename__ = 'attendances'
    __table_args__ = (
        db.UniqueConstraint('employee_id', 'tanggal', name='unique_daily_attendance'),
        db.Index('idx_attendance_tanggal', 'tanggal'),
    )
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    tanggal = db.Column(db.Date, nullable=False)
    check_in = db.Column(db.Time)
    check_out = db.Column(db.Time)
    status = db.Column(db.Enum('HADIR','TERLAMBAT','IZIN','ALPA','DITOLAK'), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    liveness_ok = db.Column(db.Boolean, default=False)
    similarity = db.Column(db.Float)
    dibuat = db.Column(db.DateTime, default=datetime.utcnow)

class LeaveRequest(db.Model):
    __tablename__ = 'leave_requests'
    __table_args__ = (
        db.Index('idx_leave_tanggal', 'tanggal_mulai', 'tanggal_selesai'),
    )

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)

    # BARU
    jenis = db.Column(
        db.Enum("IZIN", "CUTI"),
        default="IZIN",
        nullable=False
    )

    alasan = db.Column(db.String(255), nullable=False)

    tanggal_mulai = db.Column(db.Date, nullable=False)
    tanggal_selesai = db.Column(db.Date, nullable=False)

    bukti_foto = db.Column(db.String(255))

    status = db.Column(
        db.Enum('PENDING','DISETUJUI','DITOLAK'),
        default='PENDING'
    )

    dibuat = db.Column(db.DateTime, default=datetime.utcnow)