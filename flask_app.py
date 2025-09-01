from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import random
import string
import time
import hashlib
import os

app = Flask(__name__)

# --- PRODUCTION CHANGE ---
# In production, it's better to use an absolute path for the database.
# This gets the directory the script is in and creates the DB there.
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "attendance.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --- PRODUCTION CHANGE ---
# A SECRET_KEY is crucial for security features in Flask.
# In a real deployment, this should be set from an environment variable.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "a-strong-default-secret-key-for-now")

db = SQLAlchemy(app)


# -------------------- MODELS --------------------
class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)


class AttendanceSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    allowed_bssid = db.Column(db.String(50), nullable=False)
    token = db.Column(db.String(20), nullable=True)
    start_time = db.Column(db.Integer, default=int(time.time()))
    token_expiry = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)


class AttendanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(20), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("attendance_session.id"))
    timestamp = db.Column(db.Integer, default=int(time.time()))


# -------------------- HELPERS --------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token(length=8, expiry_seconds=15):
    token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    expiry = int(time.time()) + expiry_seconds
    return token, expiry


def get_active_session(teacher_id):
    return AttendanceSession.query.filter_by(teacher_id=teacher_id, active=True).first()


# -------------------- TEACHER ROUTES --------------------
@app.route("/register_teacher", methods=["POST"])
def register_teacher():
    data = request.json
    name = data.get("name")
    password = data.get("password")

    if not name or not password:
        return jsonify({"status": "error", "message": "Missing name or password"}), 400

    if Teacher.query.filter_by(name=name).first():
        return jsonify({"status": "error", "message": "Teacher already exists"}), 400

    teacher = Teacher(name=name, password_hash=hash_password(password))
    db.session.add(teacher)
    db.session.commit()

    return jsonify({"status": "success", "message": f"Teacher {name} registered"}), 201


@app.route("/start_attendance", methods=["POST"])
def start_attendance():
    data = request.json
    name = data.get("teacher")
    password = data.get("password")
    bssid = data.get("bssid")

    # --- PRODUCTION CHANGE ---
    # Re-enabled full authentication and input validation.
    if not name or not password or not bssid:
        return jsonify({"status": "error", "message": "Missing teacher, password or BSSID"}), 400

    teacher = Teacher.query.filter_by(name=name).first()
    if not teacher or teacher.password_hash != hash_password(password):
        return jsonify({"status": "error", "message": "Invalid teacher credentials"}), 403

    if get_active_session(teacher.id):
        return jsonify({"status": "error", "message": "Session already active for this teacher"}), 400

    token, expiry = generate_token()
    session = AttendanceSession(
        teacher_id=teacher.id,
        allowed_bssid=bssid,
        token=token,
        start_time=int(time.time()),
        token_expiry=expiry,
        active=True
    )
    db.session.add(session)
    db.session.commit()

    return jsonify({"status": "success", "teacher": name, "token": token}), 200


@app.route("/stop_attendance", methods=["POST"])
def stop_attendance():
    data = request.json
    name = data.get("teacher")
    password = data.get("password")

    # --- PRODUCTION CHANGE ---
    # Re-enabled authentication.
    teacher = Teacher.query.filter_by(name=name).first()
    if not teacher or teacher.password_hash != hash_password(password):
        return jsonify({"status": "error", "message": "Invalid teacher credentials"}), 403

    session = get_active_session(teacher.id)
    if not session:
        return jsonify({"status": "error", "message": "No active session found"}), 400

    session.active = False
    session.token = None
    db.session.commit()

    return jsonify({"status": "success", "message": "Attendance session stopped"}), 200


@app.route("/get_token", methods=["POST"])
def get_token():
    data = request.json
    name = data.get("teacher")
    password = data.get("password")

    # --- PRODUCTION CHANGE ---
    # Re-enabled authentication.
    teacher = Teacher.query.filter_by(name=name).first()
    if not teacher or teacher.password_hash != hash_password(password):
        return jsonify({"status": "error", "message": "Invalid teacher credentials"}), 403

    session = get_active_session(teacher.id)
    if not session:
        return jsonify({"status": "error", "message": "No active session found"}), 400

    # If token is expired, generate a new one
    if int(time.time()) > session.token_expiry:
        token, expiry = generate_token()
        session.token = token
        session.token_expiry = expiry
        db.session.commit()

    return jsonify({"status": "success", "token": session.token}), 200


# -------------------- STUDENT ROUTES --------------------
@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    data = request.json
    roll_number = data.get("roll_number")
    bssid = data.get("bssid")
    token = data.get("token")
    teacher_name = data.get("teacher")

    if not roll_number or not bssid or not token or not teacher_name:
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    teacher = Teacher.query.filter_by(name=teacher_name).first()
    if not teacher:
        return jsonify({"status": "error", "message": "Invalid teacher"}), 400

    session = get_active_session(teacher.id)
    if not session:
        return jsonify({"status": "error", "message": "No active session for this teacher"}), 400

    if int(time.time()) > session.token_expiry:
        return jsonify({"status": "error", "message": "Token has expired"}), 400

    if token != session.token:
        return jsonify({"status": "error", "message": "Invalid token"}), 400

    # --- PRODUCTION CHANGE ---
    # Re-enabled the BSSID check, which is a core security feature of your app.
    if bssid != session.allowed_bssid:
        return jsonify({"status": "error", "message": "Invalid BSSID. Connection must be from the classroom Wi-Fi."}), 400

    existing = AttendanceRecord.query.filter_by(session_id=session.id, roll_number=roll_number).first()
    if existing:
        return jsonify({"status": "error", "message": "Attendance already marked for this session"}), 400

    record = AttendanceRecord(roll_number=roll_number, session_id=session.id)
    db.session.add(record)
    db.session.commit()

    return jsonify({"status": "success", "message": f"Attendance marked for {roll_number}"}), 200


@app.route("/attendance_list", methods=["POST"])
def attendance_list():
    data = request.json
    name = data.get("teacher")
    password = data.get("password")

    # --- PRODUCTION CHANGE ---
    # Re-enabled authentication.
    teacher = Teacher.query.filter_by(name=name).first()
    if not teacher or teacher.password_hash != hash_password(password):
        return jsonify({"status": "error", "message": "Invalid teacher credentials"}), 403

    session = get_active_session(teacher.id)
    if not session:
        return jsonify({"status": "error", "message": "No active session found"}), 400

    records = AttendanceRecord.query.filter_by(session_id=session.id).all()
    attendance = [r.roll_number for r in records]
    return jsonify({"status": "success", "teacher": name, "attendance": attendance}), 200


# --- PRODUCTION CHANGE ---
# The if __name__ == "__main__": block is removed because a production
# server (like Gunicorn or Waitress) will import the `app` object
# directly. Using `app.run()` is only for development.

# Create the database tables if they don't exist
with app.app_context():
    db.create_all()

