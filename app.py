import os
import sys
from flask import Flask, request

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    print("=== ROUTE CALLED ===", flush=True)
    if request.method == 'POST':
        print("POST request received", flush=True)
        try:
            name = request.form.get('full_name', 'Unknown')
            print(f"Name: {name}", flush=True)
            return f"Hello, {name}!"
        except Exception as e:
            print(f"ERROR in POST: {e}", flush=True)
            return "Internal Server Error", 500
    return '''
        <form method="POST">
            <input name="full_name" placeholder="Your name">
            <input type="submit">
        </form>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)