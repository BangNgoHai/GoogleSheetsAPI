import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from flask_mail import Mail, Message

import gspread
from google.oauth2.service_account import Credentials


load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

# Email Configuration
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
    """
    check if the uploaded file has an allowed extension (PDF in this case).
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_google_sheet():
    """
    connect to google sheet using service account.
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


def send_confirmation_email(email, full_name):
    """
    send email to applicant after submit
    """
    try:
        subject = "Job Application Confirmation"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="background-color: #f4f7fb; padding: 20px; border-radius: 8px;">
                    <h2 style="color: #2563eb;">Thank you for your application!</h2>
                    <p>Hello <strong>{full_name}</strong>,</p>
                    
                    <p>We have received your job application at <strong>{datetime.now().strftime("%d/%m/%Y %H:%M:%S")}</strong>.</p>
                    
                    <p>Your application will be reviewed carefully. If you meet the requirements, we will contact you within <strong>7 business days</strong>.</p>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    
                    <p style="color: #666; font-size: 13px;">
                        <strong>Contact Information:</strong><br>
                        Email: {email}<br>
                        Submission Date: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
                    </p>
                    
                    <p style="color: #999; font-size: 12px;">
                        This is an automated email. Please do not reply to this email.
                    </p>
                </div>
            </body>
        </html>
        """
        
        #create a email has subject, recipients, html_body
        msg = Message(
            subject=subject,
            recipients=[email],
            html=html_body
        )

        #Mail object will send email to recipient with subject and html body
        #Message object for a specific email

        
        mail.send(msg)
        return True
        
    except Exception as error:
        print(f"Error sending email: {error}")
        return False


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
            flash("Please fill in all required fields.")
            return redirect(url_for("index"))

        if not cv_file or cv_file.filename == "":
            flash("Please upload a CV file in PDF format.")
            return redirect(url_for("index"))

        if not allowed_file(cv_file.filename):
            flash("Only PDF files are allowed.")
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

            # Send confirmation email to applicant
            email_sent = send_confirmation_email(email, full_name)
            
            if email_sent:
                flash("Application submitted successfully! A confirmation email has been sent.")
            else:
                flash("Application submitted successfully! (Confirmation email could not be sent)")

        except Exception as error:
            flash(f"An error occurred while submitting the application: {error}")

        return redirect(url_for("index"))

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
