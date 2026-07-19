import os
import traceback
from datetime import datetime
from threading import Thread

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

import gspread
from google.oauth2.service_account import Credentials


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")


# Upload config
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "/tmp/uploads")
ALLOWED_EXTENSIONS = {"pdf"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Mail config
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER", os.getenv("MAIL_USERNAME"))
app.config["MAIL_TIMEOUT"] = int(os.getenv("MAIL_TIMEOUT", 10))

mail = Mail(app)


# Google Sheets config
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


def allowed_file(filename):
    return filename and "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_google_sheet():
    credentials = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=GOOGLE_SCOPES
    )

    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

    return spreadsheet.sheet1


def send_confirmation_email(email, full_name):
    try:
        msg = Message(
            subject="Application Received - Job Application Collector",
            recipients=[email],
            body=f"""Dear {full_name},

Thank you for your application.

We have successfully received your application information and CV.
Our recruitment team will review your submission and contact you if your profile matches our requirements.

Best regards,
Recruitment Team
"""
        )

        mail.send(msg)
        print(f"Email sent to {email}")

    except Exception:
        print("Email sending error:")
        print(traceback.format_exc())


def send_confirmation_email_async(email, full_name):
    def task():
        with app.app_context():
            send_confirmation_email(email, full_name)

    thread = Thread(target=task)
    thread.daemon = True
    thread.start()


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(error):
    flash("File is too large. Please upload a PDF file smaller than 5MB.")
    return redirect(url_for("index"))


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            full_name = request.form.get("full_name", "").strip()
            age = request.form.get("age", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip()
            desired_position = request.form.get("desired_position", "").strip()
            cv_file = request.files.get("cv_file")

            if not full_name or not age or not phone or not email or not desired_position:
                flash("Please fill in all required fields.")
                return redirect(url_for("index"))

            if not cv_file or cv_file.filename == "":
                flash("Please upload a CV file in PDF format.")
                return redirect(url_for("index"))

            if not allowed_file(cv_file.filename):
                flash("Only PDF files are allowed.")
                return redirect(url_for("index"))

            original_filename = secure_filename(cv_file.filename)
            saved_filename = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + original_filename
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], saved_filename)

            cv_file.save(file_path)

            submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            row_data = [
                submitted_at,
                full_name,
                age,
                phone,
                email,
                desired_position,
                saved_filename
            ]

            sheet = get_google_sheet()
            sheet.append_row(row_data, value_input_option="USER_ENTERED")

            send_confirmation_email_async(email, full_name)

            flash("Application submitted successfully! A confirmation email will be sent shortly.")
            return redirect(url_for("index"))

        except Exception:
            print("ERROR in POST:")
            print(traceback.format_exc())

            flash("An error occurred while submitting your application. Please try again later.")
            return redirect(url_for("index"))

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
