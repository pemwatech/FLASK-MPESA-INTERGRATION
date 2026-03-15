from flask import Flask, request, render_template, jsonify, redirect
import os, requests, base64
from requests.auth import HTTPBasicAuth
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'devkey')


# Database connection
def get_db():
    url = os.getenv('DATABASE_URL')
    conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
    return conn

# Initialize payment table
def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS payment (
            id SERIAL PRIMARY KEY,
            status TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

init_db()


# M-Pesa token
def get_access_token():
    consumer_key = os.getenv('CONSUMER_KEY')
    consumer_secret = os.getenv('CONSUMER_SECRET')
    url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    r = requests.get(url, auth=HTTPBasicAuth(consumer_key, consumer_secret))
    return r.json().get('access_token')


@app.route('/')
def index():
    return render_template('form.html')


@app.route('/pay', methods=['POST'])
def pay():
    data = request.get_json()
    number = data.get('number')
    amount = int(data.get('amount'))

    shortcode = os.getenv('BUSINESS_SHORTCODE')
    passkey = os.getenv('PASSKEY')
    callback_url = os.getenv('CALLBACK_URL')

    access_token = get_access_token()
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()

    stk_url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": number,
        "PartyB": shortcode,
        "PhoneNumber": number,
        "CallBackURL": callback_url,
        "AccountReference": "TestPayment",
        "TransactionDesc": "Flask M-Pesa Test"
    }

    response = requests.post(stk_url, json=payload, headers=headers)
    result = response.json()

    if result.get('ResponseCode') == '0':
        # STK Push successfully initiated
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': result.get('errorMessage', 'Unknown error')})


@app.route('/status')
def status():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM payment ORDER BY id DESC LIMIT 1')
    message = cur.fetchone()
    cur.close()
    conn.close()

    status_text = message['status'] if message else None
    return jsonify({'status': status_text})


@app.route('/callback', methods=['POST'])
def mpesa_callback():
    data = request.get_json()
    stk = data.get('Body', {}).get('stkCallback', {})
    result_code = stk.get('ResultCode')
    result_desc = stk.get('ResultDesc')

    conn = get_db()
    cur = conn.cursor()
    if result_code == 0:
        cur.execute('INSERT INTO payment (status) VALUES (%s)', ('Payment successful',))
    else:
        cur.execute('INSERT INTO payment (status) VALUES (%s)', (result_desc,))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({'status': 'received'}), 200


@app.route('/success')
def success():
    return "<h1>Payment Successful!</h1>"