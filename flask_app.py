from flask import Flask, request, jsonify
import random
import string
import time

app = Flask(__name__)

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

    # Validate payload
    if not roll_number or not bssid or not token:
        return jsonify({"status": "error", "message": "Missing roll_number, bssid, or token"}), 400

    # Check token expiry
    if int(time.time()) > ATTENDANCE_SESSION.get("token_expiry", 0):
        return jsonify({"status": "error", "message": "Token expired"}), 400

    # Check already marked
    if roll_number in SESSION_ATTENDANCE:
        return jsonify({"status": "error", "message": "Already marked"}), 400

    # Validate token and BSSID
    if token != ATTENDANCE_SESSION["token"]:
        return jsonify({"status": "error", "message": "Invalid token"}), 400
    if bssid != ATTENDANCE_SESSION["allowed_bssid"]:
        return jsonify({"status": "error", "message": "Invalid BSSID"}), 400

    # Mark attendance
    SESSION_ATTENDANCE.append(roll_number)
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
