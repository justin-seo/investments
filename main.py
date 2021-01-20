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
totalProfitLoss = 0.00  # Total profit/loss made.
totalCostBasis = 0.00  # Total cost basis of investments.
processedInvestmentOrders = ["", "", 0, 0.00, 0, 0.00, "", "", ""]
# +----------------------------------------------Stock Data----------------------------------------------+
stock_sheet = client.open("Investments").sheet1
stock_data = stock_sheet.get_all_records()  # Assume rows are from oldest to newest.
# +----------------------------------------------Stock Data----------------------------------------------+
# +----------------------------------------------Stock Data----------------------------------------------+
otc_stock_sheet = client.open("Investments").worksheet("OTC Stocks")
otc_stock_data = otc_stock_sheet.get_all_records()  # Assume rows are from oldest to newest.
# +----------------------------------------------Stock Data----------------------------------------------+
# +----------------------------------------------Option Data---------------------------------------------+
option_sheet = client.open("Investments").worksheet("Options")
option_data = option_sheet.get_all_records()  # Assume rows are from oldest to newest.
# +----------------------------------------------Option Data---------------------------------------------+
# +----------------------------------------------Crypto Data---------------------------------------------+
coin_sheet = client.open("Investments").worksheet("Coins")
coin_data = coin_sheet.get_all_records()  # Assume rows are from oldest to newest.


# +----------------------------------------------Crypto Data---------------------------------------------+


# +-----------------------------------------------Function-----------------------------------------------+
# def calculate_cost_basis(sheets):
#     global totalCostBasis  # Keep track of total cost basis
#     for sheet in sheets:
#         quantity = sheet["Quantity"]
#         price = sheet["Buy/Sell Price"]
#         buy_sell = sheet["Buy/Sell"]
#         if buy_sell == "Buy":
#             totalCostBasis += quantity * price


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


def calculate_total_table(sheets):
    global totalCostBasis  # Keep track of total cost basis
    global totalProfitLoss  # Keep track of total cost basis

    for sheet in sheets:  # Calculate cost basis
        quantity = sheet["Quantity"]
        price = sheet["Buy/Sell Price"]
        buy_sell = sheet["Buy/Sell"]
        if buy_sell == "Buy":
            totalCostBasis += quantity * price

    total_profit_loss_rounded = round(totalProfitLoss, 2)
    total_cost_basis_rounded = round(totalCostBasis, 2)
    if total_profit_loss_rounded >= 0.00:
        total_profit_loss_cell = "{:s}+${:s}{:s}".format(G, str(total_profit_loss_rounded), N)
        total_profit_loss_percentage_rounded = round(
            ((1 + (total_profit_loss_rounded / total_cost_basis_rounded)) * 100))
        total_profit_loss_percentage_cell = "{:s}+{:s}%{:s}".format(G, str(total_profit_loss_percentage_rounded), N)
        total_cost_basis_cell = "{:s}${:s}{:s}".format(G, str(total_cost_basis_rounded), N)

    else:
        total_profit_loss_cell = "{:s}${:s}{:s}".format(R, str(total_profit_loss_rounded), N)
        total_profit_loss_percentage_rounded = round(
            ((1 - (1 + (total_profit_loss_rounded / total_cost_basis_rounded))) * 100))
        total_profit_loss_percentage_cell = "{:s}-{:s}%{:s}".format(R, str(total_profit_loss_percentage_rounded), N)
        total_cost_basis_cell = "{:s}${:s}{:s}".format(R, str(total_cost_basis_rounded), N)
    return [total_profit_loss_cell, total_profit_loss_percentage_cell, total_cost_basis_cell]


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
            # elif buy_or_sell == "Fee":
            #     fee_history = investments[full_name]["feeHistory"]
            #     fee_history.append(new_order)  # Append sell order to sellHistory
            #     investments[full_name]["feeHistory"] = fee_history
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


def process_investment_orders(full_name, current_price, investment_type):
    ticker_symbol = investments[full_name]["ticker"]
    buy_history_copy = copy.deepcopy(investments[full_name]["buyHistory"])
    sell_history_copy = copy.deepcopy(investments[full_name]["sellHistory"])
    # fee_history_copy = copy.deepcopy(investments[full_name]["feeHistory"])

    total_sold = 0.00  # Keep track of how many were sold.
    total_remaining = 0.00  # Keep track of how many are left.

    total_sold_value = 0.00  # Keep track of total value of what was sold.
    total_sold_value_by_initial_cost = 0.00  # Keep track of total value if it were sold at the value it was bought at.

    total_remaining_value = 0.00  # Keep track of total value by current price.
    total_remaining_value_by_initial_cost = 0.00  # Keep track of total value by buy in price.

    for sell_index in range(len(sell_history_copy)):
        sell_order = sell_history_copy[sell_index]
        sell_quantity = float(sell_order["quantity"])  # Quantity of a sell order.
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
                        sell_quantity = 0.00
                    else:  # Current buy order < current sell order quantity.
                        total_sold_value += (sell_price * buy_quantity)  # Add realized gain
                        total_sold_value_by_initial_cost += (buy_price * buy_quantity)  # Add initial cost.
                        total_sold += buy_quantity
                        buy_quantity = 0.00
                        sell_quantity -= buy_quantity
                buy_history_copy[buy_index]["quantity"] = buy_quantity  # Update quantity of current buy order.
        sell_history_copy[sell_index]["quantity"] = sell_quantity  # Update quantity of current buy order.

    # if investment_type == "coin":
    #     for fee_index in range(len(fee_history_copy)):
    #         fee_order = fee_history_copy[fee_index]
    #         fee_quantity = float(fee_order["quantity"])  # Quantity of a fee.
    #         fee_price = fee_order["price"]  # Price of a fee.
    #         if fee_quantity > 0:  # Iterate buy_history_copy if current fee order has quantity.
    #             for buy_index in range(len(buy_history_copy)):
    #                 buy_order = buy_history_copy[buy_index]
    #                 buy_quantity = buy_order["quantity"]  # Quantity of a buy order.
    #                 buy_price = buy_order["price"]  # Price of a buy order.
    #                 if buy_quantity != 0:  # Continue if current buy order has quantity.
    #                     if buy_quantity >= fee_quantity:  # Current buy order >= current sell order quantity.
    #                         total_sold_value += (fee_price * fee_quantity)  # Add realized gain
    #                         total_sold_value_by_initial_cost += (buy_price * fee_quantity)  # Add initial cost.
    #                         total_sold += fee_quantity
    #                         buy_quantity -= fee_quantity
    #                         sell_quantity = 0.00
    #                     else:  # Current buy order < current sell order quantity.
    #                         total_sold_value += (fee_price * buy_quantity)  # Add realized gain
    #                         total_sold_value_by_initial_cost += (buy_price * buy_quantity)  # Add initial cost.
    #                         total_sold += buy_quantity
    #                         buy_quantity = 0.00
    #                         fee_quantity -= buy_quantity
    #                 buy_history_copy[buy_index]["quantity"] = buy_quantity  # Update quantity of current buy order.
    #             sell_history_copy[fee_index]["quantity"] = sell_quantity  # Update quantity of current buy order.

    # Loop through buy history after updating quantity by running through sell history.
    for buy_index in range(len(buy_history_copy)):
        buy_order = buy_history_copy[buy_index]
        buy_quantity = float(buy_order["quantity"])  # Quantity of a buy order.
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

    if total_remaining > 0.00:
        average_price = round((total_remaining_value_by_initial_cost / total_remaining), 2)
        current_total = round((total_remaining * currentPrice), 2)
        if current_price >= average_price:
            current_price_cell = "{:s}${:s}{:s}".format(G, str(current_price), N)
            current_total_cell = "{:s}${:s}{:s}".format(G, str(current_total), N)
        else:
            current_price_cell = "{:s}${:s}{:s}".format(R, str(current_price), N)
            current_total_cell = "{:s}${:s}{:s}".format(R, str(current_total), N)
    else:
        average_price = 0.00  # No more shares left.
        current_price_cell = "{:s}${:s}{:s}".format(N, str(current_price), N)
        current_total_cell = "{:s}$0.00{:s}".format(N, N)

    average_total = round((total_remaining * average_price), 2)
    if average_price == 0.00 or currentPrice == 0.00:
        average_price_cell = "{:s}${:s}{:s}".format(N, str(average_price), N)
        average_total_cell = "{:s}${:s}{:s}".format(N, str(average_total), N)
    elif average_price <= current_price:
        average_price_cell = "{:s}${:s}{:s}".format(G, str(average_price), N)
        average_total_cell = "{:s}${:s}{:s}".format(G, str(average_total), N)
    else:
        average_price_cell = "{:s}${:s}{:s}".format(R, str(average_price), N)
        average_total_cell = "{:s}${:s}{:s}".format(R, str(average_total), N)

    return [ticker_symbol, full_name, realized_gain_loss_cell, unrealized_gain_loss_cell, current_profit_loss_cell,
            total_sold, total_remaining, current_price_cell, current_total_cell, average_price_cell, average_total_cell]
# +-----------------------------------------------Function-----------------------------------------------+


# +----------------------------------------------Stock Tables----------------------------------------------+
process_sheet(stock_data, "Stock")

stockTable = PrettyTable(["Ticker", "Name", "Realized Gain/Loss (%)", "Unrealized Gain/Loss (%)",
                          "Current Profit/Loss ($)", "Sold", "Remaining", "Current Price ($)",
                          "Current Total ($)", "Average Price ($)", "Average Total ($)"])

for fullName in investments.keys():
    ticker = investments[fullName]["ticker"]
    url = f"https://api.tdameritrade.com/v1/marketdata/{ticker}/quotes"
    payload = {
        'apikey': stockAPIToken
    }
    stockInformation = requests.get(url=url, params=payload).json()
    currentPrice = stockInformation[ticker]['lastPrice']
    stockTable.add_row(process_investment_orders(fullName, currentPrice, "stock"))

print(PrettyTable(["Stock Table"]))
print(stockTable)

stockTotalTable = PrettyTable(["Profit/Loss ($)", "Profit/Loss (%)", "Cost Basis"])
stockTotalTable.add_row(calculate_total_table(stock_data))

print(PrettyTable(["Total Table"]))
print(stockTotalTable)
# +----------------------------------------------Stock Tables----------------------------------------------+
investments.clear()  # Clear dictionary.
totalProfitLoss = 0.00
totalCostBasis = 0.00
print(Fore.RESET)
# +----------------------------------------------OTC Stock Tables----------------------------------------------+
process_sheet(otc_stock_data, "Stock")

stockTable = PrettyTable(["Ticker", "Name", "Realized Gain/Loss (%)", "Unrealized Gain/Loss (%)",
                          "Current Profit/Loss ($)", "Sold", "Remaining", "Current Price ($)",
                          "Current Total ($)", "Average Price ($)", "Average Total ($)"])

for fullName in investments.keys():
    ticker = investments[fullName]["ticker"]
    url = f"https://api.tdameritrade.com/v1/marketdata/{ticker}/quotes"
    payload = {
        'apikey': stockAPIToken
    }
    stockInformation = requests.get(url=url, params=payload).json()
    currentPrice = stockInformation[ticker]['lastPrice']
    stockTable.add_row(process_investment_orders(fullName, currentPrice, "stock"))

print(PrettyTable(["OTC Stock Table"]))
print(stockTable)

stockTotalTable = PrettyTable(["Profit/Loss ($)", "Profit/Loss (%)", "Cost Basis"])
stockTotalTable.add_row(calculate_total_table(otc_stock_data))

print(PrettyTable(["Total Table"]))
print(stockTotalTable)
# +----------------------------------------------OTC Stock Tables----------------------------------------------+
investments.clear()  # Clear dictionary.
totalProfitLoss = 0.00
totalCostBasis = 0.00
print(Fore.RESET)
# +----------------------------------------------Option Tables---------------------------------------------+
process_sheet(option_data, "Contract")

optionTable = PrettyTable(["Ticker", "Contract", "Realized Gain/Loss (%)", "Unrealized Gain/Loss (%)",
                           "Current Profit/Loss ($)", "Sold", "Remaining", "Current Price ($)",
                           "Current Total ($)", "Average Price ($)", "Average Total ($)"])

for fullName in investments.keys():
    fullNameSplit = fullName.split(" ", 4)  # Split Full Name by space to extract certain values.
    symbol = fullNameSplit[0]
    contractType = "CALL" if fullNameSplit[3] == "Call" else "PUT"
    strike = fullNameSplit[1]
    expirationDate = fullNameSplit[2]
    expirationDateSplit = expirationDate.split("/", 3)
    expirationDateFormatted = F"{expirationDateSplit[2]}-{expirationDateSplit[0]}-{expirationDateSplit[1]}"
    currentPrice = 0.00  # Default value for current option price.

    url = F"https://api.tdameritrade.com/v1/marketdata/chains?" \
          F"&symbol={symbol}&contractType={contractType}&strike={strike}" \
          F"&fromDate={expirationDateFormatted}&toDate={expirationDateFormatted}"
    payload = {
        'apikey': stockAPIToken
    }
    optionInformation = requests.get(url=url, params=payload).json()
    if optionInformation["status"] == "SUCCESS":
        if contractType == "CALL":
            expirationDateMap = optionInformation["callExpDateMap"]
        else:
            expirationDateMap = optionInformation["putExpDateMap"]
        expirationDateMapKeys = list(expirationDateMap.keys())
        if len(expirationDateMapKeys) == 1:
            expirationDateMapEntry = expirationDateMap[expirationDateMapKeys[0]]
            expirationDateMapEntryKeys = list(expirationDateMapEntry.keys())
            if len(expirationDateMapEntryKeys) == 1:
                contractList = expirationDateMapEntry[expirationDateMapEntryKeys[0]]
                if len(contractList) > 0:
                    for contract in contractList:
                        if not contract["nonStandard"]:  # NonStandard options are ones that include mergers.
                            currentPrice = contract["mark"] * 100  # multiply by 100 to get total price of contract.
                            break
                else:
                    print("Zero contractList returned by API for {:s}.".format(fullName))
            else:
                print("More than one expirationDateMapEntryKeys returned by API for {:s}.".format(fullName))
        else:
            print("More than one expirationDateMapKeys entry returned by API for {:s}.".format(fullName))
            sys.exit()
    # else:
    #     print("Invalid API call for {:s} most likely expired.".format(fullName))

    optionTable.add_row(process_investment_orders(fullName, currentPrice, "option"))

print(PrettyTable(["Stock Option Table"]))
print(optionTable)

optionTotalTable = PrettyTable(["Profit/Loss ($)", "Profit/Loss (%)", "Cost Basis"])
optionTotalTable.add_row(calculate_total_table(option_data))

print(PrettyTable(["Total Table"]))
print(optionTotalTable)
# +----------------------------------------------Option Tables---------------------------------------------+
investments.clear()  # Clear dictionary.
totalProfitLoss = 0.00
totalCostBasis = 0.00
print(Fore.RESET)
# +-----------------------------------------------Coin Tables----------------------------------------------+
process_sheet(coin_data, "Currency")

coinTable = PrettyTable(["Ticker", "Currency", "Realized Gain/Loss (%)", "Unrealized Gain/Loss (%)",
                         "Current Profit/Loss ($)", "Sold", "Remaining", "Current Price ($)",
                         "Current Total ($)", "Average Price ($)", "Average Total ($)"])

for fullName in investments.keys():
    ticker = investments[fullName]["ticker"]
    url = f"https://api.coinbase.com/v2/prices/{ticker}-USD/spot"
    coinInformation = requests.get(url=url).json()
    currentPrice = float(coinInformation["data"]['amount'])
    coinTable.add_row(process_investment_orders(fullName, currentPrice, "coin"))

print(PrettyTable(["Coin Table"]))
print(coinTable)

coinTotalTable = PrettyTable(["Profit/Loss ($)", "Profit/Loss (%)", "Cost Basis"])
coinTotalTable.add_row(calculate_total_table(coin_data))

print(PrettyTable(["Total Table"]))
print(coinTotalTable)
# +-----------------------------------------------Coin Tables----------------------------------------------+
investments.clear()  # Clear dictionary.
totalProfitLoss = 0.00
totalCostBasis = 0.00
print(Fore.RESET)
