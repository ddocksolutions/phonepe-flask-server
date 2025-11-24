# app.py — FINAL Render Hosting Version (PhonePe SDK v2)
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

# ====================== ENVIRONMENT VARIABLES (Render) ======================
CLIENT_ID = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")
CLIENT_VERSION = int(os.environ.get("CLIENT_VERSION", "1"))
REDIRECT_BASE_URL = os.environ.get("REDIRECT_BASE_URL", "")
ENV = Env.SANDBOX

# PhonePe Client
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
        "status": "running",
        "redirect_url": f"{REDIRECT_BASE_URL}/payment-success",
        "usage": "POST /pay { amount: 10000 }"
    })

@app.route('/pay', methods=['POST'])
def create_payment():
    try:
        data = request.get_json() or {}
        amount = int(data.get('amount', 10000))
        user_id = data.get('userId', 'guest')

        merchant_order_id = f"ORDER_{uuid4().hex[:20]}"
        redirect_url = f"{REDIRECT_BASE_URL}/payment-success"

        pay_request = StandardCheckoutPayRequest.build_request(
            merchant_order_id=merchant_order_id,
            amount=amount,
            redirect_url=redirect_url,
            meta_info=MetaInfo(udf1=user_id, udf2="flutter")
        )

        print(f"PAYMENT START → {merchant_order_id} | ₹{amount/100}")

        response = client.pay(pay_request)
        redirect_url_phonepe = getattr(response, "redirect_url", None)

        if not redirect_url_phonepe:
            return jsonify({
                "status": "failed",
                "message": "No redirect URL from PhonePe",
                "orderId": merchant_order_id
            }), 400

        return jsonify({
            "status": "success",
            "redirectUrl": redirect_url_phonepe,
            "orderId": merchant_order_id
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/status/<order_id>')
def status(order_id):
    try:
        resp = client.get_payment_status(order_id)
        return jsonify({
            "status": "success",
            "merchantOrderId": merchant_order_id,
            "payment_state": getattr(resp, "state", None),
            "transaction_id": getattr(resp, "transaction_id", None),
            "amount": getattr(resp, "amount", None)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/payment-success')
def payment_success():
    order_id = request.args.get("merchantOrderId") or request.args.get("orderId")
    status = request.args.get("status", "PENDING")

    html = f"""
    <html>
    <head><title>Payment Result</title></head>
    <body style="font-family:Arial;text-align:center;padding:50px;">
        <h1>{'✅ Payment Successful' if status.upper() == 'COMPLETED' else '❌ Payment Failed'}</h1>
        <p><b>Order ID:</b> {order_id}</p>
        <p><b>Status:</b> {status}</p>
        <script>
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
    print("Server running on port:", port)
    app.run(host="0.0.0.0", port=port)
