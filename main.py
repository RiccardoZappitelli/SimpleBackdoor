import os
import mss
import cv2
import flask
import numpy as np
import pyautogui as pg
from flask import request, jsonify, send_from_directory, Response

app = flask.Flask(__name__, static_folder="static", template_folder="templates")


def generate_screen_frames():
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary screen
        while True:
            img = np.array(sct.grab(monitor))
            # Convert BGRA -> BGR for OpenCV
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route("/screen_stream")
def screen_stream():
    return Response(generate_screen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/")
def homepage():
    return flask.render_template("index.html")

@app.route("/terminal", methods=["POST"])
def terminal():
    data = request.get_json(silent=True) or {}
    cmd = data.get("cmd")
    if not cmd:
        return "", 400
    print("Command received:", cmd, flush=True)

    first_arg = cmd.split()[0].lower()
    cmd_args = " ".join(cmd.split()[1:])

    if first_arg == "cd":
        directory = cmd_args
        if os.path.isfile(directory):
            return "OSError: Trying to change directory in to a file."
        elif os.path.isdir(directory):
            try:
                os.chdir(directory)
                return ""
            except OSError as e:
                return str(e)
        else:
            return "File or directory not found."
    elif first_arg == ":download":
        file_path = cmd_args
        if os.path.isfile(file_path):
            download_url = f"/files/{file_path}?from_upload_dir=false"
            return jsonify({"download_url": download_url})
        else:
            return "OSError: The file does not exist, is a directory or you dont have the permission to read it."
    else:
        try:
            output = os.popen(cmd).read().strip()
            return output if output else f"Executed: {cmd}"
        except Exception as e:
            return f"Error: {e}", 500

@app.route("/mouse", methods=["POST"])
def mouse():
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    step = int(data.get("step", 10))
    print("Mouse:", action, step, flush=True)

    if action in ["up", "down", "left", "right"]:
        move_map = {"up": (0, -step), "down": (0, step), "left": (-step, 0), "right": (step, 0)}
        pg.moveRel(*move_map[action])
    elif action == "leftclick":
        pg.click()
    elif action == "rightclick":
        pg.click(button="right")

    return jsonify({"status": "ok"})

@app.route("/key", methods=["POST"])
def key():
    data = request.get_json(silent=True) or {}
    key = data.get("key")
    if not key:
        return jsonify({"error": "no key"}), 400
    print("Key pressed:", key, flush=True)
    try:
        if key.lower() == "space":
            pg.press("space")
        if key.lower() == "gui":
            pg.press("win")
        else:
            pg.press(key)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f or f.filename == "":
        return jsonify({"error": "no file"}), 400
    path = os.path.join(UPLOAD_DIR, f.filename)
    f.save(path)
    print("Uploaded:", f.filename, flush=True)
    return jsonify({"status": "uploaded", "filename": f.filename})

@app.route("/files", methods=["GET"])
def list_files():
    files = []
    for name in os.listdir(UPLOAD_DIR):
        path = os.path.join(UPLOAD_DIR, name)
        if os.path.isfile(path):
            files.append({"name": name, "size": os.path.getsize(path)})
    return jsonify(files)

@app.route("/files/<path:filename>", methods=["GET"])
def download(filename):
    from_upload_dir = request.args.get("from_upload_dir", "true").lower() == "true"
    base_dir = UPLOAD_DIR if from_upload_dir else os.getcwd()
    print(f"Downloading: {os.path.join(base_dir, filename)}")
    return send_from_directory(base_dir, filename, as_attachment=True)

@app.route("/files/<path:filename>", methods=["DELETE"])
def delete_file(filename):
    path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
        print("Deleted:", filename, flush=True)
        return jsonify({"status": "deleted"})
    return jsonify({"error": "not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=8081)
