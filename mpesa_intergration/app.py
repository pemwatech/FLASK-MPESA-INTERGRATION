from flask import Flask,request,render_template,request,jsonify,session,redirect,flash    
from dotenv import load_dotenv 
import os 
import requests
from requests.auth import HTTPBasicAuth 
from datetime import datetime 
import base64
import sqlite3 

load_dotenv()

app=Flask(__name__)
app.secret_key=os.getenv('secret_key')

#RUN ONCE AFTER OPENING THE FLASK APPLICATION AND THEN COMMENT
#database initialization
db=sqlite3.connect('database.db')
db.execute('CREATE TABLE IF NOT EXISTS payment(id INTEGER PRIMARY KEY AUTOINCREMENT,status TEXT)')
db.commit()
db.close()


#GET ACCESS TOKEN TO BE ABLE TO TALK TO SAFARICOM TO OPEN YOUR SANDBOX
def get_access_token():
    consumer_secret=os.getenv('CONSUMER_SECRET')
    consumer_key=os.getenv('CONSUMER_KEY')
    URL='https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    r=requests.get(URL,auth=HTTPBasicAuth(consumer_key,consumer_secret))
    return r.json().get('access_token')

@app.route('/',methods=['POST','GET'])
def home():
    #CHECK WHETHER THE REQUEST METHOD IS 'POST' FOR SECURITY  
    if request.method=='POST':
        number=request.form.get('number')           
        amount=int(request.form['amount'])
        shortcode=os.getenv('BUSINESS_SHORTCODE')
        passkey=os.getenv('PASSKEY')
        callback_url=os.getenv('CALLBACK_URL')
        access_token=get_access_token()
        timestamp=datetime.now().strftime('%Y%m%d%H%M%S')
        password=base64.b64encode((shortcode+passkey+timestamp).encode()).decode()
        stkpush_url='https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
        headers={'Authorization':f'Bearer {access_token}','Content-Type':'application/json'}
        payload={
            "BusinessShortCode":shortcode,
            "Password":password,
            "Timestamp":timestamp,
            "TransactionType":"CustomerPayBillOnline",
            "Amount":amount,
            "PartyA":number,
            "PartyB":shortcode,
            "PhoneNumber":number,
            "CallBackURL":callback_url,
            "AccountReference":"TestPayment",
            "TransactionDesc":"Flask M-pesa Test"
        }

        #send stk push
        response=requests.post(stkpush_url,json=payload,headers=headers)
        result=response.json()

        #CHECKING WHETHER THE STK PUSH WAS SENT OR NOT 

        if result.get('ResponseCode')=='0':
            flash('STK Push initiated successfully,check your phone')         
        else:
            flash('stk push initiation failed')

    #GETTING SAFARICOM CALLBACK/FEEDBACK INFORMATION WHICH WAS STORED IN DATABASE DURING...
    #....CALLBACK ROUTE THEN DISPLAY INTO FORM.HTML PAGE

    db=sqlite3.connect('database.db')
    db.row_factory=sqlite3.Row
    message=db.execute('SELECT * FROM payment ORDER BY id DESC LIMIT 1').fetchone()
    

    return render_template('form.html',message=message['status'])

@app.route('/callback',methods=['POST'])
def mpesa_callback():

    #GETTING THE FEEDBACK OR CALLBACK FROM SAFARICOM 
    data=request.get_json()
    stk=data['Body']['stkCallback']
    result_code=stk['ResultCode']
    result_desc=stk['ResultDesc']

    #CHECK WHETHER THE FEEDBACK WAS POSITIVE OR NOT AND STORING IT IN DATABASE TO ACCESS.... 
    #.... IT LATER IN FORM.HTML 
    if result_code==0:
        status='payment successful'
        db=sqlite3.connect('database.db')
        db.execute('INSERT INTO payment (status) VALUES (?)',(status,))
        db.commit()
        db.close()

        

    else:
        db=sqlite3.connect('database.db')
        db.execute('INSERT INTO payment (status) VALUES (?)',(result_desc,))
        db.commit()
        db.close()
            
        
    
    return {'status':'received'},200


    
if __name__=='__main__':
    app.run(debug=True)

