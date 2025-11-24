# app.py — FINAL RENDER.COM VERSION (NOVEMBER 2025)
from uuid import uuid4
import os
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS

from phonepe.sdk.pg.payments.v2.standard_checkout_client import StandardCheckoutClient
from phonepe.sdk.pg.payments.v2.models.request.standard_checkout_pay_request import StandardCheckoutPayRequest
from phonepe.sdk.pg.common.models.request.meta_info import MetaInfo
from phonepe.sdk.pg.env import Env

app = Flask(__name__)
CORS(app)

# === SECURELY READ FROM RENDER ENVIRONMENT VARIABLES ===
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
CLIENT_VERSION = int(os.getenv("CLIENT_VERSION", "1"))
REDIRECT_BASE_URL = os.getenv("REDIRECT_BASE_URL")  # e.g. https://phonepe-flask-server-1.onrender.com

# SANDBOX for testing — Change to Env.PRODUCTION for live
ENV = Env.SANDBOX

client = StandardCheckoutClient.get_instance(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    client_version=CLIENT_VERSION,
    env=ENV,
    should_publish_events=False
)

@app.route('/')
def home():
    return jsonify({
        "status": "PhonePe Server Running",
        "redirect_url": f"{REDIRECT_BASE_URL}/payment-success",
        "environment": "SANDBOX" if ENV == Env.SANDBOX else "PRODUCTION",
        "tip": "POST /pay with amount in paise"
    })

@app.route('/pay', methods=['POST'])
def create_payment():
    try:
        data = request.get_json() or {}
        amount = int(data.get('amount', 10000))  # in paise
        user_id = data.get('userId', 'guest')

        merchant_order_id = f"ORDER_{uuid4().hex[:20]}"
        redirect_url = f"{REDIRECT_BASE_URL}/payment-success"

        pay_request = StandardCheckoutPayRequest.build_request(
            merchant_order_id=merchant_order_id,
            amount=amount,
            redirect_url=redirect_url,
            meta_info=MetaInfo(udf1=user_id, udf2="flutter")
        )

        print(f"Creating payment → {merchant_order_id} | ₹{amount/100:.2f}")
        response = client.pay(pay_request)

        redirect_url_phonepe = getattr(response, 'redirect_url', None)
        if not redirect_url_phonepe:
            return jsonify({"status": "failed", "error": "No redirect from PhonePe"}), 400

        return jsonify({
            "status": "success",
            "merchantOrderId": merchant_order_id,
            "redirectUrl": redirect_url_phonepe
        })

    except Exception as e:
        print("PAYMENT ERROR:", e)
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status/<order_id>')
def check_status(order_id):
    try:
        resp = client.get_payment_status(order_id)
        return jsonify({
            "status": "success",
            "order_id": order_id,
            "payment_state": getattr(resp, "state", "UNKNOWN"),
            "transaction_id": getattr(resp, "transaction_id", None),
            "amount": getattr(resp, "amount", None)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/payment-success')
def payment_success():
    order_id = request.args.get('merchantOrderId') or request.args.get('orderId') or 'N/A'
    status = request.args.get('status', 'PENDING').upper()

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Payment Complete</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{font-family: system-ui; text-align: center; padding: 60px; background: #f8f9fa;}}
            .box {{background: white; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); max-width: 400px; margin: auto;}}
            .success {{color: #28a745;}} .failed {{color: #dc3545;}}
        </style>
    </head>
    <body>
        <div class="box">
            <h1 class="{'success' if status == 'COMPLETED' else 'failed'}">
                {'Payment Successful!' if status == 'COMPLETED' else 'Payment Failed'}
            </h1>
            <p><strong>Order ID:</strong> {order_id}</p>
            <p><strong>Status:</strong> {status}</p>
            <p>Returning to app...</p>
        </div>

        <!-- CRITICAL: Force deep link back to Flutter app -->
        <script>
            // Method 1: Direct deep link (works 99% of cases)
            setTimeout(() => {{
                window.location.href = "stylehub://payment-success?orderId={order_id}&status={status}";
            }}, 1500);

            // Method 2: JS bridge for InAppWebView (backup)
            if (window.flutter_inappwebview) {{
                window.flutter_inappwebview.callHandler('paymentResult', {{
                    orderId: '{order_id}',
                    status: '{status}'
                }});
            }}
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"PhonePe Server Running on port {port}")
    app.run(host="0.0.0.0", port=port)
