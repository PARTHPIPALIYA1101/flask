from flask import Flask, request, jsonify
import random
import string
import time

app = Flask(__name__)

ATTENDANCE_SESSION = {"active": False, "token": None, "start_time": 0, "allowed_bssid": None}
SESSION_ATTENDANCE = []

@app.route("/start_attendance", methods=["POST"])
def start_attendance():
    data = request.json
    teacher = data.get("teacher")
    bssid = data.get("bssid")

    SESSION_ATTENDANCE.clear()
    ATTENDANCE_SESSION["active"] = True
    ATTENDANCE_SESSION["allowed_bssid"] = bssid
    ATTENDANCE_SESSION["start_time"] = int(time.time())
    ATTENDANCE_SESSION["token"] = generate_token()

    return jsonify({"status": "success", "teacher": teacher, "token": ATTENDANCE_SESSION["token"]})

@app.route("/stop_attendance", methods=["POST"])
def stop_attendance():
    ATTENDANCE_SESSION.update({"active": False, "token": None, "allowed_bssid": None, "start_time": 0})
    SESSION_ATTENDANCE.clear()
    return jsonify({"status": "success", "message": "Attendance stopped"})

@app.route("/get_token", methods=["GET"])
def get_token():
    if not ATTENDANCE_SESSION["active"]:
        return jsonify({"status": "error", "message": "No active session"}), 400
    ATTENDANCE_SESSION["token"] = generate_token()
    return jsonify({"status": "success", "token": ATTENDANCE_SESSION["token"]})

@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    if not ATTENDANCE_SESSION["active"]:
        return jsonify({"status": "error", "message": "No active session"}), 400
    data = request.json
    roll_number = data.get("roll_number")
    token = data.get("token")
    bssid = data.get("bssid")

    if roll_number in SESSION_ATTENDANCE:
        return jsonify({"status": "error", "message": "Already marked"}), 400
    if token != ATTENDANCE_SESSION["token"]:
        return jsonify({"status": "error", "message": "Invalid token"}), 400
    if bssid != ATTENDANCE_SESSION["allowed_bssid"]:
        return jsonify({"status": "error", "message": "Invalid BSSID"}), 400

    SESSION_ATTENDANCE.append(roll_number)
    return jsonify({"status": "success", "message": f"Attendance marked for {roll_number}"})

def generate_token(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# Only for local testing (Render ignores this)
if __name__ == "__main__":
    app.run(debug=True)
