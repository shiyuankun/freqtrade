import logging
from typing import Dict, List, Optional

from freqtrade.exchange.cryptopiaapi import Api as _Cryptopia

from requests.exceptions import ContentDecodingError

from freqtrade import OperationalException
from freqtrade.exchange.interface import Exchange

import time

logger = logging.getLogger(__name__)

_API: _Cryptopia = None
_EXCHANGE_CONF: dict = {}

class Cryptopia(Exchange):
    """
    Cryptopia API wrapper.
    """
    # Base URL and API endpoints

    def __init__(self, config: dict) -> None:
        global _API, _API_V2, _EXCHANGE_CONF
        _EXCHANGE_CONF.update(config)
        _API = _Cryptopia(
            api_key = _EXCHANGE_CONF['key'],
            api_secret = _EXCHANGE_CONF['secret'],
            calls_per_second = 1
            )
        self.cached_ticker = {}
        self.cached_pair_id = {}
        self.open_order = {}
    @staticmethod
    def _validate_response(response) -> None:
        """
        Validates the given cryptopia response
        and raises a ContentDecodingError if a non-fatal issue happend.
        """
        temp_error_messages = [
            'Currency not found.',
            ]

        if response['Error'] in temp_error_messages:
            raise ContentDecodingError('Got {}'.format(response['Error']))

    @property
    def fee(self) -> float:
        # 0.2 %: See https://www.cryptopia.co.nz/Forum/Thread/6022
        return 0.002        
    def add_openorder(self, orderid: str, market: str) -> None:
        self.open_order[orderid] = market

    def del_openorder(self, orderid: str, market: str) -> None:
        self.open_order.pop(orderid)
        
    def buy(self, pair: str, rate: float, amount: float) -> str:
        data = _API.submit_trade(pair, 'Buy', rate, amount)
        if not data['Success']:
            Cryptopia._validate_response(data)
            raise OperationalException('{message} params=({pair}, {rate}, {amount})'.format(
                message=data['Error'],
                pair=pair,
                rate=rate,
                amount=amount))
        orderid = data['Data']['OrderId']
        self.add_openorder(orderid, pair)
        return orderid

    def sell(self, pair: str, rate: float, amount: float) -> str:
        data = _API.SubmitTrade(pair, 'Sell', rate, amount)
        if not data['Success']:
            Cryptopia._validate_response(data)
            raise OperationalException('{message} params=({pair}, {rate}, {amount})'.format(
                message=data['Error'],
                pair=pair,
                rate=rate,
                amount=amount))
        orderid = data['Data']['OrderId']
        self.add_openorder(orderid, pair)
        return orderid

    def get_balance(self, currency: str) -> float:
        data = _API.get_balance(currency)
        print(data)
        if not data['Success']:
            Cryptopia._validate_response(data)
            raise OperationalException('{message} params=({currency})'.format(
                message=data['Error'],
                currency=currency))
        return float(data['Data'][0]['Available'] or 0.0)

    def get_balances(self):
        data = _API.get_balance("")
        if not data['Success']:
            Bittrex._validate_response(data)
            raise OperationalException('{message}'.format(message=data['Error']))
        balances = [{
            'Currency': i['Symbol'],
            'Balance': i['Total'],
            'Available': i['Available'],
            'Pending': i['PendingWithdraw'] + i['Unconfirmed'] + i['HeldForTrades']
        } for i in data['Data']]
        return balances

    def get_ticker(self, pair: str, refresh: Optional[bool] = True) -> dict:
        if refresh or pair not in self.cached_ticker.keys():
            data = _API.get_market(pair)
            if not data['Success']:
                Cryptopia._validate_response(data)
                raise OperationalException('{message} params=({pair})'.format(
                    message=data['Message'],
                    pair=pair))
            keys = ['BidPrice', 'AskPrice', 'LastPrice']
            if not data.get('Data') or\
                    not all(key in data.get('Data', {}) for key in keys) or\
                    not all(data.get('Data', {})[key] is not None for key in keys):
                raise ContentDecodingError('{message} params=({pair})'.format(
                    message='Got invalid response from cryptopia',
                    pair=pair))
            # Update the pair
            self.cached_ticker[pair] = {
                'bid': float(data['Data']['BidPrice']),
                'ask': float(data['Data']['AskPrice']),
                'last': float(data['Data']['LastPrice']),
            }
        return self.cached_ticker[pair]

    def get_ticker_history(self, pair: str, tick_interval: int) -> List[Dict]:
        pairid = self.query_currency_id(pair)
        data = _API.get_tickers(pairid, tick_interval, 'oneDay')
        tick_len = len(data['Candle'])
        if tick_len != len(data['Volume']):
            raise ContentDecodingError('{message} params=({pair})'.format(
                message="vaolume and candle dosen't have same length",
                pair=pair))
        tick_history = []
        candle_data = data['Candle']
        volume_data = data['Volume']
        for i in range(tick_len):
            candle_item = candle_data[i]
            volume_item = volume_data[i]
            tick_history.append({
                'C': candle_item[4],
                'O': candle_item[1],
                'V': volume_item['basev'] * 2.0 / (candle_item[4] + candle_item[1]),
                'H': candle_item[2],
                'L': candle_item[3],
                'T': time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(float(candle_item[0]) / 1000.0)),
                'BV': volume_item['basev'],

                })
        return tick_history

    def get_order(self, order_id: str) -> Dict:
        if not order_id in self.open_order:
            market = ""
        else:
            market = self.open_order[order_id]
        open_order = _API.get_openorders(market)
        hist_order = _API.get_tradehistory(market)
        if not open_order['Success']:
            Cryptopia._validate_response(open_order)
            raise OperationalException('{message} params=({order_id})'.format(
                message=open_order['Error'],
                order_id=order_id))
        if not hist_order['Success']:
            Cryptopia._validate_response(hist_order)
            raise OperationalException('{message} params=({order_id})'.format(
                message=hist_order['Error'],
                order_id=order_id))
        oid = int(order_id)
        for order in open_order['Data']:
            if order['OrderId'] == oid:
                return {
                    'id': order['OrderId'],
                    'type': order['Type'],
                    'pair': order['Market'],
                    'opened': True,
                    'rate': order['Rate'],
                    'amount': order['Amount'],
                    'remaining': order['Remaining'],
                    'closed': False
                }
        for order in hist_order['Data']:
            if order['TradeId'] == oid:
                return {
                    'id': order['TradeId'],
                    'type': order['Type'],
                    'pair': order['Market'],
                    'opened': False,
                    'rate': order['Rate'],
                    'amount': order['Amount'],
                    'remaining': 0.0,
                    'closed': True
                }

    def query_currency_id(self, currency):
        if currency in self.cached_pair_id:
            return self.cached_pair_id[currency]
        else:
            data = _API.get_market(currency)
            self.cached_pair_id[currency] = data['Data']['TradePairId']
            return self.cached_pair_id[currency]

    def cancel_order(self, order_id: str) -> None:
        data = _API.cancel_trade('Trade', order_id, tradepair_id)
        if not data['Success']:
            Cryptopia._validate_response(data)
            raise OperationalException('{message} params=({order_id})'.format(
                message=data['Error'],
                order_id=order_id))

    def get_pair_detail_url(self, pair: str) -> str:
        return "https://www.cryptopia.co.nz/Exchange/?market={}".format(pair)

    def get_markets(self) -> List[str]:
        data = _API.get_markets()
        if not data['Success']:
            Cryptopia._validate_response(data)
            raise OperationalException('{message}'.format(message=data['message']))
        return [m['Label'] for m in data['Data']]

    def get_market_summaries(self) -> List[Dict]:
        data = _API.get_markets()
        if not data['Success']:
            Cryptopia._validate_response(data)
            raise OperationalException('{message}'.format(message=data['message']))
        return data['Data']

    def get_wallet_health(self) -> List[Dict]:
        data = _API_V2.get_wallet_health()
        if not data['success']:
            Bittrex._validate_response(data)
            raise OperationalException('{message}'.format(message=data['message']))
        return [{
            'Currency': entry['Health']['Currency'],
            'IsActive': entry['Health']['IsActive'],
            'LastChecked': entry['Health']['LastChecked'],
            'Notice': entry['Currency'].get('Notice'),
        } for entry in data['result']]

    

        
