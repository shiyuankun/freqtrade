""" This is a wrapper for Cryptopia.co.nz API """


import json
import time
import hmac
import hashlib
import base64
import requests

# using requests.compat to wrap urlparse (python cross compatibility over 9000!!!)
from requests.compat import quote_plus

class Api(object):
    """ Represents a wrapper for cryptopia API """

    def __init__(self, api_key, api_secret, calls_per_second):
        self.key = api_key
        self.secret = api_secret
        self.interval_call_secs = 1.0 / calls_per_second
        self.public = ['GetCurrencies', 'GetTradePairs', 'GetMarkets',
                       'GetMarket', 'GetMarketHistory', 'GetMarketOrders', 'GetMarketOrderGroups']
        self.private = ['GetBalance', 'GetDepositAddress', 'GetOpenOrders',
                        'GetTradeHistory', 'GetTransactions', 'SubmitTrade',
                        'CancelTrade', 'SubmitTip', 'SubmitWithdraw', 'SubmitTransfer']
        self.noopen = ['GetTradePairChart']

    def api_query(self, feature_requested, get_parameters=None, post_parameters=None):
        """ Performs a generic api request """
        time.sleep(self.interval_call_secs)
        if feature_requested in self.private:
            url = "https://www.cryptopia.co.nz/Api/" + feature_requested
            post_data = json.dumps(post_parameters)
            headers = self.secure_headers(url=url, post_data=post_data)
            req = requests.post(url, data=post_data, headers=headers)
            if req.status_code != 200:
                try:
                    req.raise_for_status()
                except requests.exceptions.RequestException as ex:
                    return None, "Status Code : " + str(ex)
            req = req.json()
            return req
        elif feature_requested in self.public:
            url = "https://www.cryptopia.co.nz/Api/" + feature_requested + "/" + \
                  ('/'.join(i for i in get_parameters.values()
                           ) if get_parameters is not None else "")
            req = requests.get(url, params=get_parameters)
            if req.status_code != 200:
                try:
                    req.raise_for_status()
                except requests.exceptions.RequestException as ex:
                    return None, "Status Code : " + str(ex)
            req = req.json()
            return req
        elif feature_requested in self.noopen:
            url = "https://www.cryptopia.co.nz/Exchange/{}?tradePairId={}&dataRange={}&dataGroup={}&_={}".format(
                feature_requested, get_parameters['tradePairId'], get_parameters['dataRange'],\
                get_parameters['dataGroup'], get_parameters['_'])
            req = requests.get(url)
            if req.status_code != 200:
                try:
                    req.raise_for_status()
                except requests.exceptions.RequestException as ex:
                    return None, "Status Code : " + str(ex)
            req = req.json()
            return req

    def get_currencies(self):
        """ Gets all the currencies """
        return self.api_query(feature_requested='GetCurrencies')

    def get_tradepairs(self):
        """ GEts all the trade pairs """
        return self.api_query(feature_requested='GetTradePairs')

    def get_markets(self):
        """ Gets data for all markets """
        return self.api_query(feature_requested='GetMarkets')

    def get_market(self, market):
        """ Gets market data """
        return self.api_query(feature_requested='GetMarket',
                              get_parameters={'market': market})

    def get_history(self, market):
        """ Gets the full order history for the market (all users) """
        return self.api_query(feature_requested='GetMarketHistory',
                              get_parameters={'market': market})

    def get_orders(self, market):
        """ Gets the user history for the specified market """
        return self.api_query(feature_requested='GetMarketOrders',
                              get_parameters={'market': market})

    def get_ordergroups(self, markets):
        """ Gets the order groups for the specified market """
        return self.api_query(feature_requested='GetMarketOrderGroups',
                              get_parameters={'markets': markets})

    def get_balance(self, currency):
        """ Gets the balance of the user in the specified currency """
        return self.api_query(feature_requested='GetBalance',
                              post_parameters={'Currency': currency})

    def get_openorders(self, market):
        """ Gets the open order for the user in the specified market """
        return self.api_query(feature_requested='GetOpenOrders',
                              post_parameters={'Market': market})

    def get_deposit_address(self, currency):
        """ Gets the deposit address for the specified currency """
        return self.api_query(feature_requested='GetDepositAddress',
                              post_parameters={'Currency': currency})

    def get_tradehistory(self, market):
        """ Gets the trade history for a market """
        return self.api_query(feature_requested='GetTradeHistory',
                              post_parameters={'Market': market})

    def get_transactions(self, transaction_type):
        """ Gets all transactions for a user """
        return self.api_query(feature_requested='GetTransactions',
                              post_parameters={'Type': transaction_type})

    def submit_trade(self, market, trade_type, rate, amount):
        """ Submits a trade """
        return self.api_query(feature_requested='SubmitTrade',
                              post_parameters={'Market': market,
                                               'Type': trade_type,
                                               'Rate': rate,
                                               'Amount': amount})

    def cancel_trade(self, trade_type, order_id, tradepair_id):
        """ Cancels an active trade """
        return self.api_query(feature_requested='CancelTrade',
                              post_parameters={'Type': trade_type,
                                               'OrderID': order_id,
                                               'TradePairID': tradepair_id})

    def submit_tip(self, currency, active_users, amount):
        """ Submits a tip """
        return self.api_query(feature_requested='SubmitTip',
                              post_parameters={'Currency': currency,
                                               'ActiveUsers': active_users,
                                               'Amount': amount})

    def submit_withdraw(self, currency, address, amount):
        """ Submits a withdraw request """
        return self.api_query(feature_requested='SubmitWithdraw',
                              post_parameters={'Currency': currency,
                                               'Address': address,
                                               'Amount': amount})

    def submit_transfer(self, currency, username, amount):
        """ Submits a transfer """
        return self.api_query(feature_requested='SubmitTransfer',
                              post_parameters={'Currency': currency,
                                               'Username': username,
                                               'Amount': amount})

    def secure_headers(self, url, post_data):
        """ Creates secure header for cryptopia private api. """
        nonce = str(int(time.time()))
        md5 = hashlib.md5()
        jsonparams = post_data.encode('utf-8')
        md5.update(jsonparams)
        rcb64 = base64.b64encode(md5.digest()).decode('utf-8')
        
        signature = self.key + "POST" + quote_plus(url).lower() + nonce + rcb64
        hmacsignature = base64.b64encode(hmac.new(base64.b64decode(self.secret),
                                                  signature.encode('utf-8'),
                                                  hashlib.sha256).digest())
        header_value = "amx " + self.key + ":" + hmacsignature.decode('utf-8') + ":" + nonce
        return {'Authorization': header_value, 'Content-Type': 'application/json; charset=utf-8'}


    data_range_group = {
        'oneDay': (15, 30, 60, 120),
        'twoDays': (15, 30, 60, 120),
        'oneWeek': (60, 120, 240, 720),
        'twoWeeks': (120, 240, 720),
        'oneMonth': (240, 720, 1440),
        'threeMonths': (240, 720, 1440, 10080),
        'sixMonths': (720, 1440, 10080),
        'all': (1440, 10080)
    }
    
    def get_tickers(self, currency_id, tick_interval, tick_range):
        nonce = str(int(time.time()))
        datagroup = tick_interval
        if tick_interval == 1:
            datagroup = 1
        elif tick_interval <= 5:
            datagroup = 5
        elif tick_interval <= 15:
            datagroup = 15
        elif tick_interval <= 30:
            datagroup = 30
        elif tick_interval <= 60:
            datagroup = 60
        elif tick_interval <= 1440:
            datagroup = 1440

        if tick_range == 'oneDay':
            datarange = 0
        elif tick_range == 'twoDays':
            datarange = 1
            if datagroup < min(self.data_range_group[tick_range]):
                datagroup = min(self.data_range_group[tick_range])
        elif tick_range == 'oneWeek':
            datarange = 2
            if datagroup < min(self.data_range_group[tick_range]):
                datagroup = min(self.data_range_group[tick_range])
        elif tick_range == 'twoWeeks':
            datarange = 3
            if datagroup < min(self.data_range_group[tick_range]):
                datagroup = min(self.data_range_group[tick_range])
        elif tick_range == 'oneMonth':
            datarange = 4
            if datagroup < min(self.data_range_group[tick_range]):
                datagroup = min(self.data_range_group[tick_range])
            
        return self.api_query(feature_requested="GetTradePairChart",
                              get_parameters={"tradePairId": currency_id,
                                              "dataRange": datarange,
                                              "dataGroup": datagroup,
                                              "_": nonce
                              })
#        return self.api_query(https://www.cryptopia.co.nz/Exchange/GetTradePairChart?tradePairId=5207&dataRange=1&dataGroup=60&_=1519184378326

