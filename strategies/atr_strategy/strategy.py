import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from strategies.atr_strategy.config import Config


class Strategy:
    def __init__(self, timeframe=None):
        self.config = Config()
        self.timeframe = timeframe
        self.last_signal_time = None
        self.last_candle_time = None  # Son işlem yapılan mum zamanı

    def _get_timeframe_minutes(self):
        """Timeframe'i dakika cinsinden döndürür"""
        if not self.timeframe:
            return 60  # Varsayılan 1 saat
        
        timeframe_lower = self.timeframe.lower()
        if timeframe_lower.endswith('m'):
            return int(timeframe_lower[:-1])
        elif timeframe_lower.endswith('h'):
            return int(timeframe_lower[:-1]) * 60
        elif timeframe_lower.endswith('d'):
            return int(timeframe_lower[:-1]) * 24 * 60
        else:
            return 60  # Varsayılan

    def _get_candle_start_time(self, timestamp):
        """Verilen zaman damgasının ait olduğu mumun başlangıç zamanını döndürür"""
        if isinstance(timestamp, pd.Timestamp):
            dt = timestamp.to_pydatetime()
        else:
            dt = timestamp
        
        timeframe_minutes = self._get_timeframe_minutes()
        
        # Mumun başlangıç zamanını hesapla
        total_minutes = dt.hour * 60 + dt.minute
        candle_number = total_minutes // timeframe_minutes
        candle_start_minutes = candle_number * timeframe_minutes
        
        candle_start_time = dt.replace(
            hour=candle_start_minutes // 60,
            minute=candle_start_minutes % 60,
            second=0,
            microsecond=0
        )
        
        return candle_start_time

    def _is_same_candle(self, time1, time2):
        """İki zaman damgasının aynı muma ait olup olmadığını kontrol eder"""
        if not time1 or not time2:
            return False
        
        candle_start1 = self._get_candle_start_time(time1)
        candle_start2 = self._get_candle_start_time(time2)
        
        return candle_start1 == candle_start2

    def calculate_atr_trailing_stop(self, df):
        """TradingView'deki ATR Trailing Stop hesaplaması"""
        # ATR hesapla
        df['atr'] = self.calculate_atr(df, self.config.atr_period)
        df['n_loss'] = self.config.key_value * df['atr']

        # Trailing stop hesapla
        df['trailing_stop'] = 0.0

        for i in range(1, len(df)):
            prev_close = df.loc[i - 1, 'Close']
            curr_close = df.loc[i, 'Close']
            prev_stop = df.loc[i - 1, 'trailing_stop']
            n_loss = df.loc[i, 'n_loss']

            if curr_close > prev_stop and prev_close > prev_stop:
                df.loc[i, 'trailing_stop'] = max(prev_stop, curr_close - n_loss)
            elif curr_close < prev_stop and prev_close < prev_stop:
                df.loc[i, 'trailing_stop'] = min(prev_stop, curr_close + n_loss)
            elif curr_close > prev_stop:
                df.loc[i, 'trailing_stop'] = curr_close - n_loss
            else:
                df.loc[i, 'trailing_stop'] = curr_close + n_loss

        return df

    def calculate_super_trend(self, df):
        """TradingView'deki Super Trend hesaplaması"""
        df['hl2'] = (df['High'] + df['Low']) / 2
        df['super_trend_atr'] = df['atr'] * self.config.super_trend_factor
        df['trend_up'] = df['hl2'] - df['super_trend_atr']
        df['trend_down'] = df['hl2'] + df['super_trend_atr']

        df['super_trend'] = 0.0
        df['super_trend_direction'] = 0  # 1: yukarı, -1: aşağı

        for i in range(1, len(df)):
            curr_close = df.loc[i, 'Close']
            prev_trend = df.loc[i - 1, 'super_trend']
            trend_up = df.loc[i, 'trend_up']
            trend_down = df.loc[i, 'trend_down']

            if curr_close > prev_trend:
                df.loc[i, 'super_trend'] = trend_down
                df.loc[i, 'super_trend_direction'] = 1
            else:
                df.loc[i, 'super_trend'] = trend_up
                df.loc[i, 'super_trend_direction'] = -1

        return df

    def calculate_atr(self, df, period):
        """ATR hesaplaması"""
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(window=period).mean()

    def calculate_ema(self, df, period):
        """EMA hesaplaması"""
        return df['Close'].ewm(span=period, adjust=False).mean()

    def determine_position(self, df):
        """TradingView'deki sinyal mantığı"""
        # ATR Trailing Stop hesapla
        df = self.calculate_atr_trailing_stop(df)

        # Super Trend hesapla
        df = self.calculate_super_trend(df)

        # EMA hesapla
        df['ema'] = self.calculate_ema(df, 1)

        # Sinyal koşulları
        df['above'] = (df['ema'] > df['trailing_stop']) & (df['ema'].shift(1) <= df['trailing_stop'].shift(1))
        df['below'] = (df['ema'] < df['trailing_stop']) & (df['ema'].shift(1) >= df['trailing_stop'].shift(1))

        # Bar renkleri için koşullar
        df['bar_buy'] = df['Close'] > df['trailing_stop']
        df['bar_sell'] = df['Close'] < df['trailing_stop']

        # Alım-satım sinyalleri
        df['buy'] = (df['Close'] > df['trailing_stop']) & df['above']
        df['sell'] = (df['Close'] < df['trailing_stop']) & df['below']

        # Super Trend sinyalleri
        df['buy_super_trend'] = df['Close'] > df['super_trend']
        df['sell_super_trend'] = df['Close'] < df['super_trend']

        return df

    def get_trade_signal(self, df):
        """Son mumun sinyal durumunu döndürür - Timeframe bazlı sınırlama ile"""
        if df.empty:
            return None
            
        last_row = df.iloc[-1]
        current_time = datetime.now()
        
        # Son mumun zaman damgasını al
        if hasattr(df.index[-1], 'to_pydatetime'):
            last_candle_time = df.index[-1].to_pydatetime()
        else:
            last_candle_time = df.index[-1] if isinstance(df.index[-1], datetime) else current_time

        # Aynı mum içerisinde daha önce işlem yapılıp yapılmadığını kontrol et
        if self.last_candle_time and self._is_same_candle(last_candle_time, self.last_candle_time):
            # Aynı mum içerisinde zaten işlem yapıldı
            return None

        # Son işlemden yeterli süre geçti mi kontrol et (ek güvenlik)
        if self.last_signal_time:
            time_since_last_signal = (current_time - self.last_signal_time).total_seconds() / 60
            if time_since_last_signal < self.config.min_time_between_trades:
                return None

        # Sinyal kontrolü
        if last_row['buy'] and last_row['buy_super_trend']:
            self.last_signal_time = current_time
            self.last_candle_time = last_candle_time
            return 'buy'
        elif last_row['sell'] and last_row['sell_super_trend']:
            self.last_signal_time = current_time
            self.last_candle_time = last_candle_time
            return 'sell'

        return None