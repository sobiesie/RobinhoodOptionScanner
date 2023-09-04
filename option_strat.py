import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
import pandas_ta as ta
import numpy as np
import datetime

class StockAnalysis:
    def __init__(self, ticker):
        self.ticker = ticker
        self.start_date = '2023-06-01'
        self.end_date =  '2023-12-31'
        self.data = None
  
    # Fetch data
    def fetch_data(self):
        self.data = yf.download(self.ticker, start=self.start_date, end=self.end_date)
        self.data = self.data.copy()
        self.data.dropna(inplace=True)

        if self.data.empty:
            print(f"The {self.ticker} data is empty!")
            return False  # or handle it in another way if needed
        
    # Find earning day
    def find_earnings(self,ticker):
        ticker_data = yf.Ticker(ticker)
        earnings_dates = ticker_data.earnings_dates
 
        # Convert the timezone-aware index to a timezone-naive index and remove time information
        earnings_dates.index = earnings_dates.index.tz_localize(None).normalize()

        # Get the current date without time information
        current_date = pd.Timestamp.now().tz_localize(None).normalize()

        # Find the next earnings date
        next_earnings_date = None

        for date in earnings_dates.index[::-1]:  # Iterate in ascending order
            if date > current_date:  # Convert Timestamp to datetime.date for comparison
                next_earnings_date = date
                break

        # Check if current_date is 14 days away from next_earnings_date
        signal = False
        if next_earnings_date:
            days_difference = (next_earnings_date - current_date).days  # Convert Timestamp to datetime.date for subtraction
            #print("DAYs",days_difference)
            if days_difference <= 60 and days_difference > 0:  # change back to 14 later
                signal = True
            else:
                signal = False

        return signal, next_earnings_date

    
    #Calculate SMA
    def calculate_moving_averages(self, short_ma_length=9, long_ma_length=20):
        # Calculate moving averages
        self.data['short_ma'] = self.data['Close'].rolling(window=short_ma_length).mean()
        self.data['long_ma'] = self.data['Close'].rolling(window=long_ma_length).mean()

        # Shift moving averages by one day
        self.data['short_ma_shifted'] = self.data['short_ma'].shift(1)
        self.data['long_ma_shifted'] = self.data['long_ma'].shift(1)

    #Buy Sell SMA indicator
    def define_buy_sell_conditions(self):
        # Define buy and sell conditions
        self.data['buy'] = (self.data['short_ma'] < self.data['Close'])

        # Drop rows with NaN values
        self.data = self.data.dropna()

        #print("BUY CINDITION MA: ",self.data['buy'][-1])
        if not self.data.empty:
            if self.data['buy'][-1] == True:
                return True
            elif self.data['buy'][-1] == False:
                return False


    def volitility(self, ticker):
        # Get options expiration dates
        ticker = yf.Ticker(ticker)

        # Get options expiration dates
        expirations = ticker.options

        # If there are no available expirations, exit
        if not expirations:
            print(f"No option data available for {ticker}")
            return 0

        # Let's take the nearest expiration date as an example
        nearest_expiration = expirations[1]

        # Get call and put options for that expiration date
        opts = ticker.option_chain(nearest_expiration)

        # Try to get the current market price using multiple potential keys
        current_price_keys = ['regularMarketPrice', 'currentPrice', 'close']
        current_price = None
        for key in current_price_keys:
            current_price = ticker.info.get(key)
            if current_price is not None:
                break

        if current_price is None:
            raise ValueError("Unable to fetch the current market price for the stock.")

        # Find the at-the-money call option (or the closest to it)
        atm_call = opts.calls.iloc[(opts.calls['strike'] - current_price).abs().argsort()[:1]]

        # Extract the IV for that option
        # iv_atm_call = atm_call['impliedVolatility'].values[0]

        try:
        # Extract the IV for that option
            iv_atm_call = atm_call['impliedVolatility'].values[0]
        except IndexError:
            print(f"No implied volatility data found for {ticker} at the money call.")
            return 0
        #print(f"Implied Volatility for {ticker} ATM call option with expiration {nearest_expiration}: {iv_atm_call:.2%}")
        
        # Rating system
        credit = 4
        if iv_atm_call > .40:
            return 4 * 4
        elif iv_atm_call > .30:
            return 3 * 4
        elif iv_atm_call >.20:
            return 2 * 4
        elif iv_atm_call > .10:
            return 1 * 4
        else:
            return 0


    #SELL indicator
    def calculate_stop_loss(self, stop_loss_level=0.1):
        # Set the stop-loss level
        # Create a series that contains the highest price achieved so far
        self.data['high_so_far'] = self.data['Close'].expanding().max()

        # Calculate the stop-loss threshold for each day
        self.data['stop_loss_threshold'] = self.data['high_so_far'] * (1 - stop_loss_level)

        # A stop-loss sell signal occurs when the price drops to the stop-loss threshold
        self.data['stop_loss_sell'] = self.data['Close'] <= self.data['stop_loss_threshold']

    
    #Buy Indicator
    def calculate_rsi(self, rsi_period=14):
        # Calculate RSI
        # Check if the 'Volume' Series is empty
        if self.data['Close'].empty:
            print("The 'Close' data is empty!")
            return False  # or handle it in another way if needed

        rsi_indicator = RSIIndicator(self.data['Close'], rsi_period)
        self.data['rsi'] = rsi_indicator.rsi()


        # Rating System
        credit = 3
        grade =  self.data['rsi'][-1]
        #print("RSI grade", grade)
        if grade >= 90:
            return 5 * credit
        elif grade >= 80:
            return 4 * credit
        elif grade >= 70:
            return 3 * credit
        elif grade >= 60:
            return 2 * credit
        elif grade >= 50:
            return 2 * credit
        elif grade >= 40:
            return 1 * credit
        else:
            return 0
        
    # Entry indicator
    def calculate_vwap(self):
        # Calculate VWAP
        self.data['vwap'] = ta.vwap(self.data['High'], self.data['Low'], self.data['Close'], self.data['Volume'])

        if self.data['vwap'][-1] < self.data['Close'][-1]: 
            #print('vwap test')
            return True
        else:
            return False


    def calculate_PctChange(self):
        # Calculate percent change
        self.data['Pct Change'] = self.data['Adj Close'].pct_change()

        if self.data['Pct Change'][-1] > .005:
            return True
        elif self.data['Pct Change'][-1] < 0.005:
            return False
        else:
            return None

    def calculate_percentcange(self):
        # Calculate percent change
        self.data['Pct Change'] = self.data['Adj Close'].pct_change()
        self.data['Weekly Pct Change'] = self.data['Adj Close'].pct_change(periods=5)
        self.data['Monthly Pct Change'] = self.data['Adj Close'].pct_change(periods=30)

        Wpercentage_change = self.data['Weekly Pct Change'].iloc[-1] * 100
        Mpercentage_change = self.data['Monthly Pct Change'].iloc[-1] * 100

        credit = 2
        score1 = 0
        score2 = 0
        if Wpercentage_change >= 5:
            score1 = 5 * credit 
        elif Wpercentage_change >= 4:
            score1 = 4 
        elif Wpercentage_change >= 3:
            score1 = 3 
        elif Wpercentage_change >= 2:
            score1 = 2 
        elif Wpercentage_change > 0.5:
            score1 = 1 
        
        if Mpercentage_change >= 10:
            score2 = 4 * credit 
        elif Mpercentage_change >= 6:
            score2= 3 * credit 
        elif Mpercentage_change > 4:
            score2 = 2 * credit 
        elif Mpercentage_change > 1:
            score2 = 1 * credit 

        return score1 + score2


    def get_pe_ratio(self):
        # Get P/E ratio
        pe_ratio = yf.Ticker(self.ticker).info['trailingPE']
                
        #Rating
        print("PE", pe_ratio)
        credit = 4
        if pe_ratio > 20:
            return 4 * credit
        elif  pe_ratio < 20 and pe_ratio > 0:
            return 2 * credit
        else:
            return 0 

    def volume(self):
        # Check if the 'Volume' Series is empty
        if self.data['Volume'].empty:
            print("The 'Volume' data is empty!")
            return False  # or handle it in another way if needed

        if self.data['Volume'][-2] > 500_000:
            # volume = self.data['Volume'][-2]
            #print("Volume is", volume)
            return True
        else:
            return False
    

    def print_data(self):
        print(self.data)

    def fetch_current_price(self, ticker):
        current_price_keys = ['regularMarketPrice', 'currentPrice', 'close']
        for key in current_price_keys:
            price = ticker.info.get(key)
            if price:
                return price
        raise ValueError("Unable to fetch the current market price for the stock.")
    
    def get_nearest_future_expiration(self, expirations, current_date, threshold_days=45):
        future_expirations = [exp for exp in expirations if (pd.Timestamp(exp) - current_date).days >= threshold_days]
        if future_expirations:
            return future_expirations[0]
        raise ValueError("No option expiration dates available that are >= 45 days in the future.")