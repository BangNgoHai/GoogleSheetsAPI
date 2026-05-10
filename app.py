import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

import gspread
from google.oauth2.service_account import Credentials


load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {"pdf"}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def allowed_file(filename):
    """
    Kiểm tra file có phải PDF hay không.
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_google_sheet():
    """
    Kết nối tới Google Sheet bằng service account.
    """
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets"
    ]

    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")

    credentials = Credentials.from_service_account_file(
        credentials_file,
        scopes=scopes
    )

    client = gspread.authorize(credentials)

    sheet = client.open_by_key(sheet_id).sheet1

    return sheet


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        age = request.form.get("age", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        desired_position = request.form.get("desired_position", "").strip()
        cv_file = request.files.get("cv_file")

        if not full_name or not age or not phone or not email or not desired_position:
            flash("Vui lòng nhập đầy đủ thông tin.")
            return redirect(url_for("index"))

        if not cv_file or cv_file.filename == "":
            flash("Vui lòng upload file CV dạng PDF.")
            return redirect(url_for("index"))

        if not allowed_file(cv_file.filename):
            flash("Chỉ chấp nhận file PDF.")
            return redirect(url_for("index"))

        original_filename = secure_filename(cv_file.filename)
        timestamp_for_file = datetime.now().strftime("%Y%m%d%H%M%S")
        saved_filename = f"{timestamp_for_file}_{original_filename}"

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

        try:
            sheet = get_google_sheet()
            sheet.append_row(row_data, value_input_option="USER_ENTERED")

            flash("Gửi thông tin ứng tuyển thành công!")

        except Exception as error:
            flash(f"Có lỗi khi gửi dữ liệu lên Google Sheet: {error}")

        return redirect(url_for("index"))

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
