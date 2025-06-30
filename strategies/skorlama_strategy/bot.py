"""
Skorlama Strategy Bot

Bu dosya, Skorlama stratejisinin ana bot sınıfını içerir.
Pine Script'teki stratejiyi Python'da çalıştıran bot implementasyonu.
"""

import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import os
import csv

from adapters.binance.binance_client import BinanceClient
from adapters.binance.order_manager import OrderManager
from core.telegram.telegram_notifier import TelegramNotifier
from core.logging_config import setup_logging
from .strategy import SkorlamaStrategy
from .executor import SkorlamaExecutor
from .config import SkorlamaConfig

class SkorlamaBot:
    """Skorlama Stratejisi Bot Sınıfı"""
    
    def __init__(self, symbol: str, api_key: str = None, api_secret: str = None, 
                 testnet: bool = True, leverage: int = 10, trade_amount: float = 100):
        """
        Bot başlatma
        
        Args:
            symbol: Trading sembolü (örn: 'BNBUSDT')
            api_key: Binance API anahtarı
            api_secret: Binance API gizli anahtarı
            testnet: Test ağı kullanımı
            leverage: Kaldıraç oranı
            trade_amount: İşlem miktarı (yüzde)
        """
        self.symbol = symbol.upper()
        self.leverage = leverage
        self.trade_amount = trade_amount
        
        # Logging ayarla
        self.logger = setup_logging(f'skorlama_bot_{self.symbol.lower()}')
        
        # Binance client başlat
        self.client = BinanceClient(api_key, api_secret, testnet)
        self.order_manager = OrderManager(self.client)
        
        # Telegram notifier başlat
        self.telegram = TelegramNotifier(symbol=self.symbol)
        
        # Strateji ve executor başlat
        self.config = SkorlamaConfig()
        self.strategy = SkorlamaStrategy(self.config)
        self.executor = SkorlamaExecutor(self.strategy, self.config)
        
        # Bot durumu
        self.is_running = False
        self.last_candle_time = None
        
        # CSV dosya yolları
        self.trades_file = f'logs/trades_{self.symbol.lower()}.csv'
        self.positions_file = f'logs/positions_{self.symbol.lower()}.csv'
        
        # CSV dosyalarını oluştur
        self._initialize_csv_files()
        
        self.logger.info(f"Skorlama Bot başlatıldı - Sembol: {self.symbol}, Kaldıraç: {leverage}x, İşlem Miktarı: %{trade_amount}")
    
    def _initialize_csv_files(self):
        """CSV dosyalarını başlatma"""
        # Trades CSV
        if not os.path.exists(self.trades_file):
            with open(self.trades_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'symbol', 'action', 'position', 'price', 'size', 
                    'leverage', 'trade_amount', 'take_profit', 'stop_loss', 
                    'pnl_percent', 'reason', 'score', 'adx', 'rsi'
                ])
        
        # Positions CSV
        if not os.path.exists(self.positions_file):
            with open(self.positions_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'symbol', 'position', 'entry_price', 'current_price',
                    'pnl_percent', 'take_profit', 'stop_loss', 'leverage', 'trade_amount'
                ])
    
    def _log_trade(self, trade_data: Dict, signal_data: Dict = None):
        """İşlem verilerini CSV'ye kaydetme"""
        try:
            with open(self.trades_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                if trade_data['type'] == 'entry':
                    writer.writerow([
                        trade_data['timestamp'],
                        self.symbol,
                        'ENTRY',
                        trade_data['position'],
                        trade_data['price'],
                        trade_data['size'],
                        trade_data['leverage'],
                        trade_data['trade_amount'],
                        trade_data['take_profit'],
                        trade_data['stop_loss'],
                        '',  # pnl_percent
                        '',  # reason
                        signal_data.get('score', '') if signal_data else '',
                        signal_data.get('adx', '') if signal_data else '',
                        signal_data.get('rsi', '') if signal_data else ''
                    ])
                else:  # exit
                    writer.writerow([
                        trade_data['timestamp'],
                        self.symbol,
                        'EXIT',
                        trade_data['position'],
                        trade_data['exit_price'],
                        '',  # size
                        '',  # leverage
                        '',  # trade_amount
                        '',  # take_profit
                        '',  # stop_loss
                        trade_data['pnl_percent'],
                        trade_data['reason'],
                        '',  # score
                        '',  # adx
                        ''   # rsi
                    ])
        except Exception as e:
            self.logger.error(f"Trade log kaydetme hatası: {e}")
    
    def _log_position(self, position_info: Dict, current_price: float):
        """Pozisyon verilerini CSV'ye kaydetme"""
        try:
            if position_info:
                pnl_percent = 0
                if position_info['position'] == 'long':
                    pnl_percent = ((current_price - position_info['entry_price']) / position_info['entry_price']) * 100
                else:  # short
                    pnl_percent = ((position_info['entry_price'] - current_price) / position_info['entry_price']) * 100
                
                with open(self.positions_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        datetime.now(),
                        self.symbol,
                        position_info['position'],
                        position_info['entry_price'],
                        current_price,
                        pnl_percent,
                        position_info['take_profit'],
                        position_info['stop_loss'],
                        self.leverage,
                        self.trade_amount
                    ])
        except Exception as e:
            self.logger.error(f"Position log kaydetme hatası: {e}")
    
    def _get_historical_data(self, limit: int = 500) -> pd.DataFrame:
        """
        Geçmiş veri alma
        
        Args:
            limit: Alınacak mum sayısı
            
        Returns:
            pd.DataFrame: OHLCV veri çerçevesi
        """
        try:
            klines = self.client.get_klines(self.symbol, '1m', limit=limit)
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Veri tiplerini dönüştür
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Timestamp'i datetime'a çevir
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
        except Exception as e:
            self.logger.error(f"Geçmiş veri alma hatası: {e}")
            return pd.DataFrame()
    
    def _get_current_price(self) -> Optional[float]:
        """Mevcut fiyat alma"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            return float(ticker['price'])
        except Exception as e:
            self.logger.error(f"Mevcut fiyat alma hatası: {e}")
            return None
    
    def _get_account_balance(self) -> float:
        """Hesap bakiyesi alma"""
        try:
            account_info = self.client.get_account_info()
            balances = account_info.get('balances', [])
            
            # USDT bakiyesini bul
            for balance in balances:
                if balance['asset'] == 'USDT':
                    return float(balance['free'])
            
            return 0.0
        except Exception as e:
            self.logger.error(f"Bakiye alma hatası: {e}")
            return 1000.0  # Varsayılan bakiye
    
    def _send_telegram_message(self, message: str):
        """Telegram mesajı gönderme"""
        try:
            self.telegram.send_notification(message)
        except Exception as e:
            self.logger.error(f"Telegram mesaj gönderme hatası: {e}")
    
    def _process_signal(self, signal: Dict):
        """Sinyal işleme"""
        try:
            if signal['action'] == 'enter_long':
                # Long pozisyon girişi
                trade = signal['trade']
                
                # Gerçek işlem yap (testnet için)
                order_result = self.order_manager.place_futures_order(
                    symbol=self.symbol,
                    side='BUY',
                    quantity=trade['size'],
                    leverage=self.leverage
                )
                
                if order_result:
                    message = f"🟢 LONG POZİSYON AÇILDI\n"
                    message += f"Sembol: {self.symbol}\n"
                    message += f"Fiyat: {trade['price']:.6f}\n"
                    message += f"Büyüklük: {trade['size']:.2f}\n"
                    message += f"Kaldıraç: {self.leverage}x\n"
                    message += f"Take Profit: {trade['take_profit']:.6f}\n"
                    message += f"Stop Loss: {trade['stop_loss']:.6f}\n"
                    message += f"Skor: {signal.get('score', 'N/A')}\n"
                    message += f"ADX: {signal.get('adx', 'N/A'):.2f}\n"
                    message += f"RSI: {signal.get('rsi', 'N/A'):.2f}"
                    
                    self._send_telegram_message(message)
                    self.logger.info(f"Long pozisyon açıldı: {trade['price']}")
                
                # CSV'ye kaydet
                self._log_trade(trade, signal)
                
                # Ortak sinyal kontrol CSV'ye yaz
                try:
                    from core.signal_logger import signal_logger
                    # Signal data'yı hazırla
                    signal_data = {
                        'buy': True,
                        'sell': False,
                        'Close': trade['price'],
                        'score': signal.get('score', 0),
                        'adx': signal.get('adx', 0),
                        'rsi': signal.get('rsi', 0),
                        'bar_index': str(signal.get('time', datetime.now()))
                    }
                    signal_logger.log_signal("Skorlama_Strategy", self.symbol, signal_data)
                except Exception as e:
                    self.logger.error(f"Sinyal kontrol logger hatası: {e}")
                
            elif signal['action'] == 'enter_short':
                # Short pozisyon girişi
                trade = signal['trade']
                
                # Gerçek işlem yap (testnet için)
                order_result = self.order_manager.place_futures_order(
                    symbol=self.symbol,
                    side='SELL',
                    quantity=trade['size'],
                    leverage=self.leverage
                )
                
                if order_result:
                    message = f"🔴 SHORT POZİSYON AÇILDI\n"
                    message += f"Sembol: {self.symbol}\n"
                    message += f"Fiyat: {trade['price']:.6f}\n"
                    message += f"Büyüklük: {trade['size']:.2f}\n"
                    message += f"Kaldıraç: {self.leverage}x\n"
                    message += f"Take Profit: {trade['take_profit']:.6f}\n"
                    message += f"Stop Loss: {trade['stop_loss']:.6f}\n"
                    message += f"Skor: {signal.get('score', 'N/A')}\n"
                    message += f"ADX: {signal.get('adx', 'N/A'):.2f}\n"
                    message += f"RSI: {signal.get('rsi', 'N/A'):.2f}"
                    
                    self._send_telegram_message(message)
                    self.logger.info(f"Short pozisyon açıldı: {trade['price']}")
                
                # CSV'ye kaydet
                self._log_trade(trade, signal)
                
                # Ortak sinyal kontrol CSV'ye yaz
                try:
                    from core.signal_logger import signal_logger
                    # Signal data'yı hazırla
                    signal_data = {
                        'buy': False,
                        'sell': True,
                        'Close': trade['price'],
                        'score': signal.get('score', 0),
                        'adx': signal.get('adx', 0),
                        'rsi': signal.get('rsi', 0),
                        'bar_index': str(signal.get('time', datetime.now()))
                    }
                    signal_logger.log_signal("Skorlama_Strategy", self.symbol, signal_data)
                except Exception as e:
                    self.logger.error(f"Sinyal kontrol logger hatası: {e}")
                
            elif signal['action'] == 'exit':
                # Pozisyon çıkışı
                trade = signal['trade']
                
                # Gerçek işlem yap (testnet için)
                side = 'SELL' if trade['position'] == 'long' else 'BUY'
                order_result = self.order_manager.place_futures_order(
                    symbol=self.symbol,
                    side=side,
                    quantity=trade['size'] if 'size' in trade else 0,
                    leverage=self.leverage
                )
                
                if order_result:
                    pnl_emoji = "🟢" if trade['pnl_percent'] > 0 else "🔴"
                    message = f"{pnl_emoji} POZİSYON KAPANDI\n"
                    message += f"Sembol: {self.symbol}\n"
                    message += f"Pozisyon: {trade['position'].upper()}\n"
                    message += f"Giriş: {trade['entry_price']:.6f}\n"
                    message += f"Çıkış: {trade['exit_price']:.6f}\n"
                    message += f"Kar/Zarar: %{trade['pnl_percent']:.2f}\n"
                    message += f"Sebep: {trade['reason']}"
                    
                    self._send_telegram_message(message)
                    self.logger.info(f"Pozisyon kapandı: {trade['pnl_percent']:.2f}%")
                
                # CSV'ye kaydet
                self._log_trade(trade)
                
        except Exception as e:
            self.logger.error(f"Sinyal işleme hatası: {e}")
    
    def run(self):
        """Bot çalıştırma"""
        self.is_running = True
        self.logger.info("Skorlama Bot çalışmaya başladı")
        
        # Başlangıç mesajı
        start_message = f"🚀 SKORLAMA BOT BAŞLATILDI\n"
        start_message += f"Sembol: {self.symbol}\n"
        start_message += f"Kaldıraç: {self.leverage}x\n"
        start_message += f"İşlem Miktarı: %{self.trade_amount}\n"
        start_message += f"Strateji: Skorlama (PSAR + ATR Zone + Donchian + Smart Filter)"
        
        self._send_telegram_message(start_message)
        
        while self.is_running:
            try:
                # Geçmiş veriyi al
                df = self._get_historical_data(limit=500)
                if df.empty:
                    self.logger.warning("Veri alınamadı, 60 saniye bekleniyor...")
                    time.sleep(60)
                    continue
                
                # Mevcut fiyatı al
                current_price = self._get_current_price()
                if current_price is None:
                    self.logger.warning("Mevcut fiyat alınamadı, 60 saniye bekleniyor...")
                    time.sleep(60)
                    continue
                
                # Hesap bakiyesini al
                balance = self._get_account_balance()
                
                # Son mum zamanını kontrol et
                last_candle_time = df['timestamp'].iloc[-1]
                if self.last_candle_time == last_candle_time:
                    # Yeni mum yok, 10 saniye bekle
                    time.sleep(10)
                    continue
                
                self.last_candle_time = last_candle_time
                
                # Sinyal işle
                signal = self.executor.process_candle(
                    df, len(df) - 1, last_candle_time, 
                    balance, self.leverage, self.trade_amount
                )
                
                if signal:
                    self._process_signal(signal)
                
                # Mevcut pozisyon bilgilerini logla
                position_info = self.executor.get_current_position_info()
                if position_info:
                    self._log_position(position_info, current_price)
                
                # 10 saniye bekle
                time.sleep(10)
                
            except KeyboardInterrupt:
                self.logger.info("Bot durduruldu (KeyboardInterrupt)")
                break
            except Exception as e:
                self.logger.error(f"Bot çalışma hatası: {e}")
                time.sleep(60)
        
        # Kapanış mesajı
        summary = self.executor.get_trades_summary()
        end_message = f"🛑 SKORLAMA BOT DURDURULDU\n"
        end_message += f"Sembol: {self.symbol}\n"
        end_message += f"Toplam İşlem: {summary['total_trades']}\n"
        end_message += f"Kazanan: {summary['winning_trades']}\n"
        end_message += f"Kaybeden: {summary['losing_trades']}\n"
        end_message += f"Kazanma Oranı: %{summary['win_rate']:.2f}\n"
        end_message += f"Toplam Kar/Zarar: %{summary['total_pnl']:.2f}"
        
        self._send_telegram_message(end_message)
        self.logger.info("Skorlama Bot durduruldu")
    
    def stop(self):
        """Bot durdurma"""
        self.is_running = False
        self.logger.info("Bot durdurma sinyali gönderildi") 