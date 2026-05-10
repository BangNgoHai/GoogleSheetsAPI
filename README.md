# Job Application Collector Automation

A simple Python Flask web application that collects job applicant information and saves the data automatically to Google Sheets.

## Features

- Collect applicant information through a web form
- Upload CV file in PDF format
- Save uploaded PDF files locally
- Send applicant data to Google Sheets using Google Sheets API
- Simple HTML/CSS user interface
- Environment variables for configuration

## Tech Stack

- Python
- Flask
- HTML
- CSS
- Google Sheets API
- gspread
- python-dotenv

## Project Structure

```text
job-application-automation/
│
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── .env.example
│
├── templates/
│   └── index.html
│
├── static/
│   └── style.css
│
└── uploads/
