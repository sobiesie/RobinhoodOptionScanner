import config
import option_strat 
import robin_stocks.robinhood as rh
import datetime as dt
import time
import csv
import pandas as pd
import yfinance as yf
from winotify import Notification, audio
import wikipedia as wp

# login = rh.login('email','password')  # Put your robinhood email and password

def logout():
    rh.authentication.logout()

def get_stocks():
    
    #Test List
    stocks = ['AAPL', 'MSFT', 'WAL', 'SHOP']

    #Gets Watch list from named robinhood list
    # focus_list = rh.account.get_watchlist_by_name(name='Research')
    # dip_list = rh.account.get_watchlist_by_name(name='DIP BUYS')
    # stocks.extend( [item['symbol'] for item in focus_list['results']])
    # stocks.extend( [item['symbol'] for item in dip_list['results']])


    return(stocks)


def open_market():
    market = True
    time_now = dt.datetime.now().time()
    market_open = dt.time(9,30,0)
    market_close = dt.time(15,59,0)

    if time_now > market_open and time_now < market_close:
        market = True
    else:
        print('### market is closed')
        return(market)

    return(market)

def get_cash(): 
    rh_cash = rh.account.build_user_profile()
    #print("rh_cash:", rh_cash)

    cash = float(rh_cash['cash'])
    equity = float(rh_cash['equity'])
    return(cash, equity)

def get_holdings_and_bought_price(stocks):
    holdings = {stocks[i]: 0 for i in range(0, len(stocks))}
    bought_price = {stocks[i]: 0 for i in range(0, len(stocks))}
    rh_holdings = rh.account.build_holdings()

    for stock in stocks:
        try:
            holdings[stock] = int(float((rh_holdings[stock]['quantity'])))
            bought_price[stock] = float((rh_holdings[stock]['average_buy_price']))
        except:
            holdings[stock] = 0
            bought_price[stock] = 0

    return(holdings, bought_price)

Rated_StockList = pd.DataFrame(columns=["Ticker", "Price","Buy Strike", "Sell Strike", "Rating", "IV Score", "RSI Score", "Perf Score", "Next Earning Date"]) 
def add_stock(ticker,price, rating, IV_Score, RSI_Score, Perf_Score, Earning_date):
    global Rated_StockList
    new_row = pd.DataFrame({"Ticker": [ticker], "Price": price, "Rating": [rating], "IV Score": [IV_Score], "RSI Score": [RSI_Score], "Perf Score": [Perf_Score], "Next Earning Date": [Earning_date]})
    Rated_StockList = pd.concat([Rated_StockList, new_row], ignore_index=True)


def closest_option(opts, target_strike):
    return opts.iloc[(opts['strike'] - target_strike).abs().argsort()[:1]]

def spread(stock, percentage_increase):
    current_date = pd.Timestamp.now().tz_localize(None).normalize()
    ticker = yf.Ticker(stock)
    expirations = ticker.options

    if not expirations:
        raise ValueError(f"No option data available for {ticker}")

    target_expiration = ts.get_nearest_future_expiration(expirations, current_date)
    opts = ticker.option_chain(target_expiration)
    current_price = ts.fetch_current_price(ticker)

    sell_target_strike = current_price * (1 + percentage_increase)
    buy_target_strike = sell_target_strike + 5

    #To prevent the same strike from being selected
    if buy_target_strike - sell_target_strike <= 2:
        buy_target_strike = sell_target_strike + 5

    sell_call = closest_option(opts.calls, sell_target_strike)
    buy_call = closest_option(opts.calls, buy_target_strike)
    print("---------------sell call -----------------")
    print(sell_call)
    print("---------------buy call ------------------")
    print(buy_call)

    return sell_call, buy_call, target_expiration, sell_target_strike, buy_target_strike

def calculate_credit_spread_max_profit_and_loss(sell_call, buy_call):
    # Premiums received and paid
    sell_premium = sell_call['lastPrice'].values[0]  # Assuming 'lastPrice' column gives the latest premium
    buy_premium = buy_call['lastPrice'].values[0] # Adjust this column name as per the data
    # print("Sell Premuim: ", sell_premium, "Buy Premuim: ", buy_premium)
    max_profit = (sell_premium - buy_premium) * 100
    strike_difference = buy_call['strike'].values[0] - sell_call['strike'].values[0]
    print("Strike_diffference", strike_difference)
    max_loss = (strike_difference * 100) - max_profit
    rounded_max_profit = round(max_profit, 2)
    print("MAX Profit", rounded_max_profit, "  MAX Loss", max_loss)

    print("Current Profit", (max_profit/ max_loss) * 100,"%")
    return max_profit, max_loss

if __name__ == "__main__":
    stocks = get_stocks()
    print('stocks in scan list:', stocks)
    cash, equity = get_cash()

    while open_market():  # while open_market() = True: 
        prices = rh.stocks.get_latest_price(stocks)
        holdings, bought_price = get_holdings_and_bought_price(stocks)

        for i, stock in enumerate(stocks):
            print("THE STOCKS:", stock)
            ts = option_strat.StockAnalysis(stock)
            data_signal = ts.fetch_data()
            if data_signal == False:
                continue
            ts.calculate_moving_averages()

            if i < len(prices):
                price = float(prices[i])
                print('{} = ${}'.format(stock,price))

            else:
                print(f"No price returned for stock: {stock}")
                continue

            ##Rating system Prime filter
            SMA_signal = ts.define_buy_sell_conditions()
            ER_signal, Earning_date = ts.find_earnings(stock)
            Volume_Signal = ts.volume()
            Filter_signal = False

            if SMA_signal == True and ER_signal == True and Volume_Signal == True:  # Edited
                RSI_Score = ts.calculate_rsi()
                IV_Score = ts.volitility(stock)
                Perf_Score = ts.calculate_percentcange()
                Total_Score = RSI_Score + IV_Score + Perf_Score
               
                if Total_Score >= 12 or Perf_Score >= 6:
                    Filter_signal = True
                    
                # Total Score scan
                if Filter_signal == True: #edited for test
                    print("Prime filter signal passed")

                    vwap_signal = ts.calculate_vwap()
                    pctChange_signal = ts.calculate_PctChange()

                    if vwap_signal == True and ER_signal == True and pctChange_signal == True:  #Vwap can be removed because stock prices fluctuate alot
                        if Earning_date:
                            print(f"Final Filter signal passed, Next earnings date: {Earning_date.date()}")
                        else:
                            print("No future earnings date found!")
                        add_stock(stock, price,Total_Score, IV_Score, RSI_Score, Perf_Score, Earning_date) 
                    else:
                         print(f"Second fail indicators, VWAP: {vwap_signal}, Earning: {ER_signal}, Percent Change: {pctChange_signal} ")
                else:
                    print(f"{stock} Total Score too low")
                
            else:
                print(f"Prime Fail indicators, SMA: {SMA_signal}, ER: {ER_signal}, Volume: {Volume_Signal} ")

        if Rated_StockList.empty:
            print("Data is empty. Skipping trade option calculation.")
            exit()
            
        else:
            # Find the tickers with the highest rating
            Rated_StockList["Rating"] = pd.to_numeric(Rated_StockList["Rating"], errors='coerce')
            index_of_highest_rated_stock = Rated_StockList["Rating"].idxmax()
            highest_rated_stock = Rated_StockList.loc[index_of_highest_rated_stock]
            ticker_value = highest_rated_stock.at['Ticker']
            print("Best Ticker ** ", ticker_value, " **") 
            
            #Starts to look for options 8% from current price
            if ticker_value:
                percent_increase = 0.08
                sell_call, buy_call, date,sell_strike,buy_strike = spread(ticker_value, percent_increase )
                max_profit, max_loss = calculate_credit_spread_max_profit_and_loss(sell_call, buy_call)
                counter = 0

                # While loop if the first option isn't in the 5% to 10 range
                while (max_profit < 0.05 * max_loss  or  max_profit > 0.10 * max_loss or max_profit <= 0):
                    if counter == 10:
                        break
                    counter +=1
                    print(f"Profit is not within desired range. Looping...{counter}")
                    percent_increase += .02
                    sell_call, buy_call, date, sell_strike, buy_strike = spread(ticker_value, percent_increase)
                    max_profit, max_loss = calculate_credit_spread_max_profit_and_loss(sell_call, buy_call)
             
                allowable_holdings = float(equity/2)  
                print("Cash on hand",allowable_holdings, "vs Max Loss", max_loss)
                
                #Notification system
                low_funds_warning = Notification(app_id="Option screener", title="Low Funds", msg="New Notification!", icon=r"C:\Users\sobie\Pictures\IMG_8845.JPG")
                lowBreaker = False
                if equity <= 100:
                    print("Account too low funds")
                    lowBreaker == True
                    low_funds_warning.show()

                if max_loss >= allowable_holdings:
                    lowBreaker = True
                    print("Low funds")
                    low_funds_warning.show()

                noti_buy = sell_call["strike"].values[0]
                noti_sell = buy_call["strike"].values[0]
                toast = Notification(app_id="Option screener Alert", title=f"Buy {ticker_value}", msg=f"buy at {noti_buy}, sell at {noti_sell}", icon=r"C:\Users\sobie\Desktop\BUY ICON1.tif")  #Put your own Buy image

                if holdings[stock] == 0 and lowBreaker == False:
                    toast.show()

                # Find the index for the row with the ticker_value
                ticker_index = Rated_StockList[Rated_StockList['Ticker'] == ticker_value].index[0]
                Rated_StockList.loc[ticker_index, "Sell Strike"] = sell_call["strike"].values[0]
                Rated_StockList.loc[ticker_index, "Buy Strike"] = buy_call["strike"].values[0]
                print(Rated_StockList)
                
                #Saves the current scans data to csv
                from datetime import datetime
                now = datetime.now()
                timestamp = now.strftime('%Y%m%d_%H%M%S')
                filename = f'C:\\Users\\sobie\\Desktop\\Rated Stocks\\Rated_StockList_{timestamp}.csv'
                Rated_StockList.to_csv(filename, index=False)


        # Query your positions
        # print(rh.account.load_phoenix_account(info=None))  # I want to see option_buying_power
        # print("-------------")
        # positions = rh.options.get_aggregate_open_positions()    # useful for strategy name example ("long_put")
        # print(positions)

        # print("-------------")
        # open_options = rh.options.get_open_option_positions()
        # for option in open_options:
        #     symbol = option['chain_symbol']
        #     option_id = option['option_id']
        #     average_price = float(option['average_price'])/100
        #     quantity = float(option['quantity'])
            
        #     option_info = rh.options.get_option_market_data_by_id(option_id)[0]
        #     current_price = float(option_info['adjusted_mark_price'])

        #     print("CURRENT PRICE: ", current_price, " Average Price: ",average_price, "QUANTITY: ", quantity)
        #     profit_or_loss = ((current_price - average_price) * quantity) * 100
            
        #     print(f"Symbol: {symbol}, Profit/Loss: ${profit_or_loss:.2f}")

                    
        #Delay still next scan
        time.sleep(3600)
