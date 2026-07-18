import os
import json
import tempfile
from datetime import datetime

from flask import Flask, render_template, request, flash, get_flashed_messages
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from flask_mail import Mail, Message

import gspread
from google.oauth2.service_account import Credentials


load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(tempfile.gettempdir(), "uploads"))
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

# Email config
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT", 587))
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER", os.getenv("MAIL_USERNAME"))

mail = Mail(app)

ALLOWED_EXTENSIONS = {"pdf"}
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE")
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")

    if not sheet_id:
        raise ValueError("Missing GOOGLE_SHEET_ID")

    if credentials_json:
        try:
            creds_data = json.loads(credentials_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
    elif credentials_file:
        if not os.path.exists(credentials_file):
            raise FileNotFoundError(f"Credential file not found: {credentials_file}")
        creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)
    else:
        raise ValueError("Missing credentials")

    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).sheet1


def send_confirmation_email(email, full_name):
    try:
        subject = "Job Application Confirmation"
        html_body = f"""
        <html>... (giữ nguyên nội dung cũ) ...</html>
        """
        msg = Message(subject=subject, recipients=[email], html=html_body)
        mail.send(msg)
        return True
    except Exception as e:
        app.logger.error(f"Email failed to {email}: {e}", exc_info=True)
        return False


@app.route("/", methods=["GET", "POST"])
def index():
    # Mặc định không có thông báo
    message = None
    message_category = None

    if request.method == "POST":
        # Bắt toàn bộ lỗi từ đây
        try:
            full_name = request.form.get("full_name", "").strip()
            age = request.form.get("age", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip()
            desired_position = request.form.get("desired_position", "").strip()
            cv_file = request.files.get("cv_file")

            # Validate
            if not all([full_name, age, phone, email, desired_position]):
                message = "Please fill in all required fields."
                message_category = "danger"
                return render_template("index.html", message=message, category=message_category)

            if not cv_file or cv_file.filename == "":
                message = "Please upload a CV file."
                message_category = "danger"
                return render_template("index.html", message=message, category=message_category)

            if not allowed_file(cv_file.filename):
                message = "Only PDF files are allowed."
                message_category = "danger"
                return render_template("index.html", message=message, category=message_category)

            # Save file
            original_filename = secure_filename(cv_file.filename)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            saved_filename = f"{timestamp}_{original_filename}"
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], saved_filename)
            cv_file.save(file_path)
            app.logger.info(f"File saved: {file_path}")  # 👈 Log

            # Sheet data
            submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row_data = [submitted_at, full_name, age, phone, email, desired_position, saved_filename]

            # Google Sheet
            sheet = get_google_sheet()
            sheet.append_row(row_data, value_input_option="USER_ENTERED")
            app.logger.info("Google Sheet updated successfully")  # 👈 Log

            # Email
            email_sent = send_confirmation_email(email, full_name)
            if email_sent:
                message = "Application submitted! A confirmation email has been sent."
                message_category = "success"
            else:
                message = "Application submitted, but email could not be sent."
                message_category = "warning"

        except Exception as e:
            # Ghi log đầy đủ, đây là nơi bạn sẽ thấy lỗi trên Render
            app.logger.error(f"ERROR in submission: {e}", exc_info=True)
            message = f"Error: {str(e)}"
            message_category = "danger"

        # Sau khi xử lý xong (có lỗi hay không), render lại form với thông báo
        return render_template("index.html", message=message, category=message_category)

    # GET request
    return render_template("index.html", message=None, category=None)


if __name__ == "__main__":
    # Không chạy debug trong production
    app.run(debug=False, host="0.0.0.0", port=5000)