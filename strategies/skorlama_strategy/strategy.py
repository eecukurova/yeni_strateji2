"""
Skorlama Strategy Implementation

Bu dosya, Pine Script'teki "Psar ATR With Zone + Donchian + Smart Filter STRATEGY" 
stratejisinin Python implementasyonunu içerir.

Ana bileşenler:
1. PSAR (Parabolic SAR) hesaplama
2. ATR Zone sistemi
3. Donchian Channel
4. EMA 50/200
5. ADX göstergesi
6. Skorlama sistemi
7. Sinyal üretimi
"""

import pandas as pd
import numpy as np
import talib
from typing import Dict, Tuple, Optional
from .config import SkorlamaConfig

class SkorlamaStrategy:
    """Skorlama Stratejisi Ana Sınıfı"""
    
    def __init__(self, config: SkorlamaConfig = None):
        """Strateji başlatma"""
        self.config = config or SkorlamaConfig()
        
        # Strateji durumu
        self.in_long = False
        self.in_short = False
        self.zone_decider = 1  # 1: yeşil zone, -1: kırmızı zone
        
        # Geçmiş veriler
        self.down_zone_history = []
        self.up_zone_history = []
        
    def calculate_psar(self, high: pd.Series, low: pd.Series, close: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """
        PSAR (Parabolic SAR) hesaplama
        
        Args:
            high: Yüksek fiyat serisi
            low: Düşük fiyat serisi
            close: Kapanış fiyat serisi
            
        Returns:
            Tuple[pd.Series, pd.Series]: PSAR yukarı ve aşağı değerleri
        """
        # PSAR parametrelerini Pine Script'e uygun şekilde ayarla
        psar_start = self.config.PSAR_START * 0.01  # 0.02
        psar_end = self.config.PSAR_END * 0.10      # 0.20
        psar_multiplier = self.config.PSAR_MULTIPLIER * 0.01  # 0.02
        
        # TALib ile PSAR hesapla
        psar = talib.SAR(high, low, acceleration=psar_start, maximum=psar_end)
        
        # PSAR yukarı ve aşağı değerlerini ayır
        psar_up = pd.Series(index=close.index, dtype=float)
        psar_down = pd.Series(index=close.index, dtype=float)
        
        for i in range(len(close)):
            if not pd.isna(psar.iloc[i]):
                if close.iloc[i] >= psar.iloc[i]:
                    psar_up.iloc[i] = psar.iloc[i]
                else:
                    psar_down.iloc[i] = psar.iloc[i]
        
        return psar_up, psar_down
    
    def calculate_atr_zone(self, high: pd.Series, low: pd.Series, close: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        ATR Zone sistemi hesaplama
        
        Args:
            high: Yüksek fiyat serisi
            low: Düşük fiyat serisi
            close: Kapanış fiyat serisi
            
        Returns:
            Tuple[pd.Series, pd.Series, pd.Series]: Down zone, Up zone, Zone decider
        """
        # HL2 hesapla (Pine Script'teki hl2)
        hl2 = (high + low) / 2
        
        # ATR hesapla
        atr = talib.ATR(high, low, close, timeperiod=self.config.ATR_ZONE_LENGTH)
        
        # Down zone hesapla
        down_zone = hl2 + self.config.ATR_ZONE_MULTIPLIER * atr
        
        # Up zone hesapla
        up_zone = hl2 - self.config.ATR_ZONE_MULTIPLIER * atr
        
        # Zone decider hesapla
        zone_decider = pd.Series(1, index=close.index)
        
        for i in range(1, len(close)):
            # Down zone güncelleme
            if close.iloc[i-1] < down_zone.iloc[i-1]:
                down_zone.iloc[i] = min(down_zone.iloc[i], down_zone.iloc[i-1])
            else:
                down_zone.iloc[i] = down_zone.iloc[i]
            
            # Up zone güncelleme
            if close.iloc[i-1] > up_zone.iloc[i-1]:
                up_zone.iloc[i] = max(up_zone.iloc[i], up_zone.iloc[i-1])
            else:
                up_zone.iloc[i] = up_zone.iloc[i]
            
            # Zone decider güncelleme
            prev_decider = zone_decider.iloc[i-1]
            if prev_decider == -1 and close.iloc[i] > down_zone.iloc[i-1]:
                zone_decider.iloc[i] = 1
            elif prev_decider == 1 and close.iloc[i] < up_zone.iloc[i-1]:
                zone_decider.iloc[i] = -1
            else:
                zone_decider.iloc[i] = prev_decider
        
        return down_zone, up_zone, zone_decider
    
    def calculate_donchian_channel(self, high: pd.Series, low: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Donchian Channel hesaplama
        
        Args:
            high: Yüksek fiyat serisi
            low: Düşük fiyat serisi
            
        Returns:
            Tuple[pd.Series, pd.Series, pd.Series]: Upper, Lower, Middle Donchian
        """
        # Rolling window ile highest ve lowest hesapla
        upper_donchian = high.rolling(window=self.config.DONCHIAN_LENGTH).max()
        lower_donchian = low.rolling(window=self.config.DONCHIAN_LENGTH).min()
        middle_donchian = (upper_donchian + lower_donchian) / 2
        
        return upper_donchian, lower_donchian, middle_donchian
    
    def calculate_ema(self, close: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """
        EMA 50 ve 200 hesaplama
        
        Args:
            close: Kapanış fiyat serisi
            
        Returns:
            Tuple[pd.Series, pd.Series]: EMA 50, EMA 200
        """
        ema50 = talib.EMA(close, timeperiod=self.config.EMA_FAST)
        ema200 = talib.EMA(close, timeperiod=self.config.EMA_SLOW)
        
        return ema50, ema200
    
    def calculate_adx(self, high: pd.Series, low: pd.Series, close: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        ADX göstergesi hesaplama (manuel hesaplama - Pine Script'e uygun)
        
        Args:
            high: Yüksek fiyat serisi
            low: Düşük fiyat serisi
            close: Kapanış fiyat serisi
            
        Returns:
            Tuple[pd.Series, pd.Series, pd.Series]: ADX, Plus DI, Minus DI
        """
        # Up move ve down move hesapla
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        # Plus DM ve Minus DM hesapla
        plus_dm = pd.Series(0.0, index=close.index)
        minus_dm = pd.Series(0.0, index=close.index)
        
        for i in range(1, len(close)):
            if up_move.iloc[i] > 0 and up_move.iloc[i] > down_move.iloc[i]:
                plus_dm.iloc[i] = up_move.iloc[i]
            else:
                plus_dm.iloc[i] = 0
                
            if down_move.iloc[i] > 0 and down_move.iloc[i] > up_move.iloc[i]:
                minus_dm.iloc[i] = down_move.iloc[i]
            else:
                minus_dm.iloc[i] = 0
        
        # True Range hesapla
        tr = talib.TRANGE(high, low, close)
        
        # RMA (Relative Moving Average) hesapla (EMA'ya benzer)
        tr_rma = talib.EMA(tr, timeperiod=self.config.ADX_LENGTH)
        plus_dm_rma = talib.EMA(plus_dm, timeperiod=self.config.ADX_LENGTH)
        minus_dm_rma = talib.EMA(minus_dm, timeperiod=self.config.ADX_LENGTH)
        
        # Plus DI ve Minus DI hesapla
        plus_di = 100 * plus_dm_rma / tr_rma
        minus_di = 100 * minus_dm_rma / tr_rma
        
        # DX ve ADX hesapla
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = talib.EMA(dx, timeperiod=self.config.ADX_LENGTH)
        
        return adx, plus_di, minus_di
    
    def calculate_rsi(self, close: pd.Series) -> pd.Series:
        """
        RSI hesaplama
        
        Args:
            close: Kapanış fiyat serisi
            
        Returns:
            pd.Series: RSI değerleri
        """
        return talib.RSI(close, timeperiod=self.config.RSI_LENGTH)
    
    def calculate_volume_ma(self, volume: pd.Series) -> pd.Series:
        """
        Volume Moving Average hesaplama
        
        Args:
            volume: Hacim serisi
            
        Returns:
            pd.Series: Volume MA değerleri
        """
        return volume.rolling(window=self.config.VOLUME_MA_LENGTH).mean()
    
    def calculate_atr_volatility(self, high: pd.Series, low: pd.Series, close: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """
        ATR volatilite hesaplama
        
        Args:
            high: Yüksek fiyat serisi
            low: Düşük fiyat serisi
            close: Kapanış fiyat serisi
            
        Returns:
            Tuple[pd.Series, pd.Series]: ATR değerleri, ATR MA
        """
        atr = talib.ATR(high, low, close, timeperiod=self.config.ATR_LENGTH)
        atr_ma = atr.rolling(window=self.config.ATR_MA_LENGTH).mean()
        
        return atr, atr_ma
    
    def calculate_score(self, adx: pd.Series, ema50: pd.Series, ema200: pd.Series, 
                       rsi: pd.Series, volume: pd.Series, volume_ma: pd.Series) -> pd.Series:
        """
        Skorlama sistemi hesaplama
        
        Args:
            adx: ADX değerleri
            ema50: EMA 50 değerleri
            ema200: EMA 200 değerleri
            rsi: RSI değerleri
            volume: Hacim değerleri
            volume_ma: Volume MA değerleri
            
        Returns:
            pd.Series: Skor değerleri
        """
        score = pd.Series(0, index=adx.index)
        
        # ADX > 25 için 30 puan
        score += (adx > self.config.ADX_STRONG) * self.config.SCORE_ADX_WEIGHT
        
        # Trend durumu için 20 puan (EMA50 > EMA200)
        score += (ema50 > ema200) * self.config.SCORE_TREND_WEIGHT
        
        # RSI > 55 için 20 puan
        score += (rsi > self.config.RSI_MIN) * self.config.SCORE_RSI_WEIGHT
        
        # Volume > Volume MA için 30 puan
        score += (volume > volume_ma) * self.config.SCORE_VOLUME_WEIGHT
        
        return score
    
    def generate_signals(self, close: pd.Series, down_zone: pd.Series, up_zone: pd.Series,
                        zone_decider: pd.Series, middle_donchian: pd.Series,
                        ema50: pd.Series, ema200: pd.Series, adx: pd.Series,
                        atr: pd.Series, atr_ma: pd.Series, score: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """
        Alım-satım sinyalleri üretme
        
        Args:
            close: Kapanış fiyat serisi
            down_zone: Down zone değerleri
            up_zone: Up zone değerleri
            zone_decider: Zone decider değerleri
            middle_donchian: Middle Donchian değerleri
            ema50: EMA 50 değerleri
            ema200: EMA 200 değerleri
            adx: ADX değerleri
            atr: ATR değerleri
            atr_ma: ATR MA değerleri
            score: Skor değerleri
            
        Returns:
            Tuple[pd.Series, pd.Series]: Buy sinyalleri, Sell sinyalleri
        """
        buy_signals = pd.Series(False, index=close.index)
        sell_signals = pd.Series(False, index=close.index)
        
        for i in range(1, len(close)):
            # Trend durumu
            is_trend = ema50.iloc[i] > ema200.iloc[i]
            
            # Güçlü trend
            is_strong_trend = adx.iloc[i] > self.config.ADX_MIN
            
            # Volatilite
            is_volatile = atr.iloc[i] > atr_ma.iloc[i]
            
            # Zone değişimi
            green_zone = zone_decider.iloc[i] == 1 and zone_decider.iloc[i-1] == -1
            red_zone = zone_decider.iloc[i] == -1 and zone_decider.iloc[i-1] == 1
            
            # Buy sinyali
            if (green_zone and 
                close.iloc[i] > middle_donchian.iloc[i] and 
                is_trend and 
                is_strong_trend and 
                is_volatile and 
                score.iloc[i] >= self.config.MIN_SCORE):
                buy_signals.iloc[i] = True
            
            # Sell sinyali
            if (red_zone and 
                close.iloc[i] < middle_donchian.iloc[i] and 
                is_trend and 
                is_strong_trend and 
                is_volatile and 
                score.iloc[i] >= self.config.MIN_SCORE):
                sell_signals.iloc[i] = True
        
        return buy_signals, sell_signals
    
    def update_position_status(self, buy_signal: bool, sell_signal: bool, zone_decider: int):
        """
        Pozisyon durumunu güncelleme
        
        Args:
            buy_signal: Alım sinyali
            sell_signal: Satım sinyali
            zone_decider: Zone decider değeri
        """
        if buy_signal:
            self.in_long = True
            self.in_short = False
        elif sell_signal:
            self.in_short = True
            self.in_long = False
        
        self.zone_decider = zone_decider
    
    def check_early_exit(self, zone_decider: int) -> Tuple[bool, bool]:
        """
        Erken çıkış kontrolü
        
        Args:
            zone_decider: Zone decider değeri
            
        Returns:
            Tuple[bool, bool]: Long trend reversal, Short trend reversal
        """
        trend_reversed_long = self.in_long and zone_decider == -1
        trend_reversed_short = self.in_short and zone_decider == 1
        
        return trend_reversed_long, trend_reversed_short
    
    def analyze_data(self, df: pd.DataFrame) -> Dict:
        """
        Tüm veriyi analiz etme ve sinyaller üretme
        
        Args:
            df: OHLCV veri çerçevesi
            
        Returns:
            Dict: Analiz sonuçları
        """
        # Temel veriler
        high = df['high']
        low = df['low']
        close = df['close']
        volume = df['volume']
        
        # Göstergeleri hesapla
        psar_up, psar_down = self.calculate_psar(high, low, close)
        down_zone, up_zone, zone_decider = self.calculate_atr_zone(high, low, close)
        upper_donchian, lower_donchian, middle_donchian = self.calculate_donchian_channel(high, low)
        ema50, ema200 = self.calculate_ema(close)
        adx, plus_di, minus_di = self.calculate_adx(high, low, close)
        rsi = self.calculate_rsi(close)
        volume_ma = self.calculate_volume_ma(volume)
        atr, atr_ma = self.calculate_atr_volatility(high, low, close)
        
        # Skor hesapla
        score = self.calculate_score(adx, ema50, ema200, rsi, volume, volume_ma)
        
        # Sinyaller üret
        buy_signals, sell_signals = self.generate_signals(
            close, down_zone, up_zone, zone_decider, middle_donchian,
            ema50, ema200, adx, atr, atr_ma, score
        )
        
        return {
            'psar_up': psar_up,
            'psar_down': psar_down,
            'down_zone': down_zone,
            'up_zone': up_zone,
            'zone_decider': zone_decider,
            'upper_donchian': upper_donchian,
            'lower_donchian': lower_donchian,
            'middle_donchian': middle_donchian,
            'ema50': ema50,
            'ema200': ema200,
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di,
            'rsi': rsi,
            'volume_ma': volume_ma,
            'atr': atr,
            'atr_ma': atr_ma,
            'score': score,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals
        } 