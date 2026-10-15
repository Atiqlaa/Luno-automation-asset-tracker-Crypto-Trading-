import os
import time
import uuid
import requests
from datetime import datetime
import re
import sqlite3
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta, timezone

#Enter your Luno account API here, Full access
# https://guide.luno.com/hc/en-gb/articles/24590432698013-How-do-I-create-a-Luno-API-key
api_key_id = ''
api_key_secret = ''

conn = sqlite3.connect('crypto_assets.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS profit_statement (
    no INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    currency TEXT NOT NULL,
    buy_price REAL NOT NULL,
    sell_price REAL NOT NULL,
    profit REAL NOT NULL,
    sell_order_id REAL NOT NULL
    )""")

#UPDATE SQL 8/5

cur.execute("""CREATE TABLE IF NOT EXISTS buy_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE,
    client_order_id TEXT UNIQUE,
    date TEXT NOT NULL,
    asset TEXT,
    post_type,
    amount_myr REAL NOT NULL,
    amount_coin REAL NOT NULL,
    fee_counter REAL NOT NULL,
    buy_price REAL NOT NULL,
    status REAL NOT NULL,
    [order] TEXT DEFAULT 'Active',
    fee_base REAL NOT NULL,
    cancel TEXT DEFAULT 'False')""")

cur.execute('''CREATE TABLE IF NOT EXISTS sell_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE,
    client_order_id TEXT UNIQUE,
    date TEXT NOT NULL,
    asset TEXT,
    post_type,
    amount_myr REAL NOT NULL,
    amount_coin REAL NOT NULL,
    fee_counter REAL NOT NULL,
    sell_price REAL NOT NULL,
    status REAL NOT NULL,
    buy_order_id TEXT DEFAULT 'None',
    cancel TEXT DEFAULT 'False',
    FOREIGN KEY(buy_order_id) REFERENCES buy_orders(order_id))''')



conn.commit()


def convert_time(timestamp):
    sec = timestamp / 1000
    my_time = timezone(timedelta(hours=8))
    return datetime.fromtimestamp(sec, tz=my_time).strftime("%d-%m-%Y %I:%M:%S %p")
def save_profit(sell_order_id = None):
    sell_orders = cur.execute("SELECT * FROM sell_orders WHERE order_id = ?", (sell_order_id,)).fetchone()
    
    buy_order_id = sell_orders[11]
    buy_orders = cur.execute("SELECT * FROM buy_orders WHERE order_id = ?", (buy_order_id,)).fetchone()
    print(buy_order_id)
    print(buy_orders[6])
    total_belian_myr = round(buy_orders[6] + buy_orders[8],2)
    total_jualan_myr = round(sell_orders[6] + sell_orders[8],2)
    calculate = round(total_jualan_myr - total_belian_myr,2)
    
    cur.execute("""INSERT INTO profit_statement (date,currency,buy_price,sell_price,profit,sell_order_id) VALUES (?,?,?,?,?,?)""", (sell_orders[3],sell_orders[4],total_belian_myr,total_jualan_myr,calculate,sell_orders[1]))
    conn.commit()


def profit():
    a = cur.execute("SELECT * FROM profit_statement").fetchall()
    if not a:
        print('No profit saved')
        return
    no = a['no']
    date = a['date']
    currency = a['currency']
    buy_price = a['buy_price']
    sell_price = a['sell_price']
    profit = a['profit']
    sell_order_id = a['sell_order_id']

    print("(Profit/Loose Statements)")
    for row in a:
        print(f'{no}) Date: {date} | Coin : {currency}\nBuy Price: {buy_price} | Sell Price: {sell_price}\nProfit/Loose: {profit}Sell Order Id: {sell_order_id}')



def sync_pending_order():


    query = """ SELECT id, order_id, client_order_id, 'Buy' AS order_type FROM buy_orders WHERE status == 'AWAITING' or [status] = 'PENDING' and [cancel] = 'False'
    
    UNION ALL

    SELECT id, order_id, client_order_id, 'Sell' AS order_type FROM sell_orders WHERE status == 'AWAITING' or [status] = 'PENDING'"""

    cur.execute(query)

    pending_orders = cur.fetchall()
    


    if not pending_orders:
        return

    
    #Check semula untuk setiap order id yg status awating dalam data buys and sell orders
    for row in pending_orders:
        db_id,order_id,client_order_id,order_type = row
        params = {'id':order_id,'client_order_id': client_order_id}
        print(order_id)

        try:
            print('NEXT')
            reqs = requests.get(
                'https://api.luno.com/api/exchange/3/order', 
                auth=HTTPBasicAuth(api_key_id, api_key_secret), 
                params=params).json()
         
            if 'error' in reqs:
                continue


            current_status = reqs.get('status')
            amount_myr = float(reqs['counter'])
            side = reqs['side']

            if current_status == 'COMPLETE' and amount_myr >= 1:
                date = convert_time(reqs['completed_timestamp'])
                amount_myr = float(reqs['counter'])
                amount_coin_includefee = float(reqs['base'])
                fee_base = float(reqs['fee_base'])
                amount_coin = float(amount_coin_includefee - fee_base)
                fee_percent = fee_base / amount_coin_includefee 
                fee_counter = fee_percent * amount_myr
                price = amount_myr / amount_coin_includefee

                if side == "BUY":

                    cur.execute("""
                        UPDATE buy_orders 
                        SET date = ?, amount_myr = ?, amount_coin = ?, fee_counter = ?, buy_price = ?, status = ?, fee_base = ?, [order] = ?
                        WHERE id = ?
                    """, (date, amount_myr, amount_coin, fee_counter, price, 'COMPLETE',fee_base, 'Active', db_id))
                    conn.commit()
                    print(f'Order berjaya')
                elif side == "SELL":
                    cur.execute("""
                        UPDATE sell_orders 
                        SET date = ?, amount_myr = ?, amount_coin = ?, fee_counter = ?, buy_price = ?, status = ?, fee_base = ?
                        WHERE id = ?
                    """, (date, amount_myr, amount_coin, fee_counter, price, 'COMPLETE',fee_base, db_id))
                    conn.commit()
                    buy_order_id = cur.execute("SELECT buy_order_id FROM sell_orders WHERE id = ?", (db_id,)).fetchone()
                    cur.execute("UPDATE buy_orders SET [order] = 'Unactive' WHERE order_id = ?", (buy_order_id,))
                    conn.commit()
                    

            elif current_status == "COMPLETE" and amount_myr <= 0: # ciri cancel, amount 0 semua walaupun complete
                if side == "BUY":
                    print(db_id)
                    cur.execute("UPDATE buy_orders SET cancel = 'True', status = 'COMPLETE', [order] = 'Unactive' WHERE id = ?", (db_id,))
                    conn.commit()
                    
                elif side == "SELL":
                    cur.execute("UPDATE sell_orders SET cancel = 'True', status = 'COMPLETE', [order] = 'Unactive' WHERE id = ?", (db_id,))
                    conn.commit()
                    
        except Exception as E:
            print(E)

sync_pending_order()


def buys(post_type,order_id=None,client_order_id=None):
    #def ini dipanggil hanya di def post_market 
    params = {'id': None,
                  'client_order_id' : None}
    
    if order_id != None:
        try:
            params['id'] = order_id
        except Exception as E:
                print(E)
            
    elif client_order_id != None:
        try:
            params['client_order_id'] = client_order_id
        except Exception as E:
            print(E)
    else:
        print('Gagal track order, please masukkan params salah satunya')
    print(params)
    reqs = requests.get('https://api.luno.com/api/exchange/3/order', auth=HTTPBasicAuth(api_key_id,api_key_secret), params=params).json()
    print(reqs)
    fee_percent = 0
    fee_counter = 0
    price = 0
    status = reqs['status']
    date = convert_time(reqs['completed_timestamp'])
    pair = reqs['pair']
    amount_myr = float(reqs['counter']) #termasuk fee
    amount_coin_includefee = float(reqs['base']) #termasuk fee
    fee_base = float(reqs['fee_base'])
    amount_coin = float(amount_coin_includefee - fee_base)
    if fee_base or amount_coin_includefee > 0:
        fee_percent = fee_base/amount_coin_includefee
        fee_counter = fee_percent*amount_myr
        price = amount_myr/amount_coin_includefee

    percent = 0.0035

    limit_price = float(reqs['limit_price'])
    limit_amount_coin = float(reqs['limit_volume'])
    limit_amount_myr = float(limit_price*limit_amount_coin)
    limit_fee_myr = float(limit_amount_myr*percent)
    limit_fee_coin = float(limit_amount_coin*percent)
    
    

    #print(date, pair,amount_myr,amount_coin_includefee,fee_base,amount_coin,fee_percent,fee_counter,price)

    try:
        if post_type == "Market":
            cur.execute("""INSERT INTO buy_orders (order_id,client_order_id,date,asset,post_type,amount_myr,amount_coin,fee_counter,buy_price,status,fee_base) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (order_id,client_order_id,date,pair,post_type,amount_myr,amount_coin,fee_counter,price,status,fee_base))
            conn.commit()
            print('save data market')
        if post_type == 'Limit':
            cur.execute("""INSERT INTO buy_orders (order_id,client_order_id,date,asset,post_type,amount_myr,amount_coin,fee_counter,buy_price,status,fee_base) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (order_id,client_order_id,date,pair,post_type,limit_amount_myr,limit_amount_coin,limit_fee_myr,limit_price,status,limit_fee_coin))
            conn.commit()
            print('save data limit')
    except Exception as E:
        print(E)

def sells(post_type,order_id=None,client_order_id=None,order_activeID=None):
    #def ini dipanggil hanya di def post_market dengan post_limit
    params = {'id': None,
                  'client_order_id' : None}
    
    if order_id != None:
        try:
            params['id'] = order_id
        except Exception as E:
                print(E)
    elif client_order_id != None:
            params['client_order_id'] = client_order_id

    else:
        print('Gagal track order, please masukkan params salah satunya')
    
    reqs = requests.get('https://api.luno.com/api/exchange/3/order', auth=HTTPBasicAuth(api_key_id,api_key_secret), params=params).json()
    print(reqs)

    fee_percent = 0
    fee_counter = 0
    price = 0
    status = reqs['status']
    date = convert_time(reqs['completed_timestamp'])
    pair = reqs['pair']
    amount_myr = float(reqs['counter']) #termasuk fee
    amount_coin_includefee = float(reqs['base']) #termasuk fee
    fee_base = float(reqs['fee_base'])
    amount_coin = float(amount_coin_includefee - fee_base)
    if fee_base or amount_coin_includefee > 0:
        fee_percent = fee_base/amount_coin_includefee
        fee_counter = fee_percent*amount_myr
        price = amount_myr/amount_coin_includefee

    try:
        if post_type == "Market":
            cur.execute("""INSERT INTO sell_orders (order_id,client_order_id,date,asset,post_type,amount_myr,amount_coin,fee_counter,sell_price,status,buy_order_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (order_id,client_order_id,date,pair,post_type,amount_myr,amount_coin,fee_counter,price,status,order_activeID))
            
            conn.commit()
            print('save data market')
        
        if post_type == 'Limit':
            cur.execute("""INSERT INTO sell_orders (order_id,client_order_id,date,asset,post_type,amount_myr,amount_coin,fee_counter,sell_price,status,buy_order_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (order_id,client_order_id,date,pair,post_type,amount_myr,amount_coin,fee_counter,price,status,order_activeID))
            conn.commit()
            print('save data limit')
    except Exception as E:
        print(E)
                    



query={
    "min_row":-100,
    "max_row":0
}

def convert_fee(fee,price):
    fees = fee * price
    return fees
def split_harga(string):
    print(string)
    splits = str(string).replace(',','')
    split = re.search(r'\d+\.?\d*', splits)
    return float(split.group()) if split else 'Gagal split harga'

def cancel_order(order_id):
    reqs = requests.post('https://api.luno.com/api/1/stoporder', auth=HTTPBasicAuth(api_key_id,api_key_secret), data={'order_id':order_id})
    if reqs.status_code == 200:
        print(f'Order ({order_id}) telah dibatalkan!')
    sync_pending_order()


def post_market(pair,types,volume,buy_order_id = None):
    client_order_id=f'ord-{uuid.uuid4().hex[:13]}'
    if types.upper() in ('BUY','BID'):

        reqs= requests.post('https://api.luno.com/api/1/marketorder',auth=HTTPBasicAuth(api_key_id,api_key_secret),data = {
                'pair': pair+'MYR'
                ,'type':types
                ,'counter_volume':volume #wang myr
                ,'client_order_id':client_order_id
            })
        if reqs.status_code == 200:
            print(f'Post Market - BUY - OrderId:{client_order_id}')
            data = reqs.json()
            order_id = data['order_id']      
            buys(post_type ='Market',order_id=order_id,client_order_id=client_order_id)
        else:
            print('Gagal melaksanakan pesanan marketbuy!')
            return  
    elif types.upper() in ('SELL', 'ASK'):
        reqs= requests.post('https://api.luno.com/api/1/marketorder',auth=HTTPBasicAuth(api_key_id,api_key_secret),data= {
                'pair': pair+'MYR'
                ,'type':types
                ,'base_volume':round(volume,4) #mata crypto
                ,'client_order_id':client_order_id
            })
        print(f'{pair},{types},{volume},{client_order_id}')
        print(reqs.status_code)
        if reqs.status_code == 200:
    
            data = reqs.json()
            order_id = data['order_id'] 
            print(f'Post Market - SELL - OrderId:{client_order_id}')

            if buy_order_id is not None:
                sells(post_type='Market',order_id=order_id,client_order_id=client_order_id,order_activeID=buy_order_id)
                cur.execute("""UPDATE buy_orders SET [order] = 'Unactive' WHERE order_id = ?""", (buy_order_id,))
                save_profit(sell_order_id=order_id)
                conn.commit()
            else:
                sells(post_type='Market',order_id=order_id,client_order_id=client_order_id)
        else:
            print('Gagal melaksanakan pesanan (postmarket def)!')
            return  
def post_limit(pair,types,volume,price,stopprice=None,stopdirection=None,postonly_mode=None,buy_order_id=None):
    
    params={
        'pair': pair+'MYR',
        'type':types, 
        # BID for a bid (buy) limit order
        # ASK for an ask (sell) limit order
        'volume':volume, #crpto amount
        'price':price
        ,'client_order_id':f'ord-{uuid.uuid4().hex[:13]}'
    }

    if stopprice != None and str(stopprice.strip()) != "":  

        params['stop_price'] = float(stopprice)
        params['stop_direction'] = 'RELATIVE_LAST_TRADE'
    else:
        params['stop_price'] = None
    if postonly_mode != None:
        params['post_only'] = 'True'
    
    #BID buy limit order (types)
    #ASK sell limit order (types)
    reqs = requests.post('https://api.luno.com/api/1/postorder',auth=HTTPBasicAuth(api_key_id,api_key_secret),data=params)
    data = reqs.json()
    order_id = data['order_id']
    print(f'sini data{data}')
    print(f'Status Code: {reqs.status_code}\n Order Id: {data["order_id"]}')
    if reqs.status_code == 200:
        if types.lower() == 'bid':
            buys(post_type='Limit',order_id=data['order_id'])
        elif types.lower() == 'ask':
            if buy_order_id is not None:
                sells(post_type='Limit', order_id=data['order_id'],order_activeID=buy_order_id)
                #cur.execute("""UPDATE buy_orders SET [order] = 'Unactive' WHERE order_id = ?""", (buy_order_id,))
                save_profit(order_id)
            else:
                sells(post_type='Limit', order_id=data['order_id'])
    else:
        print('Gagal melaksanakan pesanan limit!')
        return      
def pending_orders():
    print('Check pending order...')
    sync_pending_order()

    #Pending Market
    
    try:  
        buy_orders_data = cur.execute("SELECT id, order_id, asset, amount_myr, amount_coin, buy_price FROM buy_orders WHERE [status] ==  'AWAITING' or [status] = 'PENDING'").fetchall()
        sell_orders_data = cur.execute("""SELECT id, order_id, asset, amount_myr, amount_coin, sell_price FROM sell_orders WHERE [status] == 'AWAITING' or [status] = 'PENDING'""").fetchall()
        if not buy_orders_data and not sell_orders_data:
            print('Tiada order pending...')
            return
        
        print('Pending order lists:-\n')
        for ord in buy_orders_data:
            id = ord['id']
            orderid = ord['order_id']
            asset = ord['asset']
            amount_myr = ord['amount_myr']
            amount_coin = ord['amount_coin']
            buy_price = ord['buy_price']
            print(f'{id}) Order Id: {orderid} | Asset: {asset} | Amount MYR: {amount_myr} | Amount Coin: {amount_coin} | Buy Price: {buy_price}')


        for ord in sell_orders_data:
            id = ord['id']
            orderid = ord['order_id']
            asset = ord['asset']
            amount_myr = ord['amount_myr']
            amount_coin = ord['amount_coin']
            sell_price = ord['sell_price']
            print(f'{id}) Order Id: {orderid} | Asset: {asset} | Amount MYR: {amount_myr} | Amount Coin: {amount_coin} | Jual Price: {sell_price}')

    except Exception as E:
        print('Gagal mencari order pendisng!')
        print(E)


# Function work perfectly
def listing_transaction():
    id_coin = requests.get(f'https://api.luno.com/api/1/balance', auth=HTTPBasicAuth(api_key_id,api_key_secret))
    #check accound id yg pelbagai aset/jenis account
    list_input = input('List all assets? ( Keep it blank if yes) Or Choosen Assets ( No )\n> ')
    if list_input.lower() == 'no': #List kan asset khusus
        loop_stop = False

        print('Jenis asset yg ada :-')
        counter = 0
        transcational_assets = []
        stacking_assets = []
        list_transaction = []
        data_staking = []
        for id in id_coin.json().get('balance'):
            #list_asset.append({'account_id': , 'asset':})
            if id['account_type'] == 'STAKING':
                stacking_assets.append({'asset':id.get('asset'), 'account_id': id.get('account_id')})
            if id['account_type'] == 'TRANSACTIONAL':
                #List asset jenis transcational yg ada
                coin = id.get('asset')              
                transcational_assets.append({'asset':coin, 'account_id': id.get('account_id')})
                counter+=1
                print(f'{counter}) {coin}')
        #Ambil melalui value variable, bukan nombor dict
        print('\nSelect the number of asset')
        number = int(input('Number: '))
        number-=1
        selection = transcational_assets[number] 

        b = requests.get(f"https://api.luno.com/api/1/accounts/{selection['account_id']}/transactions", auth=HTTPBasicAuth(api_key_id,api_key_secret),params=query)
        for a in stacking_assets:
            if a['asset'] == selection['asset']:
                c = requests.get(f"https://api.luno.com/api/1/accounts/{a['account_id']}/transactions", auth=HTTPBasicAuth(api_key_id,api_key_secret),params=query)
                data_staking = c.json().get('transactions') or {}
        data_transaction = b.json().get('transactions') or {}
        combine_transaction = data_transaction + data_staking
        page = 1
        transaction_count = 0
        if combine_transaction:
            for t in combine_transaction:
                
                if loop_stop:
                     print('>> Keluar dari page <<')
                     break
                
                currency=t.get('currency')
                balance = t.get('balance')
                desc = t.get('description')
                time = t.get('timestamp')

                
                
                detail_fields = t.get('detail_fields') or {}
                trade_details = detail_fields.get('trade_details') or {}
                types = t.get('type')
                kind = t.get('kind')
                # if types in (4,5): YG INI TAK GUNA, SEBAB INI NOISE SAHAJA
                #     #reserved/released funds
                #     print(f"Category: Reserved, Released Funds\nJumlah Baki: {t.get('balance')}\nJumlah baki yg boleh diguna: {t.get('available_delta')} {currency}\nDescription: {t.get('description')}")
                if kind == 'EXCHANGE':
                    #type 7
                    if types == 7:
                        details = t.get('details')
                        
                        transaction_count += 1
                        print('\n')
                        print('-' * 30)
                        print(f'{convert_time(time)}\nAsset: {currency}')
                        #Belian di exchange
                        pair = trade_details.get('pair')
                        harga_beli = float(trade_details.get('price'))
                        print(f'Belian di Orderbook/Exchange')
                        amount = float(trade_details.get('volume')) # ni jumlah coin yg dibeli/jual, bukan volume user
                        print(f"Asset: {pair}, Harga beli:  {harga_beli:.2f} , Amount Coin: {amount:.5f} (RM {split_harga(details.get('Approximate value'))})") 

                        
                               
                    elif types == 6:
                        details = t.get('details', {})
                        
                        transaction_count += 1
                        print('\n')
                        print('-' * 30)
                        print(f'{convert_time(time)}\nAsset: {currency}')
                        #jual
                        pair = trade_details.get('pair')
                        harga_jual = float(trade_details.get('price'))
                        print(f'Jualan di Orderbook/Exchange')
                        amount = float(trade_details.get('volume'))
                        print(f"Asset: {pair}, Harga jual: {harga_jual:.2f} MYR, Amount: {amount:.5f} (RM {split_harga(details.get('Approximate value'))})")
                        foreign_id = t.get('foreign_id')

                elif kind == 'TRANSFER' and t.get('details'):
                    details = t.get('details') or {}
                    
                    transaction_count += 1
                    print('\n')
                    print('-' * 3)
                    print(f'{convert_time(time)}\nAsset: {currency}')
                    print(f'{t.get("description")}, Value: RM {split_harga(details.get("Approximate value") or {})}')
                elif types == 15:
                   
                    transaction_count += 1
                    print('\n')
                    print('-' * 30)
                    print(f'{convert_time(time)}\nAsset: {currency}')
                    #INSTANT BUY
                    instant_details = t.get('details') or {}
                    harga_str = instant_details.get('Price')
                    fee = split_harga(t.get('details').get('Fee'))
                    price = split_harga(t.get('details').get('Price')) 
                    print(f'Belian Instant sebanyak {t.get("details").get("Approximate value") or {}} dengan harga {price}, Fee: RM {fee*price}')
                    foreign_id = t.get("foreign_id")
                           
                jumlah_list = 2
                if kind in ('EXCHANGE', 'TRANSFER') or types == 15:
                    if transaction_count > 0 and transaction_count % jumlah_list == 0:
                        print(f'\n---------- PAGE ({page}) ----------')
                        page+=1
                        print('( Taip "q" untuk keluar )')
                        choice = input ('Tekan enter untuk buka page seterusnya ->')
                        
                        if choice.lower() == 'q':
                            loop_stop = True
        

    else:
        loop_stop = False
        transaction_count = 0
        page = 1
        for id in id_coin.json().get('balance'):
            if loop_stop:
                print('>> Keluar dari page <<')
                break
            a = requests.get(f"https://api.luno.com/api/1/accounts/{id.get('account_id')}/transactions", auth=HTTPBasicAuth(api_key_id,api_key_secret),params=query)
            data=a.json()
            list_transaction=data.get('transactions') or {}
            if list_transaction:
                for t in list_transaction:
    
                    currency=t.get('currency')
                    balance = t.get('balance')
                    desc = t.get('description')
                    time = t.get('timestamp')


                    detail_fields = t.get('detail_fields') or {}
                    trade_details = detail_fields.get('trade_details') or {}
                    types = t.get('type')
                    kind = t.get('kind')
                    # if types in (4,5): YG INI TAK GUNA, SEBAB INI NOISE SAHAJA
                    #     #reserved/released funds
                    #     print(f"Category: Reserved, Released Funds\nJumlah Baki: {t.get('balance')}\nJumlah baki yg boleh diguna: {t.get('available_delta')} {currency}\nDescription: {t.get('description')}")
                    if kind == 'EXCHANGE':
                        #type 7
                        if types == 7:
                            details = t.get('details')
                            transaction_count += 1
                            print('\n')
                            print('-' * 30)
                            print(f'{convert_time(time)}\nAsset: {currency}')
                            #Belian di exchange
                            pair = trade_details.get('pair')
                            harga_beli = float(trade_details.get('price'))
                            print(f'Belian di Orderbook/Exchange')
                            amount = float(trade_details.get('volume')) # ni jumlah coin yg dibeli/jual, bukan volume user
                            print(f"Asset: {pair}, Harga beli:  {harga_beli:.2f}, Amount Coin: {amount:.5f} (RM {split_harga(details.get('Approximate value'))})") 

                            foreign_id = t.get('foreign_id')
                                   
                        elif types == 6:
                            details = t.get('details')
                            transaction_count += 1
                            print('\n')
                            print('-' * 30)
                            print(f'{convert_time(time)}\nAsset: {currency}')
                            
                            #jual
                            pair = trade_details.get('pair')
                            harga_jual = float(trade_details.get('price'))
                            print(f'Jualan di Orderbook/Exchange')
                            amount = float(trade_details.get('volume'))
                            print(f"Asset: {pair}, Harga jual:  {harga_jual:.2f} MYR, Amount: {amount:.5f} (RM {split_harga(details.get('Approximate value'))})") 
                            # save_transaction(currency,time,amount,harga_jual,action='Sell',status='Non-Active')
                            foreign_id = t.get('foreign_id')
                            
                            #sells(foreign_id=foreign_id,date=time,asset=pair,amount_sold=amount,sell_price=harga_jual,matched_buy_id=None)

                            #save_transaction(currency,)
                    elif kind == 'TRANSFER' and t.get('details'):
                            details = t.get('details') or {}

                            transaction_count += 1
                            print('\n')
                            print('-' * 30)
                            print(f'{convert_time(time)}\nAsset: {currency}')
                            print(f'{t.get("description")}, Value: RM {split_harga(details.get("Approximate value") or {})}')
                    elif types == 15:

                            #INSTANT BUY
                            transaction_count += 1
                            print('\n')
                            print('-' * 30)
                            print(f'{convert_time(time)}\nAsset: {currency}')

                            instant_details = t.get('details') or {}
                            harga_str = instant_details.get('Price')
                            fee = split_harga(t.get('details').get('Fee'))
                            price = split_harga(t.get('details').get('Price'))
                            print(f'Belian Instant sebanyak {t.get("details").get("Approximate value") or {}} dengan harga {price}, Fee: RM {fee*price}') 
                            
                    jumlah_list= 2
                    if kind in ('EXCHANGE', 'TRANSFER') or types == 15:
                        if transaction_count > 0 and transaction_count % jumlah_list == 0:
                            print(f'\n---------- PAGE ({page}) ----------')
                            page+=1
                            print('( Taip "q" untuk keluar )')
                            choice = input ('Tekan enter untuk buka page seterusnya ->')
                            if choice.lower() == 'q':
                                loop_stop = True

def sell_order(id,asset):
    active_order = cur.execute('SELECT amount_coin,order_id FROM buy_orders WHERE id = ? AND asset = ?', (id,asset,)).fetchone()
    if not active_order:
        print('Order yg dipilih tidak dijumpai di list order yg active')
        return None, None
    buy_order_id = active_order[1]
    amount_coin = active_order[0]
    return amount_coin,buy_order_id
def calculate(asset_calculate=None):
#LIST PROFIT/LOOSE DARI BELIAN YG 'ACTIVE' DARI DATA TRANSACTION
#Buat perbandingan dgn live harga coin
#Kira yg transaction dari luno, bukan terminal
    if asset_calculate != None:
        data_crypto = cur.execute('SELECT * FROM buy_orders WHERE [order] = "Active" AND [status] = "COMPLETE" AND cancel = "False" AND asset = ?',(asset_calculate,)).fetchall()
        print(f'ni active {data_crypto}')
        if not data_crypto:
            return False
    else:
        data_crypto = cur.execute('SELECT * FROM buy_orders WHERE [order] = "Active" AND cancel = "False" AND [status] = "COMPLETE"').fetchall()

        if not data_crypto:
            return False
    conn.commit()
    print('List belian yang active:-')
    for datacrypto in data_crypto:
        iddata = datacrypto[0]
  
        order_id = datacrypto[1]
        amount_myr = datacrypto[6]
        amounts = float(datacrypto[7])
        asset = datacrypto[4]
        price = datacrypto[9]
        time = datacrypto[3]
        ticker= requests.get('https://api.luno.com/api/1/ticker', auth=HTTPBasicAuth(api_key_id,api_key_secret),params={'pair':asset})
        tkers = ticker.json().get('last_trade')  
        tkers = float(tkers)
        price = float(price)
        untung_rugi_myr = float(tkers - price) * amounts
        print(f'\n{iddata}) Asset: {asset} | Harga beli dulu: {price} | Harga sekarang: {tkers} | Amount coin: {amounts} | Amount ringgit: {amount_myr:.2f} MYR')
        peratus = (tkers - price) / price * 100
        if peratus > 0:
            print(f'UNTUNG {untung_rugi_myr:.2f} {peratus:.2f}%')
        else:
            print(f'RUGI {untung_rugi_myr:.2f} MYR, {peratus:.2f}%')                    
            #print(f'( Belian secara Instant)\nHarga belian: {price}\nFee: {convert_fee(fee,price):.2f} MYR')             )
    #disini tak bleh untuk jual, sebab kerumitan dalam pilih post limit/market
def get_balance():
    u = requests.get("https://api.luno.com/api/1/balance", auth=HTTPBasicAuth(api_key_id,api_key_secret))
    print("Menghantar..")
    data=u.json()
    for acc in data["balance"]:
        account_type = acc['account_type']
    
        print(f"Coin: {acc['asset']}")
        print(f"Acoount types: {account_type}")
        print(f"Dipegang: {acc['reserved']}")
        print(f"Total: {acc['balance']}")
        available= (float(acc['balance']) - float(acc['reserved']))
        print(f"Baki: {available:.6f}")
        print("-" * 20)   

def market_price(coin):
    params = {
        'pair': coin.upper() + 'MYR'
    }
    reqs = requests.get("https://api.luno.com/api/1/trades", auth=HTTPBasicAuth(api_key_id,api_key_secret), params=params).json().get('trades')
    
    for t in reqs:
    
        date = convert_time(int(t['timestamp']))
        price = float(t['price'])
        price = round(price,2)
        amount = round(float(t['volume']),4)

        
        buy_mode = t['is_buy']
        print(f'{date}')
        if buy_mode == True:
            print(f'Price: {price} (Buying)')
        else:
            print(f'Price: {price} (Sell)')
        print(f'Amount: {amount}\n')



def live_market(coin):

    seen_trade = set()
    is_first_run = True
    timesleep = 2



    
    while True:
        try:
            params = {'pair': coin.upper() + "MYR"}
            url = "https://api.luno.com/api/1/trades"
            
            response = requests.get(url, auth=HTTPBasicAuth(api_key_id, api_key_secret), params=params)           

            if response.status_code == 200:
                trades = response.json().get('trades', [])
                trades = sorted(trades,key = lambda x: int(x['timestamp']))
                
                new_trades_found = False

                for t in trades:
                    date = convert_time(int(t['timestamp']))
                    price = float(t['price'])
                    price = round(price,2)
                    amount = round(float(t['volume']),6)
                    trade_uniqie_id = f"{date}-{price}-{amount}"
                    buy_mode = t['is_buy']

                    if is_first_run:
                        seen_trade.add(trade_uniqie_id)
                        if buy_mode:
                            action = f'🟢 BUY ({coin.upper()})'
                        else:
                            action = f'🔴 SELL({coin.upper()})'

                        print("-"*15)
                        print(f'{date}\nPrice: {price}\nAmount: {amount}\n{action}')
                        
                    elif trade_uniqie_id not in seen_trade:
                        seen_trade.add(trade_uniqie_id)

                        if buy_mode:
                            action = f'🟢 BUY ({coin.upper()})'
                        else:
                            action = f'🔴 SELL ({coin.upper()})'

                        print("-"*15)
                        print(f'{date}\nPrice: {price}\nAmount: {amount}\n{action}')
                        

                        new_trades_found = True
                if is_first_run:
                    is_first_run = False
            else:
                print("Failed API: {response.status_code}")
        except requests.exceptions.RequestException as err:
            time.sleep(5)
        except requests.exceptions.Timeout as e:
            print(f'Timeout! Cuba menyambung semula..')
            time.sleep(5)
            continue
        except requests.exceptions.ConnectionError as e:
            print(f'Masalah sambungan internet! Cuba semula dalam 5 saat...')
            time.sleep(5)
            continue


        time.sleep(timesleep)

while True:     
    print(f'\nSelect the numbers below :)\n')
    print('1) Check balance\n2) List transaction\n3) Profit-Loose for active orders\n4) Post limit order\n5) Post market order \n6) Pending orders \n7) Cancel the order\n8) Profit & Loss Statements\n9) Market Live')
    user = input('> ')
    if str(user) == '1': #Check balance
        get_balance()
    elif str(user) == '2': #List transaction luno
        listing_transaction()
    elif str(user) == '3': #P/L from Luno 
        calculate()
    elif str(user) == '4': #POST LIMIT 
        print(f'( Post Limit )\nSilakan isi dibawah')
        coin = input('Coin: ')
        types = input('Bid/Ask: ')
        amount = 0
        stopprice_mode = None
        price = 0
        if types.lower() == 'bid':
                    amount_myr = int(input('MYR: '))
                    price = float(input('Price: '))
                    amount = amount_myr/price
                    print(f'Amount myr ke coin {amount}')
                    stopprice_mode = input('Keep it blank if you dont want to set up Stop Price\nStop Price:')
        elif types.lower() == 'ask':
            pilih_jual = input('Jual order yg active? Y/N')
            if pilih_jual.lower() == 'y': #jual amount yg di order active
                print('Mencari order yg active untuk asset...')
                cal = calculate(asset_calculate=coin.upper()+'MYR')
                if cal == False:
                    print('Tiada order yg active')
                    break
                id_jual = input('Pilih nk jual yg mana satu: ')
                amount, buy_order_id = sell_order(id_jual, asset=coin.upper()+'MYR')
                if amount == None:
                    break
                price = input('Price: ')
                stopprice_mode = input('Keep it blank if you dont want to set up Stop Price\nStop Price:')
                print(f'Sila double confirm!, Coin: {coin}, Mode: {types}, Amount Coin: {amount}, Price: {price}, Stop Price: {stopprice_mode}')
                confirm = input('Confirm? Y/N')
                if confirm == 'y':
                        post_limit(coin.upper(),types.upper(),amount,price,stopprice_mode,buy_order_id=buy_order_id)
                        print(f'Coin: {coin}, Mode: {types}, Amount Coin: {amount}, Price: {price}, Stop Price: {stopprice_mode}, ( Selling Active Order )')
                        break
            else: #amount sendiri tetapkan != amount order active
                amount = input('Amount Coin:')
                price = input('Price: ')
                stopprice_mode = input('Keep it blank if you dont want to set up Stop Price\nStop Price:')
        print(f'Sila double confirm!, Coin: {coin}, Mode: {types}, Amount Coin: {amount}, Price: {price}, Stop Price: {stopprice_mode}')
        confirm = input('Confirm? Y/N')
        if confirm.lower() == 'y':    
            o = post_limit(coin.upper(),types.upper(),round(amount,4),price,stopprice_mode)
            print('Done post limit!')

        
    elif str(user) == '5': #POST MARKET
        print(f'( Post Market )\nSilakan isi dibawah')
        print('Noted! Untuk belian, amount dalam unit ringgit, untuk jualan, amount dalam unit coin')
        coin = input('Coin: ')
        types = input('Buy/Sell: ')
        amount = 0
        if types.lower() == 'buy':
            amount_myr = int(input('MYR: '))
            amount = amount_myr
        elif types.lower() == 'sell':
            pilih_jual = input('Jual order yg active? Y/N')
            if pilih_jual.lower() == 'y':
                print('Mencari order yg active untuk asset...')
                cal = calculate(asset_calculate=coin.upper()+'MYR')
                if cal == False:
                    print('Tiada order yg active')
                    break
                id_jual = input('Pilih nk jual yg mana satu: ')
                amount, buy_order_id = sell_order(id_jual, asset=coin.upper()+'MYR')
                #Cari order_id order,
                if amount == False:
                    break
                print(f'Sila double confirm!, Coin: {coin}, Mode: {types}, Sebanyak: {amount}, Jenis Transaksi: Post Market')
                confirm = input('Confirm? Y/N')
                if confirm == 'y':
                        post_market(coin.upper(),types.upper(),amount,buy_order_id=buy_order_id)
                        print(f'Coin: {coin}, Mode: {types}, Sebanyak: {amount}, Order yg dipilih: {id_jual}, Jenis Transaksi: Post Market')
                        break
            else:
                amount_coin = int(input('Amount coin:'))                
                amount = amount_coin
        print(f'Sila double confirm!, Coin: {coin}, Mode: {types}, Sebanyak: {amount}, Jenis Transaksi: Post Market')
        confirm = input('Confirm? Y/N')
        if confirm == 'y':
            post_market(coin.upper(),types.upper(),amount)
            print(f'Coin: {coin}, Mode: {types}, Sebanyak: {amount}, Jenis Transaksi: Post Market')
    elif str(user) == '7': #
        order_id = input('Cancel Order\nOrder_Id: ')
        confirm = input(f'Confirm? Y/N: ')
        if confirm.lower() == 'y':
            cancel_order(order_id)
    elif str(user) == '6':
        pending_orders()
    elif str(user) == '8':
        profit()
    elif str(user) == '9':
        print('Live Market')
        coin = input('Coin:')
        live_market(coin=coin)
    else:
        os.system('cls' if os.name == 'nt' else 'clear')
        print('Please masukkan nombor yg ada pada senarai!\n')
        time.sleep(1)    
        os.system('cls' if os.name == 'nt' else 'clear')

if __name__ == '__main__':
    live_market()
