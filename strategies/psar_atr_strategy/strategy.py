import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from strategies.psar_atr_strategy.config import Config


class Strategy:
    def __init__(self, timeframe=None):
        self.config = Config()
        self.timeframe = timeframe
        self.last_signal_time = None
        self.pending_signal = None
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

    def calculate_psar(self, df):
        """Parabolic SAR hesaplaması"""
        high = df['High']
        low = df['Low']
        close = df['Close']

        # PSAR parametreleri
        start = self.config.psar_start * 0.01
        increment = self.config.psar_increment * 0.01
        maximum = self.config.psar_maximum * 0.10

        # PSAR hesaplama
        psar = pd.Series(index=df.index, dtype=float)
        trend = pd.Series(index=df.index, dtype=int)
        ep = pd.Series(index=df.index, dtype=float)
        acc = pd.Series(index=df.index, dtype=float)

        # İlk değerler
        psar[0] = low[0]
        trend[0] = 1
        ep[0] = high[0]
        acc[0] = start

        for i in range(1, len(df)):
            # Trend devam ediyor mu kontrol et
            if trend[i - 1] == 1:
                psar[i] = psar[i - 1] + acc[i - 1] * (ep[i - 1] - psar[i - 1])
                if low[i] < psar[i]:
                    trend[i] = -1
                    psar[i] = ep[i - 1]
                    acc[i] = start
                    ep[i] = low[i]
                else:
                    trend[i] = 1
                    if high[i] > ep[i - 1]:
                        ep[i] = high[i]
                        acc[i] = min(acc[i - 1] + increment, maximum)
                    else:
                        ep[i] = ep[i - 1]
                        acc[i] = acc[i - 1]
            else:
                psar[i] = psar[i - 1] + acc[i - 1] * (ep[i - 1] - psar[i - 1])
                if high[i] > psar[i]:
                    trend[i] = 1
                    psar[i] = ep[i - 1]
                    acc[i] = start
                    ep[i] = high[i]
                else:
                    trend[i] = -1
                    if low[i] < ep[i - 1]:
                        ep[i] = low[i]
                        acc[i] = min(acc[i - 1] + increment, maximum)
                    else:
                        ep[i] = ep[i - 1]
                        acc[i] = acc[i - 1]

        df['psar'] = psar
        df['psar_trend'] = trend
        return df

    def calculate_atr(self, df, period=10):
        """ATR hesaplaması"""
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        atr = true_range.rolling(window=period).mean()
        return atr

    def calculate_zones(self, df):
        """ATR tabanlı bölgeleri hesaplar"""
        # ATR hesapla
        df['atr'] = self.calculate_atr(df, self.config.zone_length)

        # HL2 hesapla
        df['hl2'] = (df['High'] + df['Low']) / 2

        # Bölgeleri hesapla
        df['down_zone'] = df['hl2'] + (df['atr'] * self.config.zone_multiplier)
        df['up_zone'] = df['hl2'] - (df['atr'] * self.config.zone_multiplier)

        # Önceki değerleri kullanarak bölgeleri güncelle
        for i in range(1, len(df)):
            prev_close = df.loc[i - 1, 'Close']
            prev_down = df.loc[i - 1, 'down_zone']
            prev_up = df.loc[i - 1, 'up_zone']
            current_down = df.loc[i, 'down_zone']
            current_up = df.loc[i, 'up_zone']

            # Pine Script'teki mantığı uygula
            if prev_close < prev_down:
                df.loc[i, 'down_zone'] = min(current_down, prev_down)

            if prev_close > prev_up:
                df.loc[i, 'up_zone'] = max(current_up, prev_up)

        # Zone Decider hesapla
        df['zone_decider'] = 1  # Başlangıç değeri

        for i in range(1, len(df)):
            prev_decider = df.loc[i - 1, 'zone_decider']
            current_close = df.loc[i, 'Close']
            current_down = df.loc[i, 'down_zone']
            current_up = df.loc[i, 'up_zone']

            if prev_decider == -1 and current_close > current_down:
                df.loc[i, 'zone_decider'] = 1
            elif prev_decider == 1 and current_close < current_up:
                df.loc[i, 'zone_decider'] = -1
            else:
                df.loc[i, 'zone_decider'] = prev_decider

        return df

    def calculate_donchian(self, df):
        """Donchian Channel hesaplaması"""
        df['upper_donchian'] = df['High'].rolling(window=self.config.donchian_length).max()
        df['lower_donchian'] = df['Low'].rolling(window=self.config.donchian_length).min()
        df['middle_donchian'] = (df['upper_donchian'] + df['lower_donchian']) / 2
        return df

    def calculate_ema(self, df, period):
        """EMA hesaplaması"""
        return df['Close'].ewm(span=period, adjust=False).mean()

    def calculate_hma(self, df, period):
        """HMA hesaplaması"""
        wmaf = df['Close'].rolling(window=period // 2).apply(
            lambda x: np.sum(x * np.arange(1, len(x) + 1)) / np.sum(np.arange(1, len(x) + 1)))
        wmas = df['Close'].rolling(window=period).apply(
            lambda x: np.sum(x * np.arange(1, len(x) + 1)) / np.sum(np.arange(1, len(x) + 1)))
        return wmaf * 2 - wmas

    def determine_position(self, df):
        """Pozisyon belirleme mantığı"""
        # PSAR hesapla
        df = self.calculate_psar(df)

        # ATR Zone hesapla
        df = self.calculate_zones(df)

        # Donchian Channel hesapla
        df = self.calculate_donchian(df)

        # EMA ve HMA hesapla
        df['ema_lower'] = self.calculate_ema(df, self.config.ema_lower_period)
        df['ema_medium'] = self.calculate_ema(df, self.config.ema_medium_period)
        df['hma_long'] = self.calculate_hma(df, self.config.hma_long_period)

        # Alım-satım sinyalleri
        df['buy'] = (df['zone_decider'] == 1) & (df['zone_decider'].shift(1) == -1) & (df['Close'] > df['middle_donchian'])
        df['sell'] = (df['zone_decider'] == -1) & (df['zone_decider'].shift(1) == 1) & (df['Close'] < df['middle_donchian'])

        # Bar renkleri için koşullar
        df['is_close_above'] = (df['Close'] > df['ema_lower']) & (df['Close'] > df['hma_long'])
        df['is_close_below'] = (df['Close'] < df['ema_lower']) & (df['Close'] < df['hma_long'])
        df['is_close_between'] = ((df['Close'] > df['ema_lower']) & (df['Close'] < df['hma_long'])) | \
                                ((df['Close'] < df['ema_lower']) & (df['Close'] > df['hma_long']))
        df['is_neutral'] = ((df['Close'] > df['psar']) & df['is_close_below']) | \
                          ((df['Close'] < df['psar']) & df['is_close_above'])

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

        # Eğer bekleyen bir sinyal varsa ve bekleme süresi dolmamışsa
        if self.pending_signal and self.last_signal_time:
            waiting_time = current_time - self.last_signal_time
            if waiting_time.total_seconds() < self.config.waiting_period:
                return None
            else:
                # Bekleme süresi dolduysa, bekleyen sinyali sıfırla
                signal = self.pending_signal
                self.pending_signal = None
                self.last_signal_time = None
                return signal

        # Yeni sinyal kontrolü
        if last_row.get('buy', False) or last_row.get('sell', False):
            
            # Aynı mum içerisinde daha önce işlem yapılıp yapılmadığını kontrol et
            if self.last_candle_time and self._is_same_candle(last_candle_time, self.last_candle_time):
                # Aynı mum içerisinde zaten işlem yapıldı
                return None
            
            # Eğer son işlemden yeterli süre geçmediyse (ek güvenlik)
            if self.last_signal_time:
                time_since_last_signal = current_time - self.last_signal_time
                if time_since_last_signal.total_seconds() < self.config.min_time_between_trades * 60:
                    return None

            # Sinyal var ve yeni bir mum periyodu
            signal = 'buy' if last_row.get('buy', False) else 'sell'

            # Sinyali, zamanı ve mum zamanını kaydet
            self.last_signal_time = current_time
            self.last_candle_time = last_candle_time
            self.pending_signal = signal

            return signal

        return None