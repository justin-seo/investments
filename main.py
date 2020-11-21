import sys
import copy
import gspread
import os
import requests
from colorama import Fore, Back, Style
from oauth2client.service_account import ServiceAccountCredentials
from pprint import pprint
from prettytable import PrettyTable

# Colors to print with
R = "\033[0;31;40m"  # RED Color
G = "\033[0;32;40m"  # GREEN Color
N = "\033[0m"  # Reset Color

stockAPIToken = (os.environ["TD_TOKEN"])

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(credentials)

investments = {}  # Initialize dictionary of different investment types.
totalProfitLoss = 0.00
processedInvestmentOrders = ["", "", 0, 0.00, 0, 0.00, "", "", ""]
# +----------------------------------------------Stock Data----------------------------------------------+
stock_sheet = client.open("Investments").sheet1
stock_data = stock_sheet.get_all_records()  # Assume rows are from oldest to newest.
# +----------------------------------------------Stock Data----------------------------------------------+
# +----------------------------------------------Wheel Data----------------------------------------------+
# +----------------------------------------------Wheel Data----------------------------------------------+
wheel_sheet = client.open("Investments").worksheet("Wheel")
wheel_data = wheel_sheet.get_all_records()  # Assume rows are from oldest to newest.
# +----------------------------------------------Option Data---------------------------------------------+
option_sheet = client.open("Investments").worksheet("Options")
option_data = option_sheet.get_all_records()  # Assume rows are from oldest to newest.
# +----------------------------------------------Option Data---------------------------------------------+


# +-----------------------------------------------Function-----------------------------------------------+
def calculate_percentage(current_value, initial_value, investment_type):
    if current_value > 0.00:
        percentage = round((((current_value / initial_value) - 1) * 100), 2)
        if percentage > 0.00:
            percentage_output = "{:s}+{:s}%{:s}".format(G, str(percentage), N)
        else:
            percentage_output = "{:s}{:s}%{:s}".format(R, str(percentage), N)
    else:
        if investment_type == "stock" or initial_value == 0.00:
            percentage_output = "{:s}+0.00%{:s}".format(N, N)
        else:
            percentage_output = "{:s}-100.00%{:s}".format(R, N)
    return percentage_output


def calculate_total_table():
    stocks_total_profit_loss_rounded = round(totalProfitLoss, 2)
    if stocks_total_profit_loss_rounded >= 0.00:
        stocks_total_profit_loss_cell = ["{:s}+${:s}{:s}".format(G, str(stocks_total_profit_loss_rounded), N)]
    else:
        stocks_total_profit_loss_cell = ["{:s}${:s}{:s}".format(R, str(stocks_total_profit_loss_rounded), N)]
    return stocks_total_profit_loss_cell


def process_sheet(data, investment_type):
    for row in data:
        ticker_symbol = row["Ticker"]
        buy_or_sell = row["Buy/Sell"]
        full_name = row[investment_type]

        quantity = row["Quantity"]
        buy_or_sell_price = row["Buy/Sell Price"]
        order_date = row["Order Date"]
        new_order = {"date": order_date, "price": buy_or_sell_price, "quantity": quantity}

        if full_name in investments.keys():  # Stock already in dictionary
            if buy_or_sell == "Buy":
                buy_history = investments[full_name]["buyHistory"]
                buy_history.append(new_order)  # Append buy order to buyHistory
                investments[full_name]["buyHistory"] = buy_history
            elif buy_or_sell == "Sell":
                sell_history = investments[full_name]["sellHistory"]
                sell_history.append(new_order)  # Append sell order to sellHistory
                investments[full_name]["sellHistory"] = sell_history
        else:  # Stock not in dictionary.
            if buy_or_sell == "Buy":
                investments[full_name] = {"ticker": ticker_symbol, "sellHistory": [],
                                          "buyHistory": [
                                              {"date": order_date, "price": float(buy_or_sell_price),
                                               "quantity": quantity}
                                          ]}
            else:
                print(Fore.RED + "First time seeing {:s} and it's not a buy order.".format(full_name))
                sys.exit()


def process_stock_option_orders(full_name, current_price, investment_type):
    ticker_symbol = investments[full_name]["ticker"]
    buy_history_copy = copy.deepcopy(investments[full_name]["buyHistory"])
    sell_history_copy = copy.deepcopy(investments[full_name]["sellHistory"])

    total_sold = 0  # Keep track of how many were sold.
    total_remaining = 0  # Keep track of how many are left.

    total_sold_value = 0.00  # Keep track of total value of what was sold.
    total_sold_value_by_initial_cost = 0.00  # Keep track of total value if it were sold at the value it was bought at.

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

    realized_gain_loss_cell = calculate_percentage(total_sold_value, total_sold_value_by_initial_cost, investment_type)
    unrealized_gain_loss_cell = calculate_percentage(total_remaining_value, total_remaining_value_by_initial_cost,
                                                     investment_type)
    total_realized_unrealized = round((total_sold_value - total_sold_value_by_initial_cost) + \
                                      (total_remaining_value - total_remaining_value_by_initial_cost), 2)
    if total_realized_unrealized >= 0.00:
        current_profit_loss_cell = "{:s}+${:s}{:s}".format(G, str(total_realized_unrealized), N)
    else:
        current_profit_loss_cell = "{:s}${:s}{:s}".format(R, str(total_realized_unrealized), N)

    global totalProfitLoss  # Keep track of total profit/loss
    totalProfitLoss += total_realized_unrealized

    if total_remaining > 0:
        average_price = round((total_remaining_value_by_initial_cost / total_remaining), 2)
    else:
        average_price = 0.00  # No more shares left.

    if average_price == 0.00 or currentPrice == 0.00:
        average_price_cell = "{:s}${:s}{:s}".format(N, str(average_price), N)
    elif average_price <= current_price:
        average_price_cell = "{:s}${:s}{:s}".format(G, str(average_price), N)
    else:
        average_price_cell = "{:s}${:s}{:s}".format(R, str(average_price), N)

    current_price_cell = "{:s}${:s}{:s}".format(N, str(current_price), N)

    return [ticker_symbol, full_name, total_sold, realized_gain_loss_cell, total_remaining, unrealized_gain_loss_cell,
            current_profit_loss_cell, current_price_cell, average_price_cell]


# def process_wheel()


# +-----------------------------------------------Function-----------------------------------------------+


# +----------------------------------------------Stock Tables----------------------------------------------+
process_sheet(stock_data, "Stock")

stockTable = PrettyTable(["Ticker", "Sold", "Realized Gain/Loss (%)", "Remaining", "Unrealized Gain/Loss (%)",
                          "Current Profit/Loss ($)", "Current Price ($)", "Average Price ($)"])

for fullName in investments.keys():
    ticker = investments[fullName]["ticker"]
    url = f"https://api.tdameritrade.com/v1/marketdata/{ticker}/quotes"
    payload = {
        'apikey': stockAPIToken
    }
    stockInformation = requests.get(url=url, params=payload).json()
    currentPrice = requests.get(url=url, params=payload).json()[ticker]['lastPrice']
    processedInvestmentOrders = process_stock_option_orders(fullName, currentPrice, "stock")
    stockTable.add_row(processedInvestmentOrders)

print(stockTable)

stockTotalTable = PrettyTable(["Stock Total Profit/Loss ($)"])

stockTotalTable.add_row(calculate_total_table())

print(stockTotalTable)
# +----------------------------------------------Stock Tables----------------------------------------------+

# +------------------------------------------Option Wheel Tables-------------------------------------------+
process_sheet(wheel_data, "Wheel Contract")

stockTable = PrettyTable(["Ticker", "Wheel Stock", "Sold", "Realized Gain/Loss (%)", "Remaining", "Unrealized Gain/Loss (%)",
                          "Current Profit/Loss ($)", "Current Price ($)", "Average Price ($)"])

print("processedStockOptionOrders", processedInvestmentOrders)
print("investments", investments)
print("totalProfitLoss", totalProfitLoss)
# +------------------------------------------Option Wheel Tables-------------------------------------------+

# investments.clear()  # Clear dictionary.
# totalProfitLoss = 0.00
#
# # +----------------------------------------------Option Tables---------------------------------------------+
# process_sheet(option_data, "Contract")
#
# optionTable = PrettyTable(["Ticker", "Contract", "Sold", "Realized Gain/Loss (%)",
#                            "Remaining", "Unrealized Gain/Loss (%)",
#                            "Current Profit/Loss ($)", "Current Price ($)", "Average Price ($)"])
#
# for fullName in investments.keys():
#     fullNameSplit = fullName.split(" ", 4)  # Split Full Name by space to extract certain values.
#     symbol = fullNameSplit[0]
#     contractType = "CALL" if fullNameSplit[3] == "Call" else "PUT"
#     strike = fullNameSplit[1]
#     expirationDate = fullNameSplit[2]
#     expirationDateSplit = expirationDate.split("/", 3)
#     expirationDateFormatted = F"{expirationDateSplit[2]}-{expirationDateSplit[0]}-{expirationDateSplit[1]}"
#     currentPrice = 0.00  # Default value for current option price.
#
#     url = F"https://api.tdameritrade.com/v1/marketdata/chains?" \
#           F"&symbol={symbol}&contractType={contractType}&strike={strike}" \
#           F"&fromDate={expirationDateFormatted}&toDate={expirationDateFormatted}'"
#     payload = {
#         'apikey': stockAPIToken
#     }
#     optionInformation = requests.get(url=url, params=payload).json()
#     if optionInformation["status"] == "SUCCESS":
#         if contractType == "CALL":
#             expirationDateMap = optionInformation["callExpDateMap"]
#         else:
#             expirationDateMap = optionInformation["putExpDateMap"]
#         expirationDateMapKeys = list(expirationDateMap.keys())
#         if len(expirationDateMapKeys) == 1:
#             expirationDateMapEntry = expirationDateMap[expirationDateMapKeys[0]]
#             expirationDateMapEntryKeys = list(expirationDateMapEntry.keys())
#             if len(expirationDateMapEntryKeys) == 1:
#                 contractList = expirationDateMapEntry[expirationDateMapEntryKeys[0]]
#                 if len(contractList) == 1:
#                     contractInformation = contractList[0]
#                     currentPrice = contractInformation["mark"]
#                 else:
#                     print("More than contractList returned by API for {:s}.".format(fullName))
#             else:
#                 print("More than one expirationDateMapEntryKeys returned by API for {:s}.".format(fullName))
#         else:
#             print("More than one expirationDateMapKeys entry returned by API for {:s}.".format(fullName))
#             sys.exit()
#     # else:
#     #     print("Invalid API call for {:s} most likely expired.".format(fullName))
#
#     optionTable.add_row(process_stock_option_orders(fullName, currentPrice, "option"))
#
# print(optionTable)
#
# optionTotalTable = PrettyTable(["Options Total Profit/Loss ($)"])
#
# optionTotalTable.add_row(calculate_total_table())
#
# print(optionTotalTable)
# # +----------------------------------------------Option Tables---------------------------------------------+

print(Fore.RESET)
