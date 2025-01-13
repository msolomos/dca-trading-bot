from flask import Flask, jsonify
from datetime import datetime
import json
import ccxt

app = Flask(__name__)

# Initialize exchange and load orders
ORDERS_FILE = "/opt/python/dca-bot-bitcoin/orders.json"
PAIR = 'XRP/USDT'
EXCHANGE_NAME = 'binance'

def initialize_exchange():
    with open("/opt/python/dca-bot-bitcoin/config.json", "r") as f:
        keys = json.load(f)
    return getattr(ccxt, EXCHANGE_NAME)({
        "apiKey": keys["API_KEY"],
        "secret": keys["API_SECRET"],
        "enableRateLimit": True
    })

exchange = initialize_exchange()

def load_orders():
    try:
        with open(ORDERS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def calculate_metrics(order, current_price):
    sell_threshold = float(order['price']) * (1 + 2 / 100)  # PERCENTAGE_RISE = 2%
    days_open = (datetime.now() - datetime.strptime(order['datetime'], "%Y-%m-%dT%H:%M:%S.%fZ")).days
    distance_to_sell = sell_threshold - current_price
    return {
        "sell_threshold": sell_threshold,
        "days_open": days_open,
        "distance_to_sell": distance_to_sell,
    }

# Favicon Endpoint
@app.route('/favicon.ico')
def favicon():
    return "", 204

@app.route('/DCA/current_price', methods=['GET'])
def current_price():
    current_price = float(exchange.fetch_ticker(PAIR)['last'])
    return jsonify({"pair": PAIR, "current_price": current_price})

@app.route('/DCA/existing_orders', methods=['GET'])
def existing_orders():
    orders = load_orders()
    current_price = float(exchange.fetch_ticker(PAIR)['last'])
    order_details = []
    for price, order in orders.items():
        metrics = calculate_metrics(order, current_price)
        order_details.append({
            "order_id": order['id'],
            "amount": order['amount'],
            "bought_at": order['price'],
            "sell_at": metrics['sell_threshold'],
            "days_open": metrics['days_open'],
            "distance": metrics['distance_to_sell'],
        })
    return jsonify(order_details)

@app.route('/DCA/sell_threshold_eval', methods=['GET'])
def sell_threshold_eval():
    orders = load_orders()
    current_price = float(exchange.fetch_ticker(PAIR)['last'])
    evaluations = []
    for price, order in orders.items():
        metrics = calculate_metrics(order, current_price)
        status = "Selling" if current_price >= metrics['sell_threshold'] else "Not selling"
        evaluations.append({
            "order_id": order['id'],
            "sell_threshold": metrics['sell_threshold'],
            "current_price": current_price,
            "status": status,
        })
    return jsonify(evaluations)

if __name__ == "__main__":
    # Προσθήκη HTTPS εάν χρειάζεται
    app.run(debug=True, host='0.0.0.0', port=5014, ssl_context=None)  # Προσθέστε SSL αν χρειάζεται
