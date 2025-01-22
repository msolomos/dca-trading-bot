from flask import Flask, jsonify
from datetime import datetime
import json
import ccxt

app = Flask(__name__)



# Config files
ORDERS_FILE = "/opt/python/dca-bot-bitcoin/orders.json"
CONFIG_FILE = "/opt/python/dca-bot-bitcoin/config.json"


def load_pair_and_exchange():
    """Load PAIR and EXCHANGE_NAME from the JSON configuration file."""
    try:
        with open(CONFIG_FILE, "r") as file:
            keys = json.load(file)
            
            # Ανάγνωση της ενότητας TRADE_CONFIG
            trade_config = keys.get("TRADE_CONFIG", {})
            pair = trade_config.get("PAIR")
            exchange_name = trade_config.get("EXCHANGE_NAME")
            
            # Έλεγχος για κενές τιμές
            if not pair or not exchange_name:
                missing_keys = []
                if not pair:
                    missing_keys.append("PAIR")
                if not exchange_name:
                    missing_keys.append("EXCHANGE_NAME")
                raise ValueError(f"Missing keys in the JSON file: {', '.join(missing_keys)}")

            return pair, exchange_name
    except FileNotFoundError:
        raise FileNotFoundError(f"The specified JSON file '{CONFIG_FILE}' was not found.")
    except json.JSONDecodeError:
        raise ValueError(f"The JSON file '{CONFIG_FILE}' is not properly formatted.")


# Φόρτωση PAIR και EXCHANGE_NAME
PAIR, EXCHANGE_NAME = load_pair_and_exchange()



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
    if 'price' not in order:
        raise KeyError("'price' key is missing from the order.")
    
    sell_threshold = float(order['price']) * (1 + 2 / 100)  # PERCENTAGE_RISE = 2%
    days_open = (datetime.utcnow() - datetime.strptime(order['datetime'], "%Y-%m-%dT%H:%M:%S.%fZ")).days
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
    # Φόρτωση μόνο των ORDERS από το αρχείο
    orders_data = load_orders()
    orders = orders_data.get("ORDERS", {})  # Παίρνουμε μόνο το αντικείμενο ORDERS

    current_price = float(exchange.fetch_ticker(PAIR)['last'])
    order_details = []

    for price, order in orders.items():
        # Έλεγχος για το κλειδί 'price' και 'datetime'
        if 'price' not in order or 'datetime' not in order:
            logging.error(f"Order missing required keys: {order}")
            continue  # Αγνόηση παραγγελίας χωρίς τα απαραίτητα κλειδιά

        metrics = calculate_metrics(order, current_price)

        # Μετατροπή της ημερομηνίας
        try:
            iso_datetime = datetime.strptime(order['datetime'], "%Y-%m-%dT%H:%M:%S.%fZ")
            formatted_datetime = iso_datetime.strftime("%d/%m/%Y %H:%M")
        except ValueError as e:
            logging.error(f"Invalid datetime format for order: {order['datetime']}")
            formatted_datetime = "Invalid Date"

        order_details.append({
            "order_id": order['id'],
            "amount": order['amount'],
            "bought_at": order['price'],
            "sell_at": metrics['sell_threshold'],
            "days_open": metrics['days_open'],
            "distance": metrics['distance_to_sell'],
            "datetime": formatted_datetime,  # Επιστροφή της μετασχηματισμένης ημερομηνίας
        })

    return jsonify(order_details)








@app.route('/DCA/sell_threshold_eval', methods=['GET'])
def sell_threshold_eval():
    # Φόρτωση μόνο των ORDERS από το αρχείο
    orders_data = load_orders()
    orders = orders_data.get("ORDERS", {})  # Παίρνουμε μόνο το αντικείμενο ORDERS

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
