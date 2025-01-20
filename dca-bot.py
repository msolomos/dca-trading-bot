import ccxt
import pandas as pd
import time
import logging
import json
from datetime import datetime, timedelta
import pushover

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
PERCENTAGE_DROP = 2
PERCENTAGE_RISE = 2
TRADE_AMOUNT = 50
ORDERS_FILE = "/opt/python/dca-bot-bitcoin/orders.json"
CONFIG_FILE = "/opt/python/dca-bot-bitcoin/config.json"
startBot = True

# Παράμετροι Αποστολής E-mail
ENABLE_EMAIL_NOTIFICATIONS = True
ENABLE_PUSH_NOTIFICATIONS = True



# Load Keys from external file
def load_keys():
    """Load API credentials and notification settings from a JSON file."""
    try:
        with open(CONFIG_FILE, "r") as file:
            keys = json.load(file)
            
            # Απαραίτητα κλειδιά για το API
            api_key = keys.get("API_KEY")
            api_secret = keys.get("API_SECRET")
            
            # Κλειδιά για ειδοποιήσεις
            sendgrid_api_key = keys.get("SENDGRID_API_KEY")
            pushover_token = keys.get("PUSHOVER_TOKEN")
            pushover_user = keys.get("PUSHOVER_USER")
            email_sender = keys.get("EMAIL_SENDER")
            email_recipient = keys.get("EMAIL_RECIPIENT")

            # Έλεγχος για κενές τιμές
            missing_keys = []
            if not api_key or not api_secret:
                missing_keys.extend(["API_KEY", "API_SECRET"])
            if not sendgrid_api_key:
                missing_keys.append("SENDGRID_API_KEY")
            if not pushover_token:
                missing_keys.append("PUSHOVER_TOKEN")
            if not pushover_user:
                missing_keys.append("PUSHOVER_USER")
            if not email_sender:
                missing_keys.append("EMAIL_SENDER")
            if not email_recipient:
                missing_keys.append("EMAIL_RECIPIENT")
            
            if missing_keys:
                raise ValueError(f"Missing keys in the JSON file: {', '.join(missing_keys)}")

            return api_key, api_secret, sendgrid_api_key, pushover_token, pushover_user, email_sender, email_recipient
    except FileNotFoundError:
        raise FileNotFoundError(f"The specified JSON file '{CONFIG_FILE}' was not found.")
    except json.JSONDecodeError:
        raise ValueError(f"The JSON file '{CONFIG_FILE}' is not properly formatted.")




# Load API_KEY and API_SECRET from the JSON file
API_KEY, API_SECRET, SENDGRID_API_KEY, PUSHOVER_TOKEN, PUSHOVER_USER, EMAIL_SENDER, EMAIL_RECIPIENT = load_keys()



# Notifications
def send_push_notification(message, log_to_file=True):
    """
    Στέλνει push notification μέσω Pushover.

    Args:
        message (str): Το μήνυμα που θα σταλεί.
        log_to_file (bool): Αν είναι True, καταγράφει το μήνυμα στο log αρχείο.
    """
    if not ENABLE_PUSH_NOTIFICATIONS:
        if log_to_file:
            logging.info("Push notifications are paused. Notification was not sent.")
        return

    try:
        # Αποστολή push notification μέσω Pushover
        po = pushover.Client(user_key=PUSHOVER_USER, api_token=PUSHOVER_TOKEN)
        po.send_message(message, title="DCA Bot Alert")
        
        if log_to_file:
            logging.info("Push notification sent successfully!")
    except Exception as e:
        if log_to_file:
            logging.error(f"Error sending push notification: {e}")

# Initialize exchange
def initialize_exchange():
    try:
        # Φόρτωση των απαραίτητων API κλειδιών
        keys = load_keys()
        api_key, api_secret = keys[0], keys[1]  # Μόνο τα API_KEY και API_SECRET χρειάζονται για το exchange

        # Αρχικοποίηση του exchange
        exchange = getattr(ccxt, EXCHANGE_NAME)({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
        })
        exchange.set_sandbox_mode(False)  # Απενεργοποίηση sandbox mode
        exchange.load_markets()  # Φόρτωση αγορών

        logging.info(f"Connected to {EXCHANGE_NAME.upper()} - Markets loaded: {len(exchange.markets)}")
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



# Calculate technical indicators for initial buy on downtrend
def fetch_ohlcv(exchange, symbol='BTC/USDT', timeframe='1h', limit=100):
    """
    Ανάκτηση ιστορικών δεδομένων OHLCV από το exchange.
    :param exchange: ccxt exchange instance
    :param symbol: Ζεύγος νομισμάτων (π.χ., 'BTC/USDT')
    :param timeframe: Χρονικό διάστημα (π.χ., '1h', '1d')
    :param limit: Αριθμός κεριών
    :return: DataFrame με στήλες ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    """
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    logging.info(f"Fetched OHLCV data for symbol: {symbol}, timeframe: {timeframe}, limit: {limit}")

    return df




def ema(data, period):
    """
    Υπολογισμός Exponential Moving Average (EMA).
    :param data: Series από τιμές (π.χ. τιμές κλεισίματος)
    :param period: Περίοδος EMA
    :return: Series με τις τιμές EMA
    """
    
    logging.info(f"Calculated EMA for period: {period}, last value: {data.iloc[-1]:.4f}")

    return data.ewm(span=period, adjust=False).mean()




def rsi(data, period=14):
    """
    Υπολογισμός RSI.
    :param data: Series από τιμές (π.χ. τιμές κλεισίματος)
    :param period: Περίοδος RSI
    :return: Series με τις τιμές RSI
    """
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss

    # Υπολογισμός RSI
    result = 100 - (100 / (1 + rs))

    # Logging μόνο του τελικού αποτελέσματος
    if not result.empty:
        logging.info(f"Calculated RSI for period: {period}, last value: {result.iloc[-1]:.4f}")
    else:
        logging.warning(f"RSI calculation returned an empty result for period: {period}")

    return result





def price_dropped_percent(current_price, recent_high):
    """
    Υπολογισμός πτώσης τιμής ως ποσοστό από το πρόσφατο υψηλό και έλεγχος αν ξεπερνά το όριο.
    :param current_price: Τρέχουσα τιμή
    :param recent_high: Πρόσφατο υψηλό
    :return: Tuple (price_drop_percentage, meets_threshold)
    """
    if recent_high == 0:  # Αποφυγή διαίρεσης με το μηδέν
        logging.warning("Recent high is zero. Cannot calculate price drop percentage.")
        return 0, False

    # Υπολογισμός πτώσης τιμής
    price_drop = ((recent_high - current_price) / recent_high) * 100

    # Έλεγχος αν πληροί το στατικό κατώφλι
    meets_threshold = price_drop >= PERCENTAGE_DROP

    # Logging
    if meets_threshold:
        logging.info(f"Price dropped {price_drop:.2f}% from recent high, meeting the threshold of {PERCENTAGE_DROP}%.")
    else:
        logging.info(f"Price dropped {price_drop:.2f}% from recent high, below the threshold of {PERCENTAGE_DROP}%.")

    return price_drop, meets_threshold






def find_support_levels(data, window=5):
    """
    Εντοπισμός επιπέδων υποστήριξης βασισμένος σε τοπικά ελάχιστα.
    :param data: Series με τιμές (π.χ. low)
    :param window: Μέγεθος παραθύρου για τοπικά ελάχιστα
    :return: Λίστα με επίπεδα υποστήριξης
    """
    support_levels = data[(data.shift(1) > data) & (data.shift(-1) > data)].rolling(window).min().dropna().tolist()
    
    
    return sorted(set(support_levels))




def near_support_level(current_price, support_levels, tolerance=50):
    """
    Ελέγχει αν η τρέχουσα τιμή είναι κοντά σε επίπεδο υποστήριξης.
    :param current_price: Τρέχουσα τιμή
    :param support_levels: Λίστα από επίπεδα υποστήριξης
    :param tolerance: Ανοχή (σε απόλυτη τιμή)
    :return: True αν η τιμή είναι κοντά σε κάποιο επίπεδο υποστήριξης
    """
    for support in support_levels:
        if abs(current_price - support) <= tolerance:
            logging.info(
                f"Current price {current_price:.2f} is near support level {support:.2f} within tolerance {tolerance}."
            )
            return True
    logging.info(f"Current price {current_price:.2f} is not near any support level within tolerance {tolerance}.")
    return False




def wait_for_next_signal(interval=120):
    """
    Περιμένει για το επόμενο σήμα.
    :param interval: Διάστημα χρόνου σε δευτερόλεπτα (default: 120)
    """
    logging.info(f"Waiting for {interval} seconds for the next signal...")
    time.sleep(interval)






# Main trading function
def run_dca_bot():    
    logging.info(f"{'=' * 20} Starting DCA Trading bot {'=' * 20}")
    
    # Initialize Exchange and load orders
    exchange = initialize_exchange()
    orders = load_or_initialize_orders()
    logging.info(f"Loaded {len(orders)} existing order(s).")
    
    # Fetch the initial price
    last_price = float(exchange.fetch_ticker(PAIR)['last'])
    logging.debug(f"Starting price: {last_price}")    

    try:
        while True:
            iteration_start = time.time()
            

            print()            
            logging.info(f"Starting a new loop iteration for {PAIR}")
            

            
            # Fetch the current price
            current_price = float(exchange.fetch_ticker(PAIR)['last'])
            logging.info(f"Current price: {current_price} {CRYPTO_CURRENCY}")
            

            # Logging the strategy parameters
            logging.info(
                f"Strategy parameters: PERCENTAGE_DROP = {PERCENTAGE_DROP}%, PERCENTAGE_RISE = {PERCENTAGE_RISE}%."
            )


            # Υπολογισμός επόμενης τιμής αγοράς
            if orders:
                lowest_order_price = min(map(float, orders.keys()))
                next_buy_price = lowest_order_price * (1 - PERCENTAGE_DROP / 100)
                logging.info(f"Next buy will occur if the price drops to: {next_buy_price:.4f} {CRYPTO_CURRENCY} or lower.")            
            
            

            # Log details of existing orders            
            if orders:
                print()
                logging.info(f"{'=' * 20} Existing Orders in {CRYPTO_CURRENCY} {'=' * 20}")
                logging.info(f"{'Order ID':<15} {'Amount':<10} {'Bought At':<10} {'Sell At':<10} {'Days Open':<10} {'Distance to Sell':<10}")
                total_amount = 0
                total_cost = 0
                
                for price, order in orders.items():
                    metrics = calculate_metrics(order, current_price)
                    logging.info(f"{order['id']:<15} {order['amount']:<10.2f} {order['price']:<10.4f} {metrics['sell_threshold']:<10.4f} {metrics['days_open']:<10} {metrics['distance_to_sell']:<10.4f}")
                    total_amount += order['amount']
                    total_cost += order['amount'] * order['price']
                    

                # Υπολογισμός μέσου όρου αγοράς
                if total_amount > 0:
                    average_price = total_cost / total_amount
                    logging.info(f"Total quantity: {total_amount:.2f} {CRYPTO_SYMBOL}, Average Buy: {average_price:.4f} {CRYPTO_CURRENCY}")

                      
            
            else:
                logging.info("No existing orders.")
                
            

            # Initial buying logic if there are no orders
            if not orders:
                try:
                    # Fetch historical data and calculate indicators
                    df = fetch_ohlcv(exchange, symbol=PAIR, timeframe='1h', limit=100)
                    df['ema_fast'] = ema(df['close'], period=9)
                    df['ema_slow'] = ema(df['close'], period=21)
                    df['rsi'] = rsi(df['close'], period=14)
                    support_levels = find_support_levels(df['low'], window=5)

                    # Current price and conditions
                    current_price = df['close'].iloc[-1]
                    recent_high = df['close'].rolling(window=20).max().iloc[-1]

                    # Check price drop and threshold
                    price_drop, meets_threshold = price_dropped_percent(current_price, recent_high)

                    # Logging key metrics
                    logging.info(
                        f"Current price: {current_price:.4f}, Recent high: {recent_high:.4f}, "
                        f"Price drop: {price_drop:.4f}%, Threshold: {PERCENTAGE_DROP:.2f}%."
                    )
                    logging.info(f"Identified support levels: {support_levels}")

                    
                    
                    # Check conditions for initial buy
                    if meets_threshold and near_support_level(current_price, support_levels, tolerance=50):
                        
                        
                        # Execute market buy
                        order = exchange.create_market_buy_order(PAIR, TRADE_AMOUNT)

                        logging.info(
                            f"Bought {TRADE_AMOUNT} {CRYPTO_SYMBOL} at {current_price:.4f} {CRYPTO_CURRENCY}. "
                            f"Reason: Suitable conditions met (price drop and near support)."
                        )

                        send_push_notification(
                            f"Bought {TRADE_AMOUNT} {CRYPTO_SYMBOL} at {current_price:.4f} {CRYPTO_CURRENCY}. "
                            f"Reason: Suitable conditions met (price drop and near support)."
                        )

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
                        save_orders(orders)
                    
                    
                    
                    else:
                        logging.info(
                            "No suitable conditions for initial buy. Waiting for next signal."
                        )

                except ccxt.BaseError as api_error:
                    logging.error(f"Error placing buy order: {api_error}")
                    startBot = False
                    return


                    
                    
                    
            # Buy more if price drops below percentage_drop
            if orders and current_price <= min(map(float, orders.keys())) * (1 - PERCENTAGE_DROP / 100):
                
                # Buy Crypto
                try:
                    order = exchange.create_market_buy_order(PAIR, TRADE_AMOUNT)
                                       
                    
                    lowest_order_price = min(map(float, orders.keys()))
                    logging.info(
                        f"Bought {TRADE_AMOUNT} {CRYPTO_SYMBOL} at {current_price:.4f} {CRYPTO_CURRENCY}. "
                        f"Current price {current_price:.4f} {CRYPTO_CURRENCY} dropped by more than {PERCENTAGE_DROP}% "
                        f"from the lowest order price {lowest_order_price:.4f}."
                    )

                    # Ενημέρωση χρήστη για αγορά με Push msg
                    send_push_notification(
                        f"Bought {TRADE_AMOUNT} {CRYPTO_SYMBOL} at {current_price:.4f} {CRYPTO_CURRENCY}. "
                        f"Reason: Current price {current_price:.4f} {CRYPTO_CURRENCY} dropped by more than {PERCENTAGE_DROP}% "
                        f"from the lowest order price {lowest_order_price:.4f}."
                    )

                    logging.info(
                        f"Total Orders: {len(orders) + 1}. Current Portfolio Strategy: Adding to position to reduce cost average."
                    )

                    
                    print()
                                        
                    
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
                    save_orders(orders)
                    
                    
                except ccxt.BaseError as api_error:
                    logging.error(f"Error placing buy order: {api_error}")
                    startBot = False
                    return                    
                    
                    
                    
            
            # Sell evaluation
            if orders:
                print()
                logging.info(f"{'=' * 20} Sell Threshold Evaluation in {CRYPTO_CURRENCY} {'=' * 20}")
                for price, order in list(orders.items()):  # Copy to avoid modifying during iteration
                    sell_threshold = float(price) * (1 + PERCENTAGE_RISE / 100)
                    
                    #logging.info(f"Calculated sell threshold: {sell_threshold:.4f} {CRYPTO_CURRENCY} for order price: {price} {CRYPTO_CURRENCY}")
                    

                    if current_price >= sell_threshold:
                        # Sell BTC
                        sell_order = exchange.create_market_sell_order(PAIR, order['amount'])
                        logging.info(f"Order ID: {order['id']} | Sell Threshold: {sell_threshold:.4f} | Current Price: {current_price:.4f} -> Selling!")
                        
                        # Στέλνουμε push notification
                        rounded_price = round(current_price, 4)  # Στρογγυλοποίηση για να ταιριάζει με τη μορφή στο push
                        send_push_notification(f"Sale order of {order['amount']} {PAIR} was executed at {rounded_price:.4f} with order no: {order['id']}")
                                           

                        # Remove the order from the list
                        del orders[price]
                        save_orders(orders)
                        
                    else:
                        #logging.info(f"Current price {current_price:.4f} {CRYPTO_CURRENCY} did not reach the sell threshold {sell_threshold:.4f} {CRYPTO_CURRENCY}.")
                        logging.info(f"Order ID: {order['id']} | Sell Threshold: {sell_threshold:.4f} | Current Price: {current_price:.4f} -> Not selling.")
                    
                      
            
            
            # Μετά την ολοκλήρωση του iteration
            iteration_end = time.time()
            logging.info(f"Loop iteration completed in {iteration_end - iteration_start:.2f} seconds.")

            time.sleep(60)



    except KeyboardInterrupt:
        logging.info("Bot operation was interrupted by user.")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        send_push_notification(f"ALERT: Bot is stopped. An error occurred: {e}")

if __name__ == "__main__":
    run_dca_bot()
