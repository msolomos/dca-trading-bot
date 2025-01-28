# DCA Trading Bot for Bitcoin

## Overview
This DCA Trading Bot is a Python-based tool designed to execute Dollar-Cost Averaging (DCA) strategies for trading Bitcoin or other cryptocurrencies. The bot integrates with multiple exchanges via the CCXT library, supports advanced configurations, and provides detailed logging and notification mechanisms for efficient and automated trading.

---

## Features

### 1. **Trading Strategy**
- Implements a Dollar-Cost Averaging strategy:
  - Automatically buys more cryptocurrency when prices drop by a configured percentage.
  - Sells holdings when the price rises to a defined threshold, locking in profits.
- Calculates metrics such as average buy price, sell thresholds, and potential profits for every order.

### 2. **Exchange Integration**
- Supports multiple exchanges using the CCXT library.
- Configurable to connect to exchanges like Binance, Coinbase, etc.

### 3. **Technical Analysis**
- Utilizes indicators such as:
  - **Exponential Moving Average (EMA)**
  - **Relative Strength Index (RSI)**
  - Support level detection
- Ensures informed trading decisions based on historical and real-time data.

### 4. **Order Management**
- Maintains active orders in a JSON file for transparency and persistence.
- Tracks order profitability and the number of completed sales.
- Dynamically adjusts the next buy and sell thresholds.

### 5. **Notifications**
- Push notifications via Pushover.
- Email notifications via SendGrid.

### 6. **Logging**
- Detailed logs for every bot operation, including errors and trading activity.
- Logs are written to both a file and the console for easy monitoring.

---

## Configuration
The bot uses a `config.json` file to load all necessary settings. Below are the configurable parameters:

### API Keys
- `API_KEY`: Exchange API key.
- `API_SECRET`: Exchange API secret.

### Notification Settings
- `SENDGRID_API_KEY`: API key for email notifications via SendGrid.
- `PUSHOVER_TOKEN`: Token for Pushover notifications.
- `PUSHOVER_USER`: User key for Pushover notifications.

### Trade Configuration
- `PAIR`: Cryptocurrency pair (e.g., `BTC/USDT`).
- `CRYPTO_SYMBOL`: The symbol of the cryptocurrency (e.g., `BTC`).
- `CRYPTO_CURRENCY`: The base currency (e.g., `USDT`).
- `EXCHANGE_NAME`: Name of the exchange (e.g., `binance`).
- `PERCENTAGE_DROP`: Percentage drop in price to trigger a buy order.
- `PERCENTAGE_RISE`: Percentage rise in price to trigger a sell order.
- `TRADE_AMOUNT`: Amount to trade per order.
- `MAX_ORDERS`: Maximum number of active orders at any time.

---

## Usage

### 1. **Setup**
1. Clone the repository.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Place your `config.json` file in the root directory.

### 2. **Run the Bot**
Run the bot with the following command:
```bash
python dca_bot.py
```

### 3. **Logging and Monitoring**
- Logs are saved to `dca_bot.log` in the `/opt/python/dca-bot-bitcoin/` directory.
- Monitor notifications for updates on trades and errors.

---

## Key Functions

### Initialization
- `initialize_exchange()`: Sets up the exchange connection.
- `load_keys()`: Loads API credentials and configurations from `config.json`.
- `load_or_initialize_orders()`: Reads or creates the orders file.

### Technical Analysis
- `fetch_ohlcv()`: Retrieves historical market data.
- `ema(data, period)`: Calculates the Exponential Moving Average.
- `rsi(data, period)`: Calculates the Relative Strength Index.
- `find_support_levels(data, window)`: Identifies support levels.

### Trading Logic
- **Buying:** Buys cryptocurrency when the price drops below a certain threshold.
- **Selling:** Sells cryptocurrency when the price rises above a defined threshold.
- **Metrics Calculation:** Calculates sell thresholds, profit, and distance to sell for each order.

### Notifications
- `send_push_notification(message)`: Sends push notifications.

---

## File Structure
```
.
├── dca_bot.py              # Main bot script
├── config.json             # Configuration file
├── orders.json             # Stores active orders and meta data
├── requirements.txt        # Python dependencies
└── dca_bot.log             # Log file
```

---

## Requirements
- Python 3.8+
- Libraries:
  - ccxt
  - pandas
  - pushover
  - logging
  - json

Install dependencies with:
```bash
pip install -r requirements.txt
```

---

## Notes
- Ensure your API keys are secured and not exposed in public repositories.
- Backtest the bot with historical data before running it with real funds.
- Monitor the bot regularly to ensure proper operation.

---

## License
This project is open-source and available under the [MIT License](LICENSE).

---

## Contributions
Contributions are welcome! This is my first attempt at building a project with Python, and I would greatly appreciate any help, feedback, or suggestions to improve the bot. Whether it's optimizing the code, adding new features, or simply pointing out areas of improvement, your input is invaluable. Feel free to submit issues or pull requests to make this project even better.

---

## Disclaimer
This bot is provided for educational purposes only. Use it at your own risk. The creator is not responsible for any financial losses incurred.

