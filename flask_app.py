from flask import Flask, request, jsonify
from supabase import create_client, Client
from datetime import datetime
import random
import string
import time
import requests

app = Flask(__name__)

# Supabase config
SUPABASE_URL = "https://nbkduqhirhnirxssribc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5ia2R1cWhpcmhuaXJ4c3NyaWJjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY5MTE5ODksImV4cCI6MjA3MjQ4Nzk4OX0.4hEnQwToDplh3kqth_OA45TEpSLlaQPJ1S3Jl3tEHMA"

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



@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    passwd = data.get("passwd")

    try:
        # Query teacher_subjects table
        result = supabase.table("teacher_subjects").select("*").eq("email", email).execute()

        if len(result.data) == 1:
            teacher = result.data[0]
            if teacher["passwd"] == passwd:
                return jsonify({
                    "status": "success",
                    "teacher_id": teacher["teacher_id"],
                    "subject_id": teacher["subject_id"]
                })

        return jsonify({"status": "error", "message": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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
@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    if not ATTENDANCE_SESSION["active"]:
        return jsonify({"status": "error", "message": "No active session"}), 400

    data = request.json
    roll_number = data.get("roll_number")
    bssid = data.get("bssid")
    token = data.get("token")

    if not roll_number or not bssid or not token:
        return jsonify({"status": "error", "message": "Missing roll_number, bssid, or token"}), 400

    if int(time.time()) > ATTENDANCE_SESSION.get("token_expiry", 0):
        return jsonify({"status": "error", "message": "Token expired"}), 400

    if roll_number in SESSION_ATTENDANCE:
        return jsonify({"status": "error", "message": "Already marked"}), 400

    if token != ATTENDANCE_SESSION["token"]:
        return jsonify({"status": "error", "message": "Invalid token"}), 400
    if bssid != ATTENDANCE_SESSION["allowed_bssid"]:
        return jsonify({"status": "error", "message": "Invalid BSSID"}), 400

    # Mark locally
    SESSION_ATTENDANCE.append(roll_number)

    # 1. Get max id from Supabase
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/attendance?select=id&order=id.desc&limit=1",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            }
        )
        max_id = res.json()[0]["id"] if res.status_code == 200 and res.json() else 0
    except Exception as e:
        return jsonify({"status": "error", "message": f"Supabase fetch error: {str(e)}"}), 500

    new_id = max_id + 1

    # 2. Insert with manual id
    payload = {
        "id": new_id,
        "student_id": roll_number,
        "subject_id": ATTENDANCE_SESSION["teacher"],
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "present"
    }

    try:
        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/attendance",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            json=payload
        )
        if res.status_code not in (200, 201):
            return jsonify({"status": "error", "message": f"Supabase insert failed: {res.text}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"Supabase error: {str(e)}"}), 500

    return jsonify({"status": "success", "message": f"Attendance marked for {roll_number}"}), 200


@app.route("/attendance_list", methods=["GET"])
def attendance_list():
    return jsonify({
        "teacher": ATTENDANCE_SESSION.get("teacher"),
        "attendance": SESSION_ATTENDANCE
    }), 200

# Run locally
if __name__ == "__main__":
    app.run(debug=True)
