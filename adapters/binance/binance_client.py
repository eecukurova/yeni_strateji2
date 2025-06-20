import logging
import math
import time
import pandas as pd

from .config import Config
from binance.client import Client
from binance.exceptions import BinanceAPIException


class BinanceClient:
    def __init__(self,symbol, timeframe, leverage):
        try:
            self.config = Config()
            
            self.client = Client(self.config.api_key, self.config.api_secret)
                    # List of valid intervals
            self.valid_intervals = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w',
                                    '1M']

            if timeframe not in self.valid_intervals:
                raise ValueError(f"Geçersiz zaman aralığı: {timeframe}. Geçerli aralıklar: {self.valid_intervals}")

            # Zaman damgasını otomatik olarak ayarla
            self.client.time_offset = self.client.get_server_time()['serverTime'] - int(time.time() * 1000)
            self.symbol = symbol
            self.leverage = leverage
            self.timeframe = timeframe

            self.set_leverage(self.leverage)

        except BinanceAPIException as e:
            logging.error(f"Binance API Hatası: {e}")
            raise
        except Exception as e:
            logging.error(f"Bağlantı hatası: {e}")
            raise

    def set_leverage(self,leverage):
        """Leverage ayarını yapar"""
        try:
            self.client.futures_change_leverage(symbol=self.symbol, leverage=leverage)
            logging.info(f"Leverage ayarlandı: {self.leverage}")
        except BinanceAPIException as e:
            logging.error(f"Leverage ayarı hatası: {e}")

    def get_symbol_info(self):
        """Sembol için minimum miktar, adım boyutu ve fiyat hassasiyetini alır"""
        try:
            exchange_info = self.client.futures_exchange_info()
            for symbol_info in exchange_info['symbols']:
                if symbol_info['symbol'] == self.symbol:
                    filters = symbol_info['filters']
                    min_qty, step_size, price_precision = None, None, None

                    for filter in filters:
                        if filter['filterType'] == 'LOT_SIZE':
                            min_qty = float(filter['minQty'])
                            step_size = float(filter['stepSize'])
                        elif filter['filterType'] == 'PRICE_FILTER':
                            price_precision = float(filter['tickSize'])  # Fiyat hassasiyeti

                    return min_qty, step_size, price_precision

        except BinanceAPIException as e:
            logging.error(f"Sembol bilgisi alınamadı: {e}")

        return None, None, None

    def adjust_quantity(self, quantity):
        """İşlem miktarını adım boyutuna uygun şekilde yuvarlar"""
        min_qty, step_size, _ = self.get_symbol_info()

        if min_qty is None or step_size is None:
            logging.error("Sembol bilgisi alınamadı.")
            return None

        # Ensure quantity is not less than the minimum allowed
        adjusted_quantity = max(quantity, min_qty)

        # Round to the nearest step size
        adjusted_quantity = round(adjusted_quantity / step_size) * step_size

        # Ensure the quantity does not exceed the maximum precision
        precision = int(round(-math.log(step_size, 10)))
        adjusted_quantity = round(adjusted_quantity, precision)

        return adjusted_quantity

    def adjust_price(self, price):
        """Fiyatı hassasiyete uygun şekilde yuvarlar"""
        _, _, price_precision = self.get_symbol_info()

        if price_precision is None:
            logging.error("Sembol bilgisi alınamadı.")
            return None

        # Fiyatı hassasiyete uygun şekilde yuvarla
        precision = int(round(-math.log(price_precision, 10)))
        return round(price, precision)

    def fetch_current_price(self):
        """Mevcut piyasa fiyatını alır"""
        try:
            ticker = self.client.futures_symbol_ticker(symbol=self.symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            logging.error(f"Mevcut fiyat alınamadı: {e}")
            return None
        
    def fetch_data(self):
        """Binance'ten geçmiş fiyat verilerini çeker"""
        try:
            klines = self.client.futures_klines(
                symbol=self.symbol,
                interval=self.timeframe,
                limit=100
            )

            df = pd.DataFrame(klines, columns=[
                'Open time', 'Open', 'High', 'Low', 'Close', 'Volume',
                'Close time', 'Quote volume', 'Trades', 'Taker buy base',
                'Taker buy quote', 'Ignore'
            ])

            df[['Open', 'High', 'Low', 'Close', 'Volume']] = df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(
                float)
            df['datetime'] = pd.to_datetime(df['Open time'], unit='ms')
            
            # HL2 ekle (Pine Script'teki hl2)
            df['hl2'] = (df['High'] + df['Low']) / 2

            return df

        except BinanceAPIException as e:
            logging.error(f"Veri çekme hatası: {e}")
            return None