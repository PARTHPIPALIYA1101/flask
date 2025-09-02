from flask import Flask, request, jsonify
import random
import string
import time
from supabase import create_client

app = Flask(__name__)

# 🔹 Supabase direct credentials (⚠️ keep safe in production)
SUPABASE_URL = "https://lqdxvspqlsbosgflgivm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxxZHh2c3BxbHNib3NnZmxnaXZtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY3OTI2MDQsImV4cCI6MjA3MjM2ODYwNH0.rGHmLUgs4xC3jL8FExT1yNWw5dzYf2c5ALhveFo1qsk"   # replace with your key
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Global session variables
ATTENDANCE_SESSION = {
    "active": False,
    "token": None,
    "start_time": 0,
    "allowed_bssid": None,
    "token_expiry": 0,
    "teacher": None
}
SESSION_ATTENDANCE = []


# Generate a token with 15-second expiry
def generate_token(length=8, expiry_seconds=15):
    token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    ATTENDANCE_SESSION["token_expiry"] = int(time.time()) + expiry_seconds
    return token


@app.route("/start_attendance", methods=["POST"])
def start_attendance():
    data = request.json
    teacher = data.get("teacher")
    bssid = data.get("bssid")

    if not teacher or not bssid:
        return jsonify({"status": "error", "message": "Missing teacher or BSSID"}), 400
    if ATTENDANCE_SESSION["active"]:
        return jsonify({"status": "error", "message": "Attendance session already active"}), 400

    # reset
    SESSION_ATTENDANCE.clear()
    ATTENDANCE_SESSION.update({
        "active": True,
        "allowed_bssid": bssid,
        "start_time": int(time.time()),
        "teacher": teacher,
        "token": generate_token()
    })

    # ⚠️ NOTE: Supabase Python client does not support direct CREATE TABLE queries.
    # You should create the teacher tables manually in Supabase OR use one shared table.
    # Example of a shared table structure in SQL:
    # CREATE TABLE attendance (
    #     id SERIAL PRIMARY KEY,
    #     teacher TEXT NOT NULL,
    #     roll_number TEXT NOT NULL,
    #     marked_at TIMESTAMP DEFAULT NOW()
    # );

    return jsonify({
        "status": "success",
        "teacher": teacher,
        "token": ATTENDANCE_SESSION["token"]
    }), 200


@app.route("/stop_attendance", methods=["POST"])
def stop_attendance():
    ATTENDANCE_SESSION.update({
        "active": False,
        "token": None,
        "allowed_bssid": None,
        "start_time": 0,
        "token_expiry": 0,
        "teacher": None
    })
    SESSION_ATTENDANCE.clear()
    return jsonify({"status": "success", "message": "Attendance stopped"}), 200


@app.route("/get_token", methods=["GET"])
def get_token():
    if not ATTENDANCE_SESSION["active"]:
        return jsonify({"status": "error", "message": "No active session"}), 400

    now = int(time.time())
    if now > ATTENDANCE_SESSION["token_expiry"]:
        ATTENDANCE_SESSION["token"] = generate_token()

    return jsonify({
        "status": "success",
        "token": ATTENDANCE_SESSION["token"],
        "expires_in": ATTENDANCE_SESSION["token_expiry"] - now
    }), 200


ALLOWED_BSSIDS = ["00:14:22:01:23:45", "00:16:3e:5e:6c:00"]  # classroom WiFi

@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    if not ATTENDANCE_SESSION["active"]:
        return jsonify({"error": "No active attendance session"}), 400

    data = request.get_json()
    roll_number = data.get("roll_number")
    bssid = data.get("bssid")

    if not roll_number or not bssid:
        return jsonify({"error": "Missing roll_number or bssid"}), 401

    # 🔐 Check BSSID
    if bssid not in ALLOWED_BSSIDS:
        return jsonify({"error": "Invalid network. Connect to classroom WiFi."}), 403

    teacher_table = ATTENDANCE_SESSION.get("teacher")
    if not teacher_table:
        return jsonify({"error": "No teacher selected for attendance"}), 400

    timestamp = datetime.now().isoformat()

    try:
        supabase.table(f'"{teacher_table}"').insert({
            "roll_number": roll_number,
            "bssid": bssid,
            "timestamp": timestamp
        }).execute()

        return jsonify({
            "status": "success",
            "message": f"Attendance marked for {roll_number}"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/attendance_list", methods=["GET"])
def attendance_list():
    teacher = ATTENDANCE_SESSION.get("teacher")
    if not teacher:
        return jsonify({"status": "error", "message": "No teacher in session"}), 400

    # Fetch records from Supabase
    response = supabase.table("attendance").select("*").eq("teacher", teacher).execute()

    return jsonify({
        "teacher": teacher,
        "attendance": response.data  # includes roll_number + marked_at
    }), 200


if __name__ == "__main__":
    app.run(debug=True)
