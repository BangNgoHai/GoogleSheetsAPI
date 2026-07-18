import os
import json
import tempfile
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


# =========================
# Load environment variables
# =========================
load_dotenv()


# =========================
# App setup
# =========================
app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")


# =========================
# Upload config
# =========================
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "/tmp/uploads")
ALLOWED_EXTENSIONS = {"pdf"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# =========================
# Mail config
# =========================
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True").lower() in ["true", "1", "yes"]
app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL", "False").lower() in ["true", "1", "yes"]
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER", os.getenv("MAIL_USERNAME"))
app.config["MAIL_TIMEOUT"] = int(os.getenv("MAIL_TIMEOUT", 10))

mail = Mail(app)


# =========================
# Google Sheets config
# =========================
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


# =========================
# Startup logs
# =========================
print("=== ENVIRONMENT CHECK ===")
print("GOOGLE_CREDENTIALS_FILE:", GOOGLE_CREDENTIALS_FILE if GOOGLE_CREDENTIALS_FILE else "NOT SET")
print("GOOGLE_CREDENTIALS_JSON:", "SET" if GOOGLE_CREDENTIALS_JSON else "NOT SET")
print("GOOGLE_SHEET_ID:", GOOGLE_SHEET_ID if GOOGLE_SHEET_ID else "NOT SET")
print("UPLOAD_FOLDER:", app.config["UPLOAD_FOLDER"])
print("MAIL_SERVER:", app.config["MAIL_SERVER"])
print("MAIL_PORT:", app.config["MAIL_PORT"])
print("MAIL_USE_TLS:", app.config["MAIL_USE_TLS"])
print("MAIL_USE_SSL:", app.config["MAIL_USE_SSL"])
print("MAIL_USERNAME:", "SET" if app.config["MAIL_USERNAME"] else "NOT SET")
print("MAIL_PASSWORD:", "SET" if app.config["MAIL_PASSWORD"] else "NOT SET")
print("MAIL_DEFAULT_SENDER:", app.config["MAIL_DEFAULT_SENDER"] if app.config["MAIL_DEFAULT_SENDER"] else "NOT SET")
print("Current directory:", os.getcwd())

try:
    print("Files in current dir:", os.listdir("."))
except Exception as error:
    print("Could not list current directory:", error)

print("==========================")


# =========================
# Helper functions
# =========================
def allowed_file(filename):
    if not filename:
        return False

    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_google_credentials():
    """
    Supports two modes:
    1. GOOGLE_CREDENTIALS_JSON: raw JSON string in environment variable.
    2. GOOGLE_CREDENTIALS_FILE: path to credentials.json file.
    """

    if GOOGLE_CREDENTIALS_JSON:
        print("Using GOOGLE_CREDENTIALS_JSON")
        credentials_info = json.loads(GOOGLE_CREDENTIALS_JSON)
        credentials = Credentials.from_service_account_info(
            credentials_info,
            scopes=GOOGLE_SCOPES
        )
        return credentials

    if GOOGLE_CREDENTIALS_FILE:
        print("Using GOOGLE_CREDENTIALS_FILE:", GOOGLE_CREDENTIALS_FILE)
        print("Credentials file exists:", os.path.exists(GOOGLE_CREDENTIALS_FILE))

        if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
            raise FileNotFoundError(f"Credentials file not found: {GOOGLE_CREDENTIALS_FILE}")

        credentials = Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE,
            scopes=GOOGLE_SCOPES
        )
        return credentials

    raise ValueError("No Google credentials provided. Set GOOGLE_CREDENTIALS_FILE or GOOGLE_CREDENTIALS_JSON.")


def get_google_sheet():
    if not GOOGLE_SHEET_ID:
        raise ValueError("GOOGLE_SHEET_ID is not set.")

    credentials = get_google_credentials()
    client = gspread.authorize(credentials)

    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    sheet = spreadsheet.sheet1

    return sheet


def send_confirmation_email(email, full_name):
    """
    Sends confirmation email.
    This function is safe: it catches errors and returns True/False.
    """

    try:
        if not app.config["MAIL_USERNAME"]:
            print("MAIL_USERNAME is not set. Skip sending email.")
            return False

        if not app.config["MAIL_PASSWORD"]:
            print("MAIL_PASSWORD is not set. Skip sending email.")
            return False

        if not app.config["MAIL_DEFAULT_SENDER"]:
            print("MAIL_DEFAULT_SENDER is not set. Skip sending email.")
            return False

        subject = "Application Received - Job Application Collector"

        body = f"""Dear {full_name},

Thank you for your application.

We have successfully received your application information and CV.
Our recruitment team will review your submission and contact you if your profile matches our requirements.

Best regards,
Recruitment Team
"""

        msg = Message(
            subject=subject,
            recipients=[email],
            body=body
        )

        print(f"Sending confirmation email to {email}...")
        mail.send(msg)
        print(f"Email sent successfully to {email}")

        return True

    except Exception:
        print("Email sending error:")
        print(traceback.format_exc())
        return False


def send_confirmation_email_async(email, full_name):
    """
    Sends email in background thread to avoid blocking request on Render.
    """

    def task():
        with app.app_context():
            try:
                result = send_confirmation_email(email, full_name)
                print(f"Background email result for {email}: {result}")
            except Exception:
                print("Unexpected background email error:")
                print(traceback.format_exc())

    thread = Thread(target=task)
    thread.daemon = True
    thread.start()


# =========================
# Error handlers
# =========================
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(error):
    flash("File is too large. Please upload a PDF file smaller than 5MB.")
    return redirect(url_for("index"))


@app.errorhandler(500)
def handle_internal_error(error):
    print("Internal Server Error:")
    print(error)
    flash("Internal Server Error. Please try again later.")
    return redirect(url_for("index"))


# =========================
# Routes
# =========================
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        print("=== POST RECEIVED ===")
        print("Form keys:", list(request.form.keys()))
        print("File keys:", list(request.files.keys()))

        try:
            full_name = request.form.get("full_name", "").strip()
            age = request.form.get("age", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip()
            desired_position = request.form.get("desired_position", "").strip()
            cv_file = request.files.get("cv_file")

            print("Received application:")
            print("Full name:", full_name)
            print("Age:", age)
            print("Phone:", phone)
            print("Email:", email)
            print("Desired position:", desired_position)
            print("CV file:", cv_file.filename if cv_file else "NO FILE")

            # Validate required fields
            if not full_name or not age or not phone or not email or not desired_position:
                flash("Please fill in all required fields.")
                return redirect(url_for("index"))

            if not cv_file or cv_file.filename == "":
                flash("Please upload a CV file in PDF format.")
                return redirect(url_for("index"))

            if not allowed_file(cv_file.filename):
                flash("Only PDF files are allowed.")
                return redirect(url_for("index"))

            # Save CV file
            original_filename = secure_filename(cv_file.filename)
            timestamp_for_file = datetime.now().strftime("%Y%m%d%H%M%S")
            saved_filename = f"{timestamp_for_file}_{original_filename}"

            file_path = os.path.join(app.config["UPLOAD_FOLDER"], saved_filename)
            cv_file.save(file_path)

            print("CV saved successfully:", file_path)
            print("Saved file exists:", os.path.exists(file_path))

            # Prepare Google Sheet row
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

            # Append to Google Sheet
            print("Opening Google Sheet...")
            sheet = get_google_sheet()

            print("Appending row to Google Sheet...")
            sheet.append_row(row_data, value_input_option="USER_ENTERED")
            print("Google Sheet updated successfully.")

            # Send email in background to avoid timeout
            send_confirmation_email_async(email, full_name)
            print("Background confirmation email started.")

            flash("Application submitted successfully! A confirmation email will be sent shortly.")
            return redirect(url_for("index"))

        except Exception:
            print("ERROR in POST:")
            print(traceback.format_exc())

            flash("An error occurred while submitting your application. Please try again later.")
            return redirect(url_for("index"))

    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health():
    return {
        "status": "ok",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }, 200


@app.route("/debug-env", methods=["GET"])
def debug_env():
    """
    Safe debug route.
    Does not expose secret values.
    Remove this route after debugging if you want.
    """

    credentials_file_exists = False

    if GOOGLE_CREDENTIALS_FILE:
        credentials_file_exists = os.path.exists(GOOGLE_CREDENTIALS_FILE)

    return {
        "google_sheet_id_set": bool(GOOGLE_SHEET_ID),
        "google_credentials_file": GOOGLE_CREDENTIALS_FILE if GOOGLE_CREDENTIALS_FILE else None,
        "google_credentials_file_exists": credentials_file_exists,
        "google_credentials_json_set": bool(GOOGLE_CREDENTIALS_JSON),
        "upload_folder": app.config["UPLOAD_FOLDER"],
        "upload_folder_exists": os.path.exists(app.config["UPLOAD_FOLDER"]),
        "mail_server": app.config["MAIL_SERVER"],
        "mail_port": app.config["MAIL_PORT"],
        "mail_use_tls": app.config["MAIL_USE_TLS"],
        "mail_use_ssl": app.config["MAIL_USE_SSL"],
        "mail_username_set": bool(app.config["MAIL_USERNAME"]),
        "mail_password_set": bool(app.config["MAIL_PASSWORD"]),
        "mail_default_sender_set": bool(app.config["MAIL_DEFAULT_SENDER"]),
        "current_directory": os.getcwd()
    }, 200


@app.route("/ping-post", methods=["POST"])
def ping_post():
    print("PING POST RECEIVED")
    return "PING POST OK", 200


# =========================
# Local run
# =========================
if __name__ == "__main__":
    app.run(debug=True)
