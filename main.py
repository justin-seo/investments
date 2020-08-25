import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pprint import pprint
import requests
import copy
import sys
from colorama import Fore, Back, Style

stockAPIToken = (os.environ["FINNHUB_TOKEN"])

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)

client = gspread.authorize(credentials)

sheet = client.open("Investments").sheet1

data = sheet.get_all_records()  # Assume rows are from oldest to newest.

# Initialize dictionary of different investment types.
stocks = {}
# Initialize gains/losses of different investment types.
stockGains = 0.00


def sell_stock(order_history, sell_quantity, c):
    sell_quantity_copy = copy.deepcopy(sell_quantity)
    order_history_copy = copy.deepcopy(order_history)
    gain_or_loss = 0.00

    for index, order in order_history:
        order_quantity = order["quantity"]
        if order_quantity > sell_quantity_copy:  # Current order quantity is greater than what you are selling.
            order_quantity -= sell_quantity_copy
            order_history_copy[index]["quantity"] = order_quantity
            break
        elif sell_quantity_copy >= order_quantity:  # Current order quantity is equal or less than what you are selling.
            order_history_copy[index]["quantity"] = 0
            sell_quantity_copy -= order_quantity
        else:
            print(Fore.RED + "Invalid Order History.")
            sys.exit()

    return order_history_copy


for row in data:
    fullName = row["Investment"]
    ticker = row["Ticker"]
    quantity = row["Quantity"]
    buyOrSell = row["Buy/Sell"]
    buyOrSellPrice = row["Buy/Sell Price"]
    orderDate = row["Order Date"]

    if ticker in stocks.keys():  # Stock already in dictionary
        totalQuantity = stocks[ticker]["totalQuantity"]
        averagePrice = stocks[ticker]["averagePrice"]
        buyHistory = stocks[ticker]["buyHistory"]
        sellHistory = stocks[ticker]["sellHistory"]
        newOrder = {"date": orderDate, "price": buyOrSellPrice, "quantity": quantity}

        if buyOrSell == "Buy":
            buyHistory.append(newOrder)

            # Total price of stocks before new buy order.
            initialTotal = totalQuantity * averagePrice
            # New total quantity including new buy order.
            totalQuantity += quantity
            # New average price including buy order.
            averagePrice = (initialTotal + (quantity * buyOrSellPrice)) / totalQuantity

            stocks[ticker]["totalQuantity"] = totalQuantity
            stocks[ticker]["averagePrice"] = averagePrice
            stocks[ticker]["buyHistory"] = buyHistory
        elif buyOrSell == "Sell":
            sellHistory.append(newOrder)

            # Total price of stocks before new buy order.
            initialTotal = totalQuantity * averagePrice
            # New total quantity including new buy order.
            totalQuantity -= quantity
            # New average price including buy order.
            averagePrice = (initialTotal - (quantity * buyOrSellPrice)) / totalQuantity

            stocks[ticker]["totalQuantity"] = totalQuantity
            stocks[ticker]["averagePrice"] = averagePrice
            stocks[ticker]["sellHistory"] = sellHistory
    else:  # Stock not in dictionary.
        if buyOrSell == "Buy":
            stocks[ticker] = {"fullName": fullName, "totalQuantity": quantity, "averagePrice": buyOrSellPrice,
                              "buyHistory": [{"date": orderDate, "price": buyOrSellPrice, "quantity": quantity}],
                              "sellHistory": []}
        else:
            print(Fore.RED + "First time seeing {:s} and it's not a buy order.".format(ticker))

pprint(stocks)

for ticker in stocks.keys():
    url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={stockAPIToken}"
    currentPrice = requests.get(url).json()["c"]
    averagePrice = stocks[ticker]["averagePrice"]
    totalQuantity = stocks[ticker]["totalQuantity"]

    # Logic for Unrealized Gain/Loss
    currentUnrealizedTotal = currentPrice * totalQuantity
    averageUnrealizedTotal = averagePrice * totalQuantity
    unrealizedPercentage = ((currentUnrealizedTotal / averageUnrealizedTotal) - 1) * 100

    if averagePrice < currentPrice:  # Gain
        print(Fore.GREEN + "{:s} Unrealized Gain is +{:s}%".format(ticker, str(unrealizedPercentage)))
    else:  # Loss
        print(Fore.RED + "{:s} Unrealized Loss is {:s}%".format(ticker, str(unrealizedPercentage)))

print(Style.RESET_ALL)  # Reset colored terminal output.
