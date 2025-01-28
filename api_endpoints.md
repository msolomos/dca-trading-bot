# DCA Bot API Endpoints

## Overview
This Flask-based API provides endpoints to interact with and monitor the DCA Trading Bot. It enables seamless integration with tools like Excel for live data visualization and management of bot activities. The API facilitates access to current prices, active orders, profit details, and sell threshold evaluations.

---

## Features

### 1. **Real-Time Data**
- Fetch the latest cryptocurrency prices from the configured exchange.
- Retrieve detailed information about active orders and trading metrics.

### 2. **Comprehensive Order Insights**
- View active orders with calculated metrics such as:
  - Sell thresholds
  - Days open
  - Distance to the sell price
  - Formatted timestamps for better readability

### 3. **Sell Threshold Evaluation**
- Check whether the current price has reached the sell threshold for active orders.
- Evaluate the status of each order (e.g., "Selling" or "Not Selling").

### 4. **Excel Integration**
- Designed for seamless integration with Excel via HTTP GET requests.
- Returns JSON responses, making it easy to parse and use in external tools.

---

## Endpoints

### 1. **Favicon**
- **Endpoint:** `/favicon.ico`
- **Method:** GET
- **Description:** Returns an empty response to suppress unnecessary browser requests.

### 2. **Current Price**
- **Endpoint:** `/DCA/current_price`
- **Method:** GET
- **Description:** Fetches the current price of the configured cryptocurrency pair, along with meta and profit data.
- **Response Format:**
  ```json
  {
    "pair": "BTC/USDT",
    "current_price": 27650.55,
    "meta": {
      "SALES": 5
    },
    "profit": 102.75
  }
  ```

### 3. **Existing Orders**
- **Endpoint:** `/DCA/existing_orders`
- **Method:** GET
- **Description:** Provides details of all active orders, including:
  - Order ID
  - Amount
  - Bought price
  - Sell threshold
  - Days open
  - Distance to sell price
  - Formatted date and time of the order
- **Response Format:**
  ```json
  [
    {
      "order_id": "12345",
      "amount": 0.05,
      "bought_at": 27000,
      "sell_at": 27540,
      "days_open": 3,
      "distance": 90,
      "datetime": "25/01/2025 15:30"
    }
  ]
  ```

### 4. **Sell Threshold Evaluation**
- **Endpoint:** `/DCA/sell_threshold_eval`
- **Method:** GET
- **Description:** Evaluates if the sell threshold for each active order has been reached, returning the status of each order.
- **Response Format:**
  ```json
  [
    {
      "order_id": "12345",
      "sell_threshold": 27540,
      "current_price": 27600,
      "status": "Selling"
    }
  ]
  ```

---

## Configuration

### Files
1. **`config.json`**
   - Contains exchange API keys, trading pair, and other bot settings.
   - Example:
     ```json
     {
       "API_KEY": "your_api_key",
       "API_SECRET": "your_api_secret",
       "TRADE_CONFIG": {
         "PAIR": "BTC/USDT",
         "EXCHANGE_NAME": "binance"
       }
     }
     ```
2. **`orders.json`**
   - Stores active orders and metadata, updated dynamically by the bot.

---

## Usage

### 1. **Setup**
1. Clone the repository.
2. Install the required dependencies:
   ```bash
   pip install flask ccxt
   ```
3. Place your `config.json` and `orders.json` files in the configured directory.

### 2. **Run the API**
Start the Flask server:
```bash
python api_endpoints.py
```
The API will run on `http://0.0.0.0:5014` by default.

### 3. **Integrate with Excel**
1. Use Excel's `WEBSERVICE` function to fetch data:
   - Example:
     ```excel
     =WEBSERVICE("http://your_server_ip:5014/DCA/current_price")
     ```
2. Parse JSON responses using Excel-compatible tools for visualization and analysis.

---

## File Structure
```
.
├── api_endpoints.py        # API script
├── config.json             # Configuration file
├── orders.json             # Active orders data
└── requirements.txt        # Python dependencies
```

---

## Notes
- Ensure your API keys are secured and not exposed in public repositories.
- Verify that your Flask server is accessible from the Excel environment.
- Use HTTPS for secure connections in production.

---

## Contributions
This is an evolving project, and contributions are welcome! Whether you have suggestions for new endpoints, optimizations, or additional features, your feedback is invaluable. Feel free to submit issues or pull requests to help improve this API.

---

## Disclaimer
This API is provided for educational purposes only. Use it at your own risk.
