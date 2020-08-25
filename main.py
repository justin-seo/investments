import copy
import gspread
import os
import requests
from colorama import Fore, Back, Style
from oauth2client.service_account import ServiceAccountCredentials
from pprint import pprint
from prettytable import PrettyTable

# Colors to print with
R = "\033[0;31;40m"  # RED
G = "\033[0;32;40m"  # GREEN
N = "\033[0m"  # Reset

stockAPIToken = (os.environ["FINNHUB_TOKEN"])

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)

client = gspread.authorize(credentials)

sheet = client.open("Investments").sheet1

data = sheet.get_all_records()  # Assume rows are from oldest to newest.

stocks_total_profit_loss = 0.00
stocks = {}  # Initialize dictionary of different investment types.


def calculate_percentage(current_value, initial_value):
    if current_value > 0.00:
        percentage = round((((current_value / initial_value) - 1) * 100), 2)
        if percentage > 0.00:
            percentage_output = "{:s}+{:s}%{:s}".format(G, str(percentage), N)
        else:
            percentage_output = "{:s}{:s}%{:s}".format(R, str(percentage), N)
    else:
        percentage_output = "{:s}+0.00%{:s}".format(N, N)
    return percentage_output


def process_orders(ticker_symbol, current_price):
    buy_history_copy = copy.deepcopy(stocks[ticker_symbol]["buyHistory"])
    sell_history_copy = copy.deepcopy(stocks[ticker_symbol]["sellHistory"])
    full_name = stocks[ticker_symbol]["fullName"]

    total_sold = 0  # Keep track of how many were sold.
    total_remaining = 0  # Keep track of how many are left.

    total_sold_value = 0.00  # Keep track of the value after being sold.
    total_sold_value_by_initial_cost = 0.00  # Keep track of the value it was bought at.

    total_remaining_value = 0.00  # Keep track of total value by current price.
    total_remaining_value_by_initial_cost = 0.00  # Keep track of total value by buy in price.

    for sell_index in range(len(sell_history_copy)):
        sell_order = sell_history_copy[sell_index]
        sell_quantity = sell_order["quantity"]  # Quantity of a sell order.
        sell_price = sell_order["price"]  # Price of a sell order.
        if sell_quantity > 0:  # Iterate buy_history_copy if current sell order has quantity.
            for buy_index in range(len(buy_history_copy)):
                buy_order = buy_history_copy[buy_index]
                buy_quantity = buy_order["quantity"]  # Quantity of a buy order.
                buy_price = buy_order["price"]  # Price of a buy order.
                if buy_quantity != 0:  # Continue if current buy order has quantity.
                    if buy_quantity >= sell_quantity:  # Current buy order >= current sell order quantity.
                        total_sold_value += (sell_price * sell_quantity)  # Add realized gain
                        total_sold_value_by_initial_cost += (buy_price * sell_quantity)  # Add initial cost.
                        total_sold += sell_quantity
                        buy_quantity -= sell_quantity
                        sell_quantity = 0
                    else:  # Current buy order < current sell order quantity.
                        total_sold_value += (sell_price * buy_quantity)  # Add realized gain
                        total_sold_value_by_initial_cost += (buy_price * buy_quantity)  # Add initial cost.
                        total_sold += buy_quantity
                        buy_quantity = 0
                        sell_quantity -= buy_quantity
                buy_history_copy[buy_index]["quantity"] = buy_quantity  # Update quantity of current buy order.
        sell_history_copy[sell_index]["quantity"] = sell_quantity  # Update quantity of current buy order.

    # Loop through buy history after updating quantity by running through sell history.
    for buy_index in range(len(buy_history_copy)):
        buy_order = buy_history_copy[buy_index]
        buy_quantity = buy_order["quantity"]  # Quantity of a buy order.
        buy_price = buy_order["price"]  # Price of a buy order.

        total_remaining_value += (current_price * buy_quantity)
        total_remaining_value_by_initial_cost += (buy_price * buy_quantity)
        total_remaining += buy_quantity

    realized_gain_loss_cell = calculate_percentage(total_sold_value, total_sold_value_by_initial_cost)
    unrealized_gain_loss_cell = calculate_percentage(total_remaining_value, total_remaining_value_by_initial_cost)

    total_realized_unrealized = round((total_sold_value - total_sold_value_by_initial_cost) + \
                                      (total_remaining_value - total_remaining_value_by_initial_cost), 2)
    if total_realized_unrealized >= 0.00:
        current_profit_loss_cell = "{:s}+${:s}{:s}".format(G, str(total_realized_unrealized), N)
    else:
        current_profit_loss_cell = "{:s}${:s}{:s}".format(R, str(total_realized_unrealized), N)

    global stocks_total_profit_loss  # Keep track of total profit/loss
    stocks_total_profit_loss += total_realized_unrealized

    average_price = round((total_remaining_value_by_initial_cost / total_remaining), 2)
    if average_price <= current_price:
        average_price_cell = "{:s}${:s}{:s}".format(G, str(average_price), N)
    else:
        average_price_cell = "{:s}${:s}{:s}".format(R, str(average_price), N)

    current_price_cell = "{:s}${:s}{:s}".format(N, str(current_price), N)

    return [ticker_symbol, full_name, total_sold, realized_gain_loss_cell, total_remaining, unrealized_gain_loss_cell,
            current_profit_loss_cell, current_price_cell, average_price_cell]


for row in data:
    ticker = row["Ticker"]
    buyOrSell = row["Buy/Sell"]
    fullName = row["Investment"]

    quantity = row["Quantity"]
    buyOrSellPrice = row["Buy/Sell Price"]
    orderDate = row["Order Date"]
    newOrder = {"date": orderDate, "price": buyOrSellPrice, "quantity": quantity}

    if ticker in stocks.keys():  # Stock already in dictionary
        if buyOrSell == "Buy":
            buyHistory = stocks[ticker]["buyHistory"]
            buyHistory.append(newOrder)  # Append buy order to buyHistory
            stocks[ticker]["buyHistory"] = buyHistory
        elif buyOrSell == "Sell":
            sellHistory = stocks[ticker]["sellHistory"]
            sellHistory.append(newOrder)  # Append sell order to sellHistory
            stocks[ticker]["sellHistory"] = sellHistory
    else:  # Stock not in dictionary.
        if buyOrSell == "Buy":
            stocks[ticker] = {"fullName": fullName, "sellHistory": [],
                              "buyHistory": [{"date": orderDate, "price": buyOrSellPrice, "quantity": quantity}]}
        else:
            print(Fore.RED + "First time seeing {:s} and it's not a buy order.".format(ticker))

pprint(stocks)

stock_table = PrettyTable(["Ticker", "Name", "Sold", "Realized Gain/Loss (%)", "Remaining", "Unrealized Gain/Loss (%)",
                           "Current Profit/Loss ($)", "Current Price ($)", "Average Price ($)"])
for ticker in stocks.keys():
    url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={stockAPIToken}"
    currentPrice = requests.get(url).json()["c"]
    stock_table.add_row(process_orders(ticker, currentPrice))

print(stock_table)

total_table = PrettyTable(["Total Profit/Loss ($)"])
stocks_total_profit_loss = round(stocks_total_profit_loss, 2)
if stocks_total_profit_loss >= 0.00:
    average_price_cell = ["{:s}+${:s}{:s}".format(G, str(stocks_total_profit_loss), N)]
else:
    average_price_cell = ["{:s}${:s}{:s}".format(R, str(stocks_total_profit_loss), N)]
total_table.add_row(average_price_cell)

print(total_table)
