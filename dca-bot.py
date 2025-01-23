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

# Διαδρομές αρχείων 
ORDERS_FILE = "/opt/python/dca-bot-bitcoin/orders.json"
CONFIG_FILE = "/opt/python/dca-bot-bitcoin/config.json"

# Παράμετροι Αποστολής E-mail
ENABLE_EMAIL_NOTIFICATIONS = True
ENABLE_PUSH_NOTIFICATIONS = True

# Άλλες μεταβλητές αρχικοποίησης
startBot = True


# Load Keys from external file
def load_keys():
    """Load API credentials, notification settings, and trade configuration from a JSON file."""
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

            # Ρυθμίσεις για το Trade Configuration
            trade_config = keys.get("TRADE_CONFIG", {})
            pair = trade_config.get("PAIR")
            crypto_symbol = trade_config.get("CRYPTO_SYMBOL")
            crypto_currency = trade_config.get("CRYPTO_CURRENCY")
            exchange_name = trade_config.get("EXCHANGE_NAME")
            percentage_drop = trade_config.get("PERCENTAGE_DROP")
            percentage_rise = trade_config.get("PERCENTAGE_RISE")
            trade_amount = trade_config.get("TRADE_AMOUNT")
            
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
            if not pair or not crypto_symbol or not crypto_currency or not exchange_name:
                missing_keys.extend(["PAIR", "CRYPTO_SYMBOL", "CRYPTO_CURRENCY", "EXCHANGE_NAME"])
            if percentage_drop is None or percentage_rise is None or trade_amount is None:
                missing_keys.extend(["PERCENTAGE_DROP", "PERCENTAGE_RISE", "TRADE_AMOUNT"])
            
            if missing_keys:
                raise ValueError(f"Missing keys in the JSON file: {', '.join(missing_keys)}")

            return (api_key, api_secret, sendgrid_api_key, pushover_token, pushover_user, email_sender, email_recipient,
                    pair, crypto_symbol, crypto_currency, exchange_name, percentage_drop, percentage_rise, trade_amount)
    except FileNotFoundError:
        raise FileNotFoundError(f"The specified JSON file '{CONFIG_FILE}' was not found.")
    except json.JSONDecodeError:
        raise ValueError(f"The JSON file '{CONFIG_FILE}' is not properly formatted.")



# Load configuration from the JSON file
(API_KEY, API_SECRET, SENDGRID_API_KEY, PUSHOVER_TOKEN, PUSHOVER_USER, EMAIL_SENDER, EMAIL_RECIPIENT,
 PAIR, CRYPTO_SYMBOL, CRYPTO_CURRENCY, EXCHANGE_NAME, PERCENTAGE_DROP, PERCENTAGE_RISE, TRADE_AMOUNT) = load_keys()




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
        api_key, api_secret = keys[0], keys[1]

        # Δημιουργία βάσει του EXCHANGE_NAME
        exchange_class = getattr(ccxt, EXCHANGE_NAME)
        exchange_params = {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
        }

        # Ειδικές ρυθμίσεις για συγκεκριμένα ανταλλακτήρια
        if EXCHANGE_NAME == "coinbase":
            exchange_params["options"] = {
                "createMarketBuyOrderRequiresPrice": False
            }

        # Αρχικοποίηση του exchange
        exchange = exchange_class(exchange_params)
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
            orders_data = json.load(f)
            
            # Αρχικοποίηση των πεδίων αν δεν υπάρχουν
            if "ORDERS" not in orders_data:
                orders_data["ORDERS"] = {}
            if "META" not in orders_data:
                orders_data["META"] = {"PROFIT": 0.0, "SALES": 0}
            
            return orders_data
    except (FileNotFoundError, ValueError):
        logging.warning("Orders file not found or invalid. Initializing new data.")
        return {
            "ORDERS": {},
            "META": {
                "PROFIT": 0.0,
                "SALES": 0
            }
        }



# Save orders
def save_orders(orders, save_meta=True, save_orders=True):
    try:
        # Φορτώνουμε το τρέχον περιεχόμενο του αρχείου
        try:
            with open(ORDERS_FILE, 'r') as f:
                existing_data = json.load(f)
        except (FileNotFoundError, ValueError):
            existing_data = {}

        # Ενημερώνουμε μόνο τα απαραίτητα μέρη
        if save_orders:
            existing_data["ORDERS"] = orders.get("ORDERS", {})
        if save_meta:
            existing_data["META"] = orders.get("META", {"PROFIT": 0.0, "SALES": 0})

        # Αποθηκεύουμε τα δεδομένα πίσω στο αρχείο
        with open(ORDERS_FILE, 'w') as f:
            json.dump(existing_data, f, indent=4)
    except Exception as e:
        logging.error(f"Failed to save orders: {e}")




# Calculate metrics
def calculate_metrics(order, current_price):
    sell_threshold = float(order['price']) * (1 + PERCENTAGE_RISE / 100)
    
    # Default τιμή για days_open αν δεν υπάρχει ημερομηνία
    if order.get('datetime') is not None:
        try:
            order_datetime = datetime.strptime(order['datetime'], "%Y-%m-%dT%H:%M:%S.%fZ")
            days_open = (datetime.now() - order_datetime).days
        except ValueError:
            days_open = 0  # Εναλλακτικά: πέταξε εξαίρεση ή log το σφάλμα
    else:
        days_open = 0

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
    # Υλοποίηση της κύριας λογικής του bot
   
    logging.info(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    logging.info(f"Starting {PAIR} DCA Trading bot...")
    logging.info(f"Loaded configuration file from {CONFIG_FILE}.")
    
    iteration_start = time.time()    
    
    # Initialize Exchange and load orders
    exchange = initialize_exchange()
    orders = load_or_initialize_orders()
    meta = orders["META"]
       
    if "ORDERS" in orders and orders["ORDERS"]:
        logging.info(f"Loaded {len(orders['ORDERS'])} existing order(s).")
    
    else:
        logging.info("There are no existing orders.")
    
    
    profit = round(meta["PROFIT"], 2)  # Στρογγυλοποίηση στο δεύτερο δεκαδικό
    sales = meta["SALES"]
    
    logging.info(f"Total Profit Earned: {profit:.2f} {CRYPTO_CURRENCY}.")
    logging.info(f"Total Sales Completed: {sales} transactions.")   
    
    
    # Fetch the initial price
    last_price = float(exchange.fetch_ticker(PAIR)['last'])
    logging.debug(f"Starting price: {last_price}")    

    
    
    try:
              
        # Fetch the current price
        current_price = float(exchange.fetch_ticker(PAIR)['last'])
        logging.info(f"Current price: {current_price} {CRYPTO_CURRENCY}")
        

        # Logging the strategy parameters
        logging.info(
            f"Strategy parameters: PERCENTAGE_DROP = {PERCENTAGE_DROP}%, PERCENTAGE_RISE = {PERCENTAGE_RISE}%."
        )


        # Υπολογισμός επόμενης τιμής αγοράς & Log details of existing orders
        if "ORDERS" in orders and orders["ORDERS"]:
            lowest_order_price = min(map(float, orders["ORDERS"].keys()))
            next_buy_price = lowest_order_price * (1 - PERCENTAGE_DROP / 100)
            logging.info(f"Next buy will occur if the price drops to: {next_buy_price:.4f} {CRYPTO_CURRENCY} or lower.")
            
            print()
            
            logging.info(f"{'=' * 20} Existing Orders in {CRYPTO_CURRENCY} {'=' * 20}")
            logging.info(f"{'Order ID':<15} {'Amount':<10} {'Bought At':<10} {'Sell At':<10} {'Days Open':<10} {'Distance to Sell':<10}")
            total_amount = 0
            total_cost = 0

            for price, order in orders["ORDERS"].items():
                metrics = calculate_metrics(order, current_price)
                logging.info(f"{order['id']:<15} {order['amount']:<10.2f} {order['price']:<10.4f} {metrics['sell_threshold']:<10.4f} {metrics['days_open']:<10} {metrics['distance_to_sell']:<10.4f}")
                total_amount += order['amount']
                total_cost += order['amount'] * order['price']

            # Υπολογισμός μέσου όρου αγοράς
            if total_amount > 0:
                average_price = total_cost / total_amount
                logging.info(f"Total quantity: {total_amount:.2f} {CRYPTO_SYMBOL}, Average Buy: {average_price:.4f} {CRYPTO_CURRENCY}")

           
        

        # Initial buying logic if there are no orders
        if "ORDERS" not in orders or not orders["ORDERS"]:
            try:
                # Executing buy logic...
                logging.info(f"Executing buy logic for for {PAIR}...")
                
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

                    # Ενημέρωση και αποθήκευση του ORDERS
                    if "ORDERS" not in orders:
                        orders["ORDERS"] = {}
                    orders["ORDERS"][str(current_price)] = order_data
                    save_orders({"ORDERS": orders["ORDERS"]}, save_meta=False)

                else:
                    logging.info(
                        "No suitable conditions for initial buy. Waiting for next signal."
                    )

            except ccxt.BaseError as api_error:
                logging.error(f"Error placing buy order: {api_error}")
                startBot = False
                return



                
                
                
        # Buy more if price drops below percentage_drop
        if "ORDERS" in orders and orders["ORDERS"] and current_price <= min(map(float, orders["ORDERS"].keys())) * (1 - PERCENTAGE_DROP / 100):
            # Buy Crypto
            try:
                order = exchange.create_market_buy_order(PAIR, TRADE_AMOUNT)
                
                lowest_order_price = min(map(float, orders["ORDERS"].keys()))
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
                    f"Total Orders: {len(orders['ORDERS']) + 1}. Current Portfolio Strategy: Adding to position to reduce cost average."
                )

                # Καταγραφή της παραγγελίας
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

                # Ενημέρωση και αποθήκευση του ORDERS
                orders["ORDERS"][str(current_price)] = order_data
                save_orders({"ORDERS": orders["ORDERS"]}, save_meta=False)

            except ccxt.BaseError as api_error:
                logging.error(f"Error placing buy order: {api_error}")
                startBot = False
                return
                  
                
                
                
        
        # Sell evaluation
        if "ORDERS" in orders and orders["ORDERS"]:
            print()
            logging.info(f"{'=' * 20} Sell Threshold Evaluation in {CRYPTO_CURRENCY} {'=' * 20}")
            for price, order in list(orders["ORDERS"].items()):  # Copy to avoid modifying during iteration
                sell_threshold = float(price) * (1 + PERCENTAGE_RISE / 100)

                if current_price >= sell_threshold:
                    # Sell BTC
                    sell_order = exchange.create_market_sell_order(PAIR, order['amount'])
                    logging.info(f"Order ID: {order['id']} | Sell Threshold: {sell_threshold:.4f} | Current Price: {current_price:.4f} -> Selling!")

                    # Υπολογισμός κέρδους
                    buy_price = float(order['price'])  # Η τιμή αγοράς της θέσης
                    amount = float(order['amount'])   # Το ποσό του crypto που πουλιέται
                    sell_price = current_price        # Η τρέχουσα τιμή πώλησης

                    total_cost = buy_price * amount   # Συνολικό κόστος αγοράς
                    total_income = sell_price * amount  # Συνολικό εισόδημα από την πώληση
                    profit = total_income - total_cost  # Κέρδος

                    # Ενημέρωση του META
                    orders["META"]["PROFIT"] += profit  # Προσθήκη στο συνολικό κέρδος
                    orders["META"]["SALES"] += 1        # Αύξηση του αριθμού πωλήσεων

                    # Καταγραφή του κέρδους
                    logging.info(f"Profit for order ID {order['id']}: {profit:.4f} {CRYPTO_CURRENCY}. Total Profit: {orders['META']['PROFIT']:.4f}. Total Sales: {orders['META']['SALES']}.")
                    send_push_notification(
                        f"Sale executed for order ID {order['id']}. Sold {amount} {PAIR} at {sell_price:.4f}. "
                        f"Profit: {profit:.4f} {CRYPTO_CURRENCY}. Total Profit: {orders['META']['PROFIT']:.4f}. Total Sales: {orders['META']['SALES']}."
                    )

                    # Αφαίρεση της παραγγελίας
                    del orders["ORDERS"][price]

                    # Αποθήκευση του ORDERS και του META ξεχωριστά
                    save_orders({"ORDERS": orders["ORDERS"]}, save_meta=False)  # Αποθήκευση των παραγγελιών
                    save_orders({"META": orders["META"]}, save_orders=False)   # Αποθήκευση του META

                else:
                    logging.info(f"Order ID: {order['id']} | Sell Threshold: {sell_threshold:.4f} | Current Price: {current_price:.4f} -> Not selling.")

                
                         
        # Μετά την ολοκλήρωση του iteration
        iteration_end = time.time()
        logging.info(f"Loop iteration completed in {iteration_end - iteration_start:.2f} seconds.")




    except KeyboardInterrupt:
        logging.info("Bot operation was interrupted by user.")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        send_push_notification(f"ALERT: Bot is stopped. An error occurred: {e}")

if __name__ == "__main__":
    run_dca_bot()
