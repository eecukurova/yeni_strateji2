"""
Skorlama Strategy Executor

Bu dosya, Skorlama stratejisinin işlem yürütme mantığını içerir.
Pine Script'teki strateji giriş/çıkış mantığını Python'da uygular.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime
from .strategy import SkorlamaStrategy
from .config import SkorlamaConfig

class SkorlamaExecutor:
    """Skorlama Stratejisi İşlem Yürütücüsü"""
    
    def __init__(self, strategy: SkorlamaStrategy = None, config: SkorlamaConfig = None):
        """Executor başlatma"""
        self.strategy = strategy or SkorlamaStrategy(config)
        self.config = config or SkorlamaConfig()
        
        # İşlem durumu
        self.current_position = None  # 'long', 'short', None
        self.entry_price = None
        self.entry_time = None
        self.take_profit_price = None
        self.stop_loss_price = None
        
        # İşlem geçmişi
        self.trades = []
        self.positions = []
        
    def calculate_position_size(self, balance: float, leverage: int, trade_amount: float) -> float:
        """
        Pozisyon büyüklüğü hesaplama
        
        Args:
            balance: Hesap bakiyesi
            leverage: Kaldıraç
            trade_amount: İşlem miktarı
            
        Returns:
            float: Pozisyon büyüklüğü
        """
        # Trade amount'u balance'ın yüzdesi olarak hesapla
        position_value = (balance * trade_amount / 100) * leverage
        return position_value
    
    def calculate_take_profit_stop_loss(self, entry_price: float, position_type: str) -> Tuple[float, float]:
        """
        Take Profit ve Stop Loss fiyatlarını hesaplama
        
        Args:
            entry_price: Giriş fiyatı
            position_type: Pozisyon tipi ('long' veya 'short')
            
        Returns:
            Tuple[float, float]: Take Profit, Stop Loss fiyatları
        """
        if position_type == 'long':
            take_profit = entry_price * (1 + self.config.TAKE_PROFIT_PERCENT)
            stop_loss = entry_price * (1 - self.config.STOP_LOSS_PERCENT)
        else:  # short
            take_profit = entry_price * (1 - self.config.TAKE_PROFIT_PERCENT)
            stop_loss = entry_price * (1 + self.config.STOP_LOSS_PERCENT)
        
        return take_profit, stop_loss
    
    def should_enter_long(self, analysis: Dict, current_index: int) -> bool:
        """
        Long pozisyon giriş kontrolü
        
        Args:
            analysis: Strateji analiz sonuçları
            current_index: Mevcut veri indeksi
            
        Returns:
            bool: Long giriş yapılmalı mı
        """
        if current_index < 1:
            return False
        
        # Buy sinyali kontrolü
        buy_signal = analysis['buy_signals'].iloc[current_index]
        
        # Pozisyon kontrolü
        if self.current_position is not None:
            return False
        
        return buy_signal
    
    def should_enter_short(self, analysis: Dict, current_index: int) -> bool:
        """
        Short pozisyon giriş kontrolü
        
        Args:
            analysis: Strateji analiz sonuçları
            current_index: Mevcut veri indeksi
            
        Returns:
            bool: Short giriş yapılmalı mı
        """
        if current_index < 1:
            return False
        
        # Sell sinyali kontrolü
        sell_signal = analysis['sell_signals'].iloc[current_index]
        
        # Pozisyon kontrolü
        if self.current_position is not None:
            return False
        
        return sell_signal
    
    def should_exit_position(self, analysis: Dict, current_index: int, current_price: float) -> Tuple[bool, str]:
        """
        Pozisyon çıkış kontrolü
        
        Args:
            analysis: Strateji analiz sonuçları
            current_index: Mevcut veri indeksi
            current_price: Mevcut fiyat
            
        Returns:
            Tuple[bool, str]: Çıkış yapılmalı mı, çıkış sebebi
        """
        if self.current_position is None:
            return False, ""
        
        # Take Profit kontrolü
        if self.current_position == 'long' and current_price >= self.take_profit_price:
            return True, "Take Profit"
        elif self.current_position == 'short' and current_price <= self.take_profit_price:
            return True, "Take Profit"
        
        # Stop Loss kontrolü
        if self.current_position == 'long' and current_price <= self.stop_loss_price:
            return True, "Stop Loss"
        elif self.current_position == 'short' and current_price >= self.stop_loss_price:
            return True, "Stop Loss"
        
        # Erken çıkış kontrolü (trend reversal)
        zone_decider = analysis['zone_decider'].iloc[current_index]
        trend_reversed_long, trend_reversed_short = self.strategy.check_early_exit(zone_decider)
        
        if (self.current_position == 'long' and trend_reversed_long) or \
           (self.current_position == 'short' and trend_reversed_short):
            return True, "Trend Reversal"
        
        return False, ""
    
    def enter_position(self, position_type: str, entry_price: float, entry_time: datetime, 
                      balance: float, leverage: int, trade_amount: float) -> Dict:
        """
        Pozisyon girişi
        
        Args:
            position_type: Pozisyon tipi ('long' veya 'short')
            entry_price: Giriş fiyatı
            entry_time: Giriş zamanı
            balance: Hesap bakiyesi
            leverage: Kaldıraç
            trade_amount: İşlem miktarı
            
        Returns:
            Dict: İşlem detayları
        """
        # Pozisyon büyüklüğü hesapla
        position_size = self.calculate_position_size(balance, leverage, trade_amount)
        
        # Take Profit ve Stop Loss hesapla
        take_profit, stop_loss = self.calculate_take_profit_stop_loss(entry_price, position_type)
        
        # Pozisyon durumunu güncelle
        self.current_position = position_type
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.take_profit_price = take_profit
        self.stop_loss_price = stop_loss
        
        # İşlem kaydı oluştur
        trade = {
            'timestamp': entry_time,
            'type': 'entry',
            'position': position_type,
            'price': entry_price,
            'size': position_size,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'leverage': leverage,
            'trade_amount': trade_amount
        }
        
        self.trades.append(trade)
        
        return trade
    
    def exit_position(self, exit_price: float, exit_time: datetime, exit_reason: str) -> Dict:
        """
        Pozisyon çıkışı
        
        Args:
            exit_price: Çıkış fiyatı
            exit_time: Çıkış zamanı
            exit_reason: Çıkış sebebi
            
        Returns:
            Dict: İşlem detayları
        """
        if self.current_position is None:
            return None
        
        # Kar/zarar hesapla
        if self.current_position == 'long':
            pnl_percent = ((exit_price - self.entry_price) / self.entry_price) * 100
        else:  # short
            pnl_percent = ((self.entry_price - exit_price) / self.entry_price) * 100
        
        # İşlem kaydı oluştur
        trade = {
            'timestamp': exit_time,
            'type': 'exit',
            'position': self.current_position,
            'entry_price': self.entry_price,
            'exit_price': exit_price,
            'pnl_percent': pnl_percent,
            'reason': exit_reason,
            'entry_time': self.entry_time
        }
        
        self.trades.append(trade)
        
        # Pozisyon durumunu sıfırla
        self.current_position = None
        self.entry_price = None
        self.entry_time = None
        self.take_profit_price = None
        self.stop_loss_price = None
        
        return trade
    
    def update_position_status(self, analysis: Dict, current_index: int):
        """
        Pozisyon durumunu güncelleme
        
        Args:
            analysis: Strateji analiz sonuçları
            current_index: Mevcut veri indeksi
        """
        if current_index < 1:
            return
        
        # Strateji durumunu güncelle
        buy_signal = analysis['buy_signals'].iloc[current_index]
        sell_signal = analysis['sell_signals'].iloc[current_index]
        zone_decider = analysis['zone_decider'].iloc[current_index]
        
        self.strategy.update_position_status(buy_signal, sell_signal, zone_decider)
    
    def get_current_position_info(self) -> Optional[Dict]:
        """
        Mevcut pozisyon bilgilerini alma
        
        Returns:
            Optional[Dict]: Pozisyon bilgileri
        """
        if self.current_position is None:
            return None
        
        return {
            'position': self.current_position,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time,
            'take_profit': self.take_profit_price,
            'stop_loss': self.stop_loss_price
        }
    
    def get_trades_summary(self) -> Dict:
        """
        İşlem özeti alma
        
        Returns:
            Dict: İşlem özeti
        """
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_pnl': 0,
                'win_rate': 0
            }
        
        # Çıkış işlemlerini filtrele
        exit_trades = [trade for trade in self.trades if trade['type'] == 'exit']
        
        if not exit_trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_pnl': 0,
                'win_rate': 0
            }
        
        # İstatistikleri hesapla
        total_trades = len(exit_trades)
        winning_trades = len([trade for trade in exit_trades if trade['pnl_percent'] > 0])
        losing_trades = len([trade for trade in exit_trades if trade['pnl_percent'] <= 0])
        total_pnl = sum([trade['pnl_percent'] for trade in exit_trades])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'total_pnl': total_pnl,
            'win_rate': win_rate
        }
    
    def process_candle(self, df: pd.DataFrame, current_index: int, current_time: datetime,
                      balance: float, leverage: int, trade_amount: float) -> Optional[Dict]:
        """
        Tek mum verisi işleme
        
        Args:
            df: OHLCV veri çerçevesi
            current_index: Mevcut veri indeksi
            current_time: Mevcut zaman
            balance: Hesap bakiyesi
            leverage: Kaldıraç
            trade_amount: İşlem miktarı
            
        Returns:
            Optional[Dict]: İşlem sinyali (varsa)
        """
        # Veriyi analiz et
        analysis = self.strategy.analyze_data(df)
        
        # Pozisyon durumunu güncelle
        self.update_position_status(analysis, current_index)
        
        current_price = df['close'].iloc[current_index]
        
        # Pozisyon çıkış kontrolü
        should_exit, exit_reason = self.should_exit_position(analysis, current_index, current_price)
        if should_exit:
            exit_trade = self.exit_position(current_price, current_time, exit_reason)
            return {
                'action': 'exit',
                'trade': exit_trade,
                'reason': exit_reason,
                'price': current_price,
                'time': current_time
            }
        
        # Pozisyon giriş kontrolü
        if self.should_enter_long(analysis, current_index):
            entry_trade = self.enter_position('long', current_price, current_time, 
                                           balance, leverage, trade_amount)
            return {
                'action': 'enter_long',
                'trade': entry_trade,
                'price': current_price,
                'time': current_time,
                'score': analysis['score'].iloc[current_index],
                'adx': analysis['adx'].iloc[current_index],
                'rsi': analysis['rsi'].iloc[current_index]
            }
        
        if self.should_enter_short(analysis, current_index):
            entry_trade = self.enter_position('short', current_price, current_time, 
                                           balance, leverage, trade_amount)
            return {
                'action': 'enter_short',
                'trade': entry_trade,
                'price': current_price,
                'time': current_time,
                'score': analysis['score'].iloc[current_index],
                'adx': analysis['adx'].iloc[current_index],
                'rsi': analysis['rsi'].iloc[current_index]
            }
        
        return None 