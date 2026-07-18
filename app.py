import os
import json
import tempfile
from datetime import datetime
from flask import Flask, request
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

app = Flask(__name__)
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(tempfile.gettempdir(), "uploads"))
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf"}
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise ValueError("Missing GOOGLE_SHEET_ID")
    if not credentials_json:
        raise ValueError("Missing GOOGLE_CREDENTIALS_JSON")
    try:
        creds_data = json.loads(credentials_json)
    except Exception as e:
        raise ValueError(f"Invalid JSON: {e}")
    creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).sheet1

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return '''
            <form method="POST" enctype="multipart/form-data">
                <input name="full_name" placeholder="Full Name"><br>
                <input name="age" placeholder="Age"><br>
                <input name="phone" placeholder="Phone"><br>
                <input name="email" placeholder="Email"><br>
                <input name="desired_position" placeholder="Position"><br>
                <input type="file" name="cv_file" accept=".pdf"><br>
                <input type="submit">
            </form>
        '''
    try:
        print("=== POST received ===", flush=True)
        full_name = request.form.get("full_name", "").strip()
        age = request.form.get("age", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        desired_position = request.form.get("desired_position", "").strip()
        cv_file = request.files.get("cv_file")

        if not all([full_name, age, phone, email, desired_position]):
            return "Missing fields", 400
        if not cv_file or not allowed_file(cv_file.filename):
            return "Invalid file", 400

        # Save file
        original_filename = secure_filename(cv_file.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        saved_filename = f"{timestamp}_{original_filename}"
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], saved_filename)
        cv_file.save(file_path)
        print(f"File saved: {file_path}", flush=True)

        # Google Sheet
        submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [submitted_at, full_name, age, phone, email, desired_position, saved_filename]
        sheet = get_google_sheet()
        sheet.append_row(row_data, value_input_option="USER_ENTERED")
        print("Sheet updated", flush=True)

        # ✅ Không gửi email, không flash, chỉ trả về thành công
        return "SUCCESS: Data saved to sheet and file uploaded."

    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return f"Internal Server Error: {e}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)