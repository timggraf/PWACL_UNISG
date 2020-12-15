from pycoingecko import CoinGeckoAPI 
from binance.client import Client # Import the Binance Client
from binance.websockets import BinanceSocketManager # Import the Binance Socket Manager
import pandas as pd

# turn off warnings
pd.options.mode.chained_assignment = None  # default='warn'


cg = CoinGeckoAPI()

# Although fine for tutorial purposes, your API Keys should never be placed directly in the script like below. 
# You should use a config file (cfg or yaml) to store them and reference when needed.
PUBLIC = 'r7NNoC9Y67xf2mmwSTYM1DwRA03Q3i6YHvKElp9aU6a3LFh0Fhmv0MRPSqBsAt6z'
SECRET = 'CTfkY0bkUpiLfzEgZjL78X93UhN79Tb26Cqp7W27TSVvhod8vZUR3ACr1Q0B86ju'

# Instantiate a Client 
client = Client(api_key=PUBLIC, api_secret=SECRET)

# Gets data from account balance as dictionary
coin_balance = client.get_account()

#transform balance from dictionary to dataframe
coin_balance = pd.DataFrame.from_dict(coin_balance['balances'])
print(coin_balance)

# transform values to integers
coin_balance['free'] = pd.to_numeric(coin_balance['free'])
coin_balance['locked'] = pd.to_numeric(coin_balance['locked'])
coin_balance.dtypes


# Get market caps from coingecko
market_cap = pd.DataFrame.from_dict(cg.get_global()) #get the data from the api
market_cap = market_cap.sort_values(by='market_cap_percentage', ascending=False, na_position='last') #sort by largest to smallest
market_cap = market_cap.reset_index(drop=False) # reset index
market_cap = market_cap.head(10) #only get top 10
columns_marketcap = ['index', 'market_cap_percentage'] #add columns
market_cap = market_cap.drop(columns=[col for col in market_cap if col not in columns_marketcap]) #drop all columns we don't need
market_cap = market_cap.rename(columns={'index': 'symbol'}) #change name of column
market_cap['symbol'] = market_cap['symbol'] + 'usdt' # add USDT to string
market_cap['symbol'] = market_cap['symbol'].str.upper() # make the dataframe Uppercase to compare
sum_caps = market_cap['market_cap_percentage'].sum() 
market_cap['market_cap_percentage'] = (market_cap['market_cap_percentage']/sum_caps)

"""
# COINGECKO: Get market cap data from 
tickers = client.get_ticker()
prices = pd.DataFrame.from_dict(tickers)
prices_table_columns = ['symbol']
prices = prices.drop(columns=[col for col in prices if col not in prices_table_columns]) #drop all values not needed
prices.loc[prices['symbol']=='BTCUSDT'] #check for USDT

# COINGECKO: As USDTUSDT does not exist we need to append it
prices.loc[prices['symbol']=='USDTUSDT'] #check for USDT
prices = prices.append({'symbol': 'USDTUSDT', "lastPrice": 1}, ignore_index=True)
prices.loc[prices['symbol']=='USDTUSDT'] #check for USDT again, now we find it
print(prices)
"""

# BINANCE: Get prices from Binance
prices_binance = client.get_all_tickers() #gets all prices
prices_binance = pd.DataFrame.from_dict(prices_binance) #converts dictionary to dataframe
prices_binance.loc[prices_binance['symbol']=='BTCUSDT'] #check for BTCUSDT, we find it

# As USDTUSDT does not exist we need to append it
prices_binance.loc[prices_binance['symbol']=='USDTUSDT'] #check for USDT
prices_binance = prices_binance.append({'symbol': 'USDTUSDT', "price": 1}, ignore_index=True)
prices_binance.loc[prices_binance['symbol']=='USDTUSDT'] #check for USDT again, now we find it
print(prices_binance)


# create columns for later and some more data handling
coin_balance['portfolio weights'] = 'NA'
coin_balance['USDT'] = 'NA'
coin_balance = coin_balance.rename(columns={'asset': 'symbol'}) #change name of column
coin_balance['symbol'] = coin_balance['symbol'] + 'usdt' # add USDT to string
coin_balance['symbol'] = coin_balance['symbol'].str.upper() # make the dataframe Uppercase to compare


# merge both dataframes
coin_balance = coin_balance.rename(columns={'asset': 'symbol'})
df = pd.merge(prices_binance, coin_balance, how ='inner', on='symbol')
df['price'] = pd.to_numeric(df['price']) #transform to integers
df.dtypes #check it is transformered to integers


# calculate portfolio values
for i in range(len(df)):
    df['USDT'][i] =  df['price'][i] * df['free'][i]

# calculate portfolio weights
df['USDT'] = pd.to_numeric(df['USDT'])
portfolio_sum = df['USDT']
portfolio_sum = portfolio_sum.sum()
for i in range(len(df)):
    df['portfolio weights'][i] = df['USDT'][i]/portfolio_sum
df.loc[df['symbol'] == 'USDTUSDT'] #probably not necessary


# drop all not needed values from the df price 
df_table_columns = ['symbol', 'price', 'free', 'portfolio weights', 'USDT']
df = df.drop(columns=[col for col in df if col not in df_table_columns])

#merge both dataframes
df_merged = pd.merge(df, market_cap, how ='left', on='symbol')
df_merged = df_merged.sort_values(by='market_cap_percentage', ascending=False, na_position='last') #sort by largest to smallest
df_merged['market_cap_percentage'] = df_merged['market_cap_percentage'].fillna(0)

#calculate the differences
df_merged['difference'] = df_merged['market_cap_percentage'] - df_merged['portfolio weights']

#compare market_cap_perc and df
print(market_cap)
df_merged = df_merged[(df_merged["free"] != 0) | (df_merged["market_cap_percentage"] != 0)]
print(df_merged)
df_merged = df_merged.reset_index(drop=True) # reset index


# -------------------------------------------------------------

# Start placing orders
from binance.enums import *

#threshold as we need to account for fees
threshold = 0.95
i=0
pf_value = df_merged['USDT'].sum()


# Test order
order = client.create_test_order(
            symbol= df_merged['symbol'][i],
            side=SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity = round(df_merged['difference'][i]*threshold*-1*pf_value,2)
            )
print(order)
# creating a test order returns an empty response by design if the order would be valid (see the official docs). 
# You would get an error in the response if there were a problem with it, so the fact that your response is empty means success.


# get all open orders
print(client.get_all_orders(symbol=df_merged['symbol'][i]))
#if this is empty then we have no open orders

# For Loop for Rebalancing (Work in Progress)

# If we have USDT in our portfolio, we cannot sell directly USDT i, but we buy other cryptos with it
for i in range(len(df_merged)):
    if df_merged['symbol'][i] == 'USDTUSDT':
        print(df_merged['symbol'][i] + ': will not execute this order')
    else:
        print(df_merged['symbol'][i] + ': will execute this order')






for i in range(len(df_merged)):
    #sell order
    if df_merged['difference'][i] < 0:
        order = client.create_test_order(
            symbol= df_merged['symbol'][i],
            side=SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity = round(df_merged['difference'][i]*threshold*-1*pf_value,2)
            )
        print(df_merged['symbol'][i] + ': sell order')
        print(order)
    #buy order
    if df_merged['difference'][i] > 0:
        order = client.create_test_order(
            symbol= df_merged['symbol'][i],
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity = round(df_merged['difference'][i]*threshold*pf_value,2)
            )
        print(df_merged['symbol'][i] +': buy order')
        print(order)




order = client.create_order(
    symbol='BNBBTC',
    side=SIDE_BUY,
    type=ORDER_TYPE_LIMIT,
    timeInForce=TIME_IN_FORCE_GTC,
    quantity=100,
    price='0.00001')


#without USDT
df_merged['symbol'] = df_merged['symbol'].str[:-4]
"""




