import ccxt
import time
import logging
import json
from datetime import datetime, timedelta

# Configure logging to both file and console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/opt/python/dca-bot-bitcoin/dca_bot.log"),
        logging.StreamHandler(),
    ],
)

# Configuration
PAIR = 'XRP/USDT'
CRYPTO_SYMBOL = 'XRP'
CRYPTO_CURRENCY = 'USDT'
EXCHANGE_NAME = 'binance'
PERCENTAGE_DROP = 5
PERCENTAGE_RISE = 3
TRADE_AMOUNT = 5
ORDERS_FILE = "/opt/python/dca-bot-bitcoin/orders.json"
JSON_PATH = "/opt/python/dca-bot-bitcoin/config.json"

# Load Keys from external file
def load_keys():
    try:
        with open(JSON_PATH, "r") as file:
            keys = json.load(file)
            api_key = keys.get("API_KEY")
            api_secret = keys.get("API_SECRET")
            if not api_key or not api_secret:
                raise ValueError("API_KEY or API_SECRET missing.")
            return api_key, api_secret
    except Exception as e:
        logging.error(f"Error loading keys: {e}")
        raise

# Initialize exchange
def initialize_exchange():
    try:
        API_KEY, API_SECRET = load_keys()
        exchange = getattr(ccxt, EXCHANGE_NAME)({
            "apiKey": API_KEY,
            "secret": API_SECRET,
            "enableRateLimit": True,
        })
        exchange.set_sandbox_mode(False)
        exchange.load_markets()
        logging.info(f"Connected to {EXCHANGE_NAME} - Markets loaded: {len(exchange.markets)}")
        return exchange
    except Exception as e:
        logging.error(f"Failed to connect to {EXCHANGE_NAME}: {e}")
        raise

# Load or initialize orders
def load_or_initialize_orders():
    try:
        with open(ORDERS_FILE, 'r') as f:
            orders = json.load(f)
            if not isinstance(orders, dict):
                raise ValueError("Orders file contains invalid data.")
            return orders
    except (FileNotFoundError, ValueError):
        logging.warning("Orders file not found or invalid. Initializing new orders.")
        return {}

# Save orders
def save_orders(orders):
    try:
        with open(ORDERS_FILE, 'w') as f:
            json.dump(orders, f, indent=4)
    except Exception as e:
        logging.error(f"Failed to save orders: {e}")

# Calculate metrics
def calculate_metrics(order, current_price):
    sell_threshold = float(order['price']) * (1 + PERCENTAGE_RISE / 100)
    days_open = (datetime.now() - datetime.strptime(order['datetime'], "%Y-%m-%dT%H:%M:%S.%fZ")).days
    distance_to_sell = sell_threshold - current_price
    return {
        "sell_threshold": sell_threshold,
        "days_open": days_open,
        "distance_to_sell": distance_to_sell,
    }

# Main trading function
def run_dca_bot():
    logging.info(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    logging.info("Starting DCA Trading bot...")
    
    # Initialize Exchange and load orders
    exchange = initialize_exchange()
    orders = load_or_initialize_orders()
    logging.info(f"Loaded {len(orders)} existing order(s).")
    
    # Fetch the initial price
    last_price = float(exchange.fetch_ticker(PAIR)['last'])
    logging.info(f"Starting price: {last_price}")    

    try:
        while True:
            iteration_start = time.time()

            logging.info(f"==========================================================")
            logging.info(f"Starting a new loop iteration for {PAIR}")
            logging.info(f"==========================================================")

            
            # Fetch the current price
            current_price = float(exchange.fetch_ticker(PAIR)['last'])
            logging.info(f"Current price: {current_price} {CRYPTO_CURRENCY}")

            # Log details of existing orders
            if orders:
                logging.info("Existing orders:")
                for price, order in orders.items():
                    metrics = calculate_metrics(order, current_price)
                    readable_datetime = datetime.strptime(order['datetime'], "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d %H:%M:%S")
                    logging.info(f" - Order ID: {order['id']}, Amount: {order['amount']}, Bought at: {order['price']}, Sell at: {metrics['sell_threshold']:.4f}, Days Open: {metrics['days_open']}, Distance to Sell: {metrics['distance_to_sell']:.4f}")
                    logging.info(f" - Metrics: Days Open: {metrics['days_open']}, Distance to Sell: {metrics['distance_to_sell']:.4f}")
            else:
                logging.info("No existing orders.")
                
            # Handle buying logic
            if not orders or current_price <= min(map(float, orders.keys())) * (1 - PERCENTAGE_DROP / 100):
                
                # Buy Crypto
                try:
                    order = exchange.create_market_buy_order(PAIR, TRADE_AMOUNT)
                    logging.info(f"Bought {TRADE_AMOUNT} {CRYPTO_SYMBOL} at {current_price}")
                    
                except ccxt.BaseError as api_error:
                    logging.error(f"Error placing buy order: {api_error}")
                    continue                    
                    
                    
                    # Record the order
                    order_data = {
                        "id": order['id'],
                        "symbol": PAIR,
                        "price": current_price,
                        "side": "buy",
                        "status": "open",
                        "amount": TRADE_AMOUNT,
                        "remaining": TRADE_AMOUNT,
                        "datetime": order['datetime'],
                        "timestamp": order['timestamp']
                    }
                    orders[str(current_price)] = order_data
                    save_orders()
                    
                    
                    
            # Handle selling logic
            for price, order in list(orders.items()):  # Copy to avoid modifying during iteration
                sell_threshold = float(price) * (1 + PERCENTAGE_RISE / 100)
                logging.info(f"Calculated sell threshold: {sell_threshold:.4f} for order price: {price}")
                

                if current_price >= sell_threshold:
                    # Sell BTC
                    sell_order = binance.create_market_sell_order(PAIR, order['amount'])
                    logging.info(f"Sold {order['amount']} {CRYPTO_SYMBOL} at {current_price} {CRYPTO_CURRENCY}")

                    # Remove the order from the list
                    del orders[price]
                    save_orders()
                    
                else:
                    logging.info(f"Current price {current_price:.4f} did not reach the sell threshold {sell_threshold:.4f}. Skipping this round.")


            # Μετά την ολοκλήρωση του iteration
            iteration_end = time.time()
            logging.info(f"Loop iteration completed in {iteration_end - iteration_start:.2f} seconds.")

            time.sleep(60)
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    run_dca_bot()
