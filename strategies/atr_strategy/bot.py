import time
import logging
import platform
import os
import ntplib
import socket
import threading
import csv
from datetime import datetime
import pandas as pd

# Konfigürasyon ve diğer modüllerin import edildiğini varsayıyoruz
from core.logging_config import LoggingConfig
from adapters.binance.binance_client import BinanceClient
from strategies.atr_strategy.strategy import Strategy
from strategies.atr_strategy.config import Config
from strategies.atr_strategy.executor import Executor
from core.telegram.telegram_notifier import TelegramNotifier
from core.signal_logger import signal_logger

class Bot:
    def __init__(self, symbol, timeframe, leverage, trade_amount):

        # NTP senkronizasyonunu en başta yap
        self._sync_ntp_time()

        # Windows sisteminde zamanı senkronize et
        if platform.system() == 'Windows':
            os.system('w32tm /resync')
        self.logging_config = LoggingConfig()

        # Logging ayarları - Yeni dosya tabanlı sistem
        self.logger = self.logging_config.setup_logging("atr_strategy_bot")
        self.logger.info("🚀 ATR Strategy Bot başlatılıyor...")
        
        # Konfigürasyon ayarları
        self.symbol = symbol
        self.timeframe = timeframe
        self.leverage = leverage
        self.trade_amount = trade_amount

        """
        Trading Bot inizializasyonu
        - Konfigürasyon ayarları
        - Gerekli servislerin başlatılması
        """

        # Telegram bildirim servisi
        self.telegram = TelegramNotifier(symbol=symbol)

        # Config dosyasını yükle
        self.config = Config()

        # Binance client ve diğer servislerin inizializasyonu
        self.client = BinanceClient(symbol, timeframe, leverage)
        self.strategy = Strategy(timeframe)
        self.executor = Executor(self.client, symbol, trade_amount)

        # Durum değişkenleri
        self.position = 0  # 0: No Position, 1: Long, -1: Short
        self.entry_price = 0.0
        self.last_check_time = time.time()
        self.running = False
        
        # Timeframe kontrolü için yeni değişkenler
        self.last_trade_candle_start = None  # Son işlem yapılan mumun başlangıç zamanı
        
        # Sinyal onay sistemi için değişkenler
        self.pending_signal = None
        self.pending_signal_time = None
        self.pending_signal_data = None
        
        # NTP senkronizasyon thread'i için
        self.ntp_sync_running = False
        self.ntp_thread = None

        # Signal ID takibi için
        self.current_signal_id = None
        self.position_entry_price = None

    def _sync_ntp_time(self, is_periodic=False):
        """NTP sunucusu ile sistem saatini senkronize eder"""
        ntp_servers = [
            'pool.ntp.org',
            'time.google.com',
            'time.cloudflare.com',
            'time.windows.com',
            'tr.pool.ntp.org'
        ]
        
        if not is_periodic:
            print("Bot başlatılıyor, NTP senkronizasyonu yapılıyor...")
        
        for server in ntp_servers:
            try:
                if not is_periodic:
                    print(f"NTP senkronizasyonu başlatılıyor: {server}")
                
                # NTP client oluştur
                client = ntplib.NTPClient()
                
                # NTP sunucusundan zaman al (5 saniye timeout)
                response = client.request(server, version=3, timeout=5)
                
                # NTP zamanını al
                ntp_time = response.tx_time
                
                # Sistem zamanı ile NTP zamanı arasındaki farkı hesapla
                system_time = time.time()
                time_diff = ntp_time - system_time
                
                if is_periodic:
                    logging.info(f"Periyodik NTP senkronizasyonu başarılı: {server}")
                    logging.info(f"Sistem zamanı ile NTP zamanı arasındaki fark: {time_diff:.3f} saniye")
                else:
                    print(f"NTP senkronizasyonu başarılı: {server}")
                    print(f"Sistem zamanı ile NTP zamanı arasındaki fark: {time_diff:.3f} saniye")
                
                # Eğer fark 1 saniyeden fazlaysa uyarı ver
                if abs(time_diff) > 1.0:
                    warning_msg = f"UYARI: Sistem zamanında {time_diff:.3f} saniye fark tespit edildi!"
                    if is_periodic:
                        logging.warning(warning_msg)
                        # Büyük fark varsa Telegram bildirimi gönder
                        if abs(time_diff) > 5.0:
                            self.telegram.send_notification(f"⚠️ NTP Senkronizasyon Uyarısı\nZaman farkı: {time_diff:.3f} saniye")
                    else:
                        print(warning_msg)
                
                # İlk başarılı NTP senkronizasyonundan sonra çık
                return True
                
            except (socket.timeout, socket.gaierror, ntplib.NTPException) as e:
                error_msg = f"UYARI: NTP sunucusu {server} ile bağlantı kurulamadı: {e}"
                if is_periodic:
                    logging.warning(error_msg)
                else:
                    print(error_msg)
                continue
            except Exception as e:
                error_msg = f"UYARI: NTP senkronizasyonu hatası {server}: {e}"
                if is_periodic:
                    logging.warning(error_msg)
                else:
                    print(error_msg)
                continue
        
        error_msg = "HATA: Hiçbir NTP sunucusu ile bağlantı kurulamadı!"
        if is_periodic:
            logging.error(error_msg)
        else:
            print(error_msg)
        return False

    def _periodic_ntp_sync(self):
        """Her 3 dakikada bir NTP senkronizasyonu yapar"""
        while self.ntp_sync_running:
            try:
                # 3 dakika (180 saniye) bekle
                time.sleep(180)
                
                if self.ntp_sync_running:  # Hala çalışıyor mu kontrol et
                    logging.info("Periyodik NTP senkronizasyonu başlatılıyor...")
                    success = self._sync_ntp_time(is_periodic=True)
                    
                    if success:
                        logging.info("Periyodik NTP senkronizasyonu başarılı")
                    else:
                        logging.warning("Periyodik NTP senkronizasyonu başarısız")
                        
            except Exception as e:
                logging.error(f"Periyodik NTP senkronizasyon hatası: {e}")
                time.sleep(60)  # Hata durumunda 1 dakika bekle

    def _start_ntp_sync_thread(self):
        """NTP senkronizasyon thread'ini başlatır"""
        if not self.ntp_sync_running:
            self.ntp_sync_running = True
            self.ntp_thread = threading.Thread(target=self._periodic_ntp_sync, daemon=True)
            self.ntp_thread.start()
            logging.info("Periyodik NTP senkronizasyon thread'i başlatıldı (her 3 dakika)")

    def _stop_ntp_sync_thread(self):
        """NTP senkronizasyon thread'ini durdurur"""
        if self.ntp_sync_running:
            self.ntp_sync_running = False
            if self.ntp_thread and self.ntp_thread.is_alive():
                logging.info("NTP senkronizasyon thread'i durduruluyor...")

    def execute_trade_with_notification(self, side, quantity, entry_price, stop_loss, take_profit):
        """
        Trade işlemini yapıp bildirim gönderen yardımcı fonksiyon
        - İşlem gerçekleştirme
        - Telegram bildirim gönderme
        """
        try:
            # Pozisyon açılışını logla
            self._log_trade_activity_to_csv(
                action="POSITION_OPEN",
                side=side,
                quantity=quantity,
                price=entry_price,
                details=f"TP: {take_profit:.4f}, SL: {stop_loss:.4f}"
            )
            
            result = self.executor.execute_trade(
                side=side,
                quantity=quantity,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit
            )

            if result:
                # İşlem başarılı olduğunda order oluşturma bilgilerini logla
                self._log_trade_activity_to_csv(
                    action="ORDERS_CREATED",
                    side=side,
                    quantity=quantity,
                    price=entry_price,
                    details=f"Main Order + TP Order + SL Order created successfully"
                )
                
                profit_percent = abs((take_profit - entry_price) / entry_price * 100)
                message = self.create_trade_message(
                    side=side,
                    quantity=quantity,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    profit_percent=profit_percent
                )
                self.telegram.send_notification(message)
            else:
                # İşlem başarısız olduğunda logla
                self._log_trade_activity_to_csv(
                    action="TRADE_FAILED",
                    side=side,
                    quantity=quantity,
                    price=entry_price,
                    details="Trade execution failed"
                )

            return result
        except Exception as e:
            logging.error(f"Trade işlemi sırasında hata: {e}")
            # Hata durumunu logla
            self._log_trade_activity_to_csv(
                action="TRADE_ERROR",
                side=side if 'side' in locals() else "UNKNOWN",
                quantity=quantity if 'quantity' in locals() else 0,
                price=entry_price if 'entry_price' in locals() else 0,
                details=f"Error: {str(e)}"
            )
            self.telegram.send_notification(f"⚠️ Trade hatası: {str(e)}")
            return False

    def _log_trade_activity_to_csv(self, action, side="", quantity=0, price=0, details="", signal_data=None):
        """Tüm trade aktivitelerini CSV dosyasına kaydeder"""
        try:
            # logs klasörü yoksa oluştur
            os.makedirs('logs', exist_ok=True)
            
            # CSV dosya yolu - symbol bazlı trade log
            csv_filename = f'logs/atr_trades_{self.symbol.lower()}.csv'
            
            # Signal data varsa indikatör değerlerini al
            signal_indicators = ""
            if signal_data is not None:
                indicators = []
                # Temel indikatörler
                if 'Close' in signal_data:
                    indicators.append(f"Close: {signal_data['Close']:.4f}")
                if 'atr' in signal_data:
                    indicators.append(f"ATR: {signal_data['atr']:.6f}")
                if 'atr_upper' in signal_data:
                    indicators.append(f"ATR_Upper: {signal_data['atr_upper']:.4f}")
                if 'atr_lower' in signal_data:
                    indicators.append(f"ATR_Lower: {signal_data['atr_lower']:.4f}")
                if 'ema_9' in signal_data:
                    indicators.append(f"EMA_9: {signal_data['ema_9']:.4f}")
                if 'ema_21' in signal_data:
                    indicators.append(f"EMA_21: {signal_data['ema_21']:.4f}")
                if 'rsi' in signal_data:
                    indicators.append(f"RSI: {signal_data['rsi']:.2f}")
                # Sinyal koşulları
                if 'buy_signal' in signal_data:
                    indicators.append(f"Buy_Signal: {signal_data['buy_signal']}")
                if 'sell_signal' in signal_data:
                    indicators.append(f"Sell_Signal: {signal_data['sell_signal']}")
                if 'buy' in signal_data:
                    indicators.append(f"Buy: {signal_data['buy']}")
                if 'sell' in signal_data:
                    indicators.append(f"Sell: {signal_data['sell']}")
                
                signal_indicators = " | ".join(indicators)
            
            # CSV verisi
            csv_data = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Tarih/Saat
                self.symbol,                                    # Sembol
                action,                                        # Aksiyon (POSITION_OPEN, ORDERS_CREATED, POSITION_CLOSE, etc.)
                side,                                          # BUY/SELL
                f"{quantity:.6f}" if quantity else "",         # Miktar
                f"{price:.4f}" if price else "",               # Fiyat
                details,                                       # Detaylar
                signal_indicators                              # Sinyal indikatörleri
            ]
            
            # Dosya yoksa header ekle
            file_exists = os.path.exists(csv_filename)
            
            with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Header yazma (sadece dosya yoksa)
                if not file_exists:
                    header = ['Tarih/Saat', 'Sembol', 'Aksiyon', 'Yön', 'Miktar', 'Fiyat', 'Detaylar', 'Sinyal_İndikatörleri']
                    writer.writerow(header)
                
                # Veri yazma
                writer.writerow(csv_data)
            
            logging.info(f"Trade aktivitesi CSV'ye kaydedildi: {action}")
            
        except Exception as e:
            logging.error(f"Trade aktivitesi CSV log kaydetme hatası: {e}")

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
        elif isinstance(timestamp, str):
            dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
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

    def _is_same_candle_timeframe(self, current_time):
        """Mevcut zamanın son işlem yapılan mum ile aynı timeframe'de olup olmadığını kontrol eder"""
        if not self.last_trade_candle_start:
            return False
        
        current_candle_start = self._get_candle_start_time(current_time)
        
        return current_candle_start == self.last_trade_candle_start

    def create_trade_message(self, side, quantity, entry_price, stop_loss, take_profit, profit_percent):
        """
        Telegram mesajını formatlayan fonksiyon
        - Detaylı ticaret bilgilerini içeren mesaj oluşturma
        """
        emoji = "🟢" if side == 'BUY' else "🔴"
        direction = "ALIM" if side == 'BUY' else "SATIM"

        return f"""{emoji} <b>YENİ İŞLEM AÇILDI</b> {emoji}

<b>Sembol:</b> {self.symbol}
<b>İşlem:</b> {direction}
<b>Miktar:</b> {quantity:.4f}
<b>Giriş:</b> {entry_price:.4f}
<b>TP:</b> {take_profit:.4f} (+{profit_percent:.2f}%)
<b>SL:</b> {stop_loss:.4f}
<b>Kaldıraç:</b> {self.leverage}x

⏰ {time.strftime('%d.%m.%Y %H:%M')}"""

    def check_and_sync_position(self):
        """
        Pozisyon durumunu kontrol et ve senkronize et
        - API'den gerçek pozisyon durumunu alma
        - Tutarsızlıkları düzeltme
        """
        try:
            # API'den gerçek pozisyon durumunu al
            actual_position = self.executor.get_position_direction(self.symbol)

            # Eğer tutarsızlık varsa
            if actual_position != self.position:
                logging.warning(f"Pozisyon tutarsızlığı: Bot={self.position}, Gerçek={actual_position}")
                
                # Pozisyon kapandıysa detaylı bildirim gönder
                if self.position != 0 and actual_position == 0:
                    self._send_position_closed_notification()
                
                self.position = actual_position

                # Pozisyon yoksa state'i resetle
                if actual_position == 0:
                    self.entry_price = 0.0
                    logging.info("Pozisyon kapatılmış, durum sıfırlandı")

            return actual_position
        except Exception as e:
            logging.error(f"Pozisyon senkronizasyon hatası: {e}")
            return self.position  # Hata durumunda mevcut değeri koru

    def _send_position_closed_notification(self):
        """Pozisyon kapanma bildirimi gönderir ve CSV log kaydı yapar"""
        try:
            # Mevcut fiyatı al
            current_price = float(self.client.client.futures_symbol_ticker(symbol=self.symbol)['price'])
            current_time = datetime.now()
            
            # Kar/zarar hesapla
            if self.entry_price > 0:
                if self.position == 1:  # Long pozisyon
                    pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100
                else:  # Short pozisyon
                    pnl_percent = ((self.entry_price - current_price) / self.entry_price) * 100
                
                # Kaldıraçlı kar/zarar
                leveraged_pnl = pnl_percent * self.leverage
                
                # Emoji ve durum
                if leveraged_pnl > 0:
                    emoji = "💰"
                    status = "KAR"
                else:
                    emoji = "📉"
                    status = "ZARAR"
                
                position_type = "LONG" if self.position == 1 else "SHORT"
                
                # CSV log kaydı - Pozisyon kapanışı
                self._log_position_close_to_csv(
                    timestamp=current_time,
                    symbol=self.symbol,
                    position_type=position_type,
                    entry_price=self.entry_price,
                    exit_price=current_price,
                    price_change_percent=pnl_percent,
                    leveraged_pnl_percent=leveraged_pnl,
                    status=status
                )
                
                # Trade aktivitesi log kaydı
                self._log_trade_activity_to_csv(
                    action="POSITION_CLOSE",
                    side=position_type,
                    quantity=0,
                    price=current_price,
                    details=f"Entry: {self.entry_price:.4f}, Exit: {current_price:.4f}, P&L: {leveraged_pnl:+.2f}%, Status: {status}"
                )
                
                # Signal logger'a kar/zarar bilgilerini bildir
                if self.current_signal_id and self.position_entry_price:
                    try:
                        # USDT cinsinden kar/zarar hesapla (yaklaşık)
                        pnl_usdt = (leveraged_pnl / 100) * self.trade_amount
                        
                        signal_logger.update_position_closed(
                            self.current_signal_id,
                            current_price,
                            pnl_usdt,
                            leveraged_pnl
                        )
                        logging.info(f"Signal {self.current_signal_id} için pozisyon kapanış bilgisi güncellendi")
                        
                        # Signal takibini temizle
                        self.current_signal_id = None
                        self.position_entry_price = None
                        
                    except Exception as e:
                        logging.error(f"Signal logger pozisyon kapanış güncelleme hatası: {e}")
                
                message = f"""{emoji} <b>POZİSYON KAPANDI</b> {emoji}

<b>Sembol:</b> {self.symbol}
<b>Pozisyon:</b> {position_type}
<b>Giriş Fiyatı:</b> {self.entry_price:.4f}
<b>Kapanış Fiyatı:</b> {current_price:.4f}
<b>Fiyat Değişimi:</b> {pnl_percent:+.2f}%
<b>Kaldıraçlı P&L:</b> {leveraged_pnl:+.2f}%
<b>Durum:</b> {status}

⏰ {current_time.strftime('%d.%m.%Y %H:%M')}"""
                
                self.telegram.send_notification(message)
                logging.info(f"Pozisyon kapanma bildirimi gönderildi: {status} {leveraged_pnl:+.2f}%")
            else:
                # Entry price bilinmiyorsa basit bildirim
                self._log_trade_activity_to_csv(
                    action="POSITION_CLOSE",
                    details="Position closed - entry price unknown"
                )
                self.telegram.send_notification("🔄 Pozisyon kapatıldı")
                
        except Exception as e:
            logging.error(f"Pozisyon kapanma bildirimi hatası: {e}")
            # Hata durumunda basit bildirim gönder
            self._log_trade_activity_to_csv(
                action="POSITION_CLOSE_ERROR",
                details=f"Error: {str(e)}"
            )
            self.telegram.send_notification("🔄 Pozisyon kapatıldı")

    def _log_position_close_to_csv(self, timestamp, symbol, position_type, entry_price, exit_price, 
                                   price_change_percent, leveraged_pnl_percent, status):
        """Pozisyon kapanış bilgilerini CSV dosyasına kaydeder"""
        try:
            # logs klasörü yoksa oluştur
            os.makedirs('logs', exist_ok=True)
            
            # CSV dosya yolu - symbol bazlı farklılaştırma
            csv_filename = f'logs/atr_positions_{symbol.lower()}.csv'
            
            # CSV verisi
            csv_data = [
                timestamp.strftime('%Y-%m-%d %H:%M:%S'),  # Tarih/Saat
                symbol,                                    # Sembol
                position_type,                            # Pozisyon tipi
                f"{entry_price:.4f}",                    # Giriş fiyatı
                f"{exit_price:.4f}",                     # Çıkış fiyatı
                f"{price_change_percent:+.2f}%",         # Fiyat değişim yüzdesi
                f"{leveraged_pnl_percent:+.2f}%",        # Kaldıraçlı P&L yüzdesi
                status                                    # Durum (KAR/ZARAR)
            ]
            
            # Dosya yoksa header ekle
            file_exists = os.path.exists(csv_filename)
            
            with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Header yazma (sadece dosya yoksa)
                if not file_exists:
                    header = ['Tarih/Saat', 'Sembol', 'Pozisyon', 'Giriş Fiyatı', 
                             'Çıkış Fiyatı', 'Fiyat Değişimi', 'Kaldıraçlı P&L', 'Durum']
                    writer.writerow(header)
                
                # Veri yazma
                writer.writerow(csv_data)
            
            logging.info(f"Pozisyon kapanış bilgisi CSV'ye kaydedildi: {csv_filename}")
            
        except Exception as e:
            logging.error(f"CSV log kaydetme hatası: {e}")

    def process_signal(self, last_row):
        """
        Sinyal işleme fonksiyonu
        - Sinyal tipine göre işlem başlatma
        - Miktar ve fiyat ayarlama
        - Başarılı işlem durumunda True döndürür
        """
        price = last_row['Close']
        quantity = self.trade_amount / price
        adjusted_quantity = self.client.adjust_quantity(quantity)

        if adjusted_quantity is None:
            logging.error("Miktar ayarlanamadı.")
            return False

        if last_row['buy']:
            side = 'BUY'
            signal_type = 'buy'
        else:
            side = 'SELL'
            signal_type = 'sell'

        self.entry_price = self.client.adjust_price(price)
        if self.entry_price is None or self.entry_price <= 0:
            logging.error("Geçersiz giriş fiyatı.")
            return False

        take_profit, stop_loss = self.executor.calculate_take_profit_stop_loss(
            entry_price=self.entry_price,
            side=side
        )

        if self.execute_trade_with_notification(
                side=side,
                quantity=adjusted_quantity,
                entry_price=self.entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit
        ):
            self.position = 1 if side == 'BUY' else -1
            self.position_entry_price = self.entry_price
            
            # Signal logger'a pozisyon açıldığını bildir
            if self.current_signal_id:
                try:
                    signal_logger.update_position_opened(self.current_signal_id, self.entry_price)
                    logging.info(f"Signal {self.current_signal_id} için pozisyon açılış bilgisi güncellendi")
                except Exception as e:
                    logging.error(f"Signal logger pozisyon açılış güncelleme hatası: {e}")
            
            logging.info(f"Başarılı {side} işlemi: Entry={self.entry_price}")
            return True
        else:
            logging.error(f"İşlem başarısız: {side}")
            return False

    def trade_logic(self):
        """
        Gelişmiş ticaret mantığı - Sinyal onay sistemi ile
        - Pozisyon kontrolü
        - TP/SL izleme
        - Sinyal onay beklemesi
        - Otomatik işlem yönetimi
        """
        try:
            # 1. Bekleyen sinyal kontrolü
            if self.pending_signal:
                self._handle_pending_signal()
                return

            # 2. Pozisyon senkronizasyonu ve kontrol
            try:
                current_position = self.check_and_sync_position()
            except Exception as sync_error:
                logging.error(f"Pozisyon senkronizasyon hatası: {sync_error}")
                self.telegram.send_notification(f"⚠️ Pozisyon senkronizasyon hatası: {str(sync_error)}")
                return

            # 3. Aktif pozisyon varsa TP/SL kontrolü
            if current_position != 0:
                try:
                    # Pozisyon durumunu kontrol et
                    position_status = self.executor.monitor_position_status(self.symbol)

                    # Pozisyon kapatılması gerekiyorsa
                    if position_status == 'CLOSE':
                        logging.info("Pozisyon otomatik olarak kapatıldı")
                        self.position = 0
                        self.entry_price = 0.0
                        # Pozisyon kapandıktan sonra hemen yeni sinyal kontrolü yap
                        time.sleep(2)
                        return self.trade_logic()

                    # Pozisyon devam ediyorsa başka işlem yapma
                    return

                except Exception as monitor_error:
                    logging.error(f"Pozisyon izleme hatası: {monitor_error}")
                    self.telegram.send_notification(f"⚠️ Pozisyon izleme hatası: {str(monitor_error)}")
                    return

            # 4. Pozisyon yoksa sinyal kontrolü
            try:
                # Güncel veriyi çek
                df = self.client.fetch_data()

                # Veri kontrolü
                if df is None or df.empty:
                    logging.warning("Veri çekilemedi veya boş")
                    return

                # Stratejiye göre pozisyon belirleme
                df = self.strategy.determine_position(df)
                last_row = df.iloc[-1]

                # 5. Yeni sinyal kontrolü
                if last_row['buy']:
                    logging.info("Buy sinyali algılandı")
                    
                    # Aynı timeframe'de zaten işlem yapılıp yapılmadığını kontrol et
                    current_time = datetime.now()
                    if self._is_same_candle_timeframe(current_time):
                        logging.info(f"Aynı timeframe içinde zaten işlem yapıldı. İşlem atlanıyor. (Timeframe: {self.timeframe})")
                        return
                    
                    # Sinyali beklenmeye al
                    self._set_pending_signal('buy', last_row, current_time)
                        
                elif last_row['sell']:
                    logging.info("Sell sinyali algılandı")
                    
                    # Aynı timeframe'de zaten işlem yapılıp yapılmadığını kontrol et
                    current_time = datetime.now()
                    if self._is_same_candle_timeframe(current_time):
                        logging.info(f"Aynı timeframe içinde zaten işlem yapıldı. İşlem atlanıyor. (Timeframe: {self.timeframe})")
                        return
                    
                    # Sinyali beklenmeye al
                    self._set_pending_signal('sell', last_row, current_time)
                        
                else:
                    logging.debug("Herhangi bir sinyal bulunamadı")

            except Exception as signal_error:
                logging.error(f"Sinyal işleme hatası: {signal_error}")
                self.telegram.send_notification(f"⚠️ Sinyal işleme hatası: {str(signal_error)}")

        except Exception as critical_error:
            logging.critical(f"Kritik trade logic hatası: {critical_error}")
            self.telegram.send_notification(f"🚨 KRİTİK HATA: {str(critical_error)}")

    def _set_pending_signal(self, signal_type, row_data, current_time):
        """Sinyali beklenmeye alır"""
        self.pending_signal = signal_type
        self.pending_signal_time = current_time
        self.pending_signal_data = row_data.copy()
        
        # Sinyal tespitini logla
        self._log_trade_activity_to_csv(
            action="SIGNAL_DETECTED",
            side=signal_type.upper(),
            price=row_data['Close'],
            details=f"{signal_type} signal detected, waiting for confirmation ({self.config.signal_confirmation_delay}s)",
            signal_data=row_data
        )
        
        # Ortak sinyal kontrol CSV'ye yaz ve signal ID'yi kaydet
        try:
            self.current_signal_id = signal_logger.log_signal("ATR_Strategy", self.symbol, row_data)
            logging.info(f"Signal ID kaydedildi: {self.current_signal_id}")
        except Exception as e:
            logging.error(f"Sinyal kontrol logger hatası: {e}")
        
        logging.info(f"{signal_type.upper()} sinyali onay beklemesine alındı ({self.config.signal_confirmation_delay} saniye beklenecek)")

    def _handle_pending_signal(self):
        """Bekleyen sinyali işler"""
        if not self.pending_signal or not self.pending_signal_time:
            return
        
        current_time = datetime.now()
        elapsed_time = (current_time - self.pending_signal_time).total_seconds()
        
        # Bekleme süresi henüz dolmadıysa bekle
        if elapsed_time < self.config.signal_confirmation_delay:
            remaining_time = self.config.signal_confirmation_delay - elapsed_time
            logging.debug(f"Sinyal onay bekleniyor... Kalan süre: {remaining_time:.1f} saniye")
            return
        
        # Bekleme süresi doldu, sinyali yeniden kontrol et
        logging.info(f"Sinyal onay süresi doldu ({elapsed_time:.1f} saniye). Sinyal yeniden kontrol ediliyor...")
        
        try:
            # Güncel veriyi çek
            df = self.client.fetch_data()
            
            if df is None or df.empty:
                logging.warning("Sinyal onayı için veri çekilemedi, bekleyen sinyal iptal ediliyor")
                self._clear_pending_signal()
                return
            
            # Stratejiye göre pozisyon belirleme
            df = self.strategy.determine_position(df)
            last_row = df.iloc[-1]
            
            # Sinyal hala aktif mi kontrol et
            signal_still_active = False
            if self.pending_signal == 'buy' and last_row['buy']:
                signal_still_active = True
            elif self.pending_signal == 'sell' and last_row['sell']:
                signal_still_active = True
            
            if signal_still_active:
                logging.info(f"{self.pending_signal.upper()} sinyali onaylandı! İşlem gerçekleştiriliyor...")
                
                # Onaylanan sinyali logla
                self._log_trade_activity_to_csv(
                    action="SIGNAL_CONFIRMED",
                    side=self.pending_signal.upper(),
                    price=last_row['Close'],
                    details=f"{self.pending_signal} signal confirmed after {elapsed_time:.1f}s",
                    signal_data=last_row
                )
                
                # Ortak sinyal kontrol CSV'ye yaz (confirmed signal)
                try:
                    signal_logger.log_signal("ATR_Strategy", self.symbol, last_row)
                except Exception as e:
                    logging.error(f"Sinyal kontrol logger hatası: {e}")
                
                # Aynı timeframe'de zaten işlem yapılıp yapılmadığını kontrol et
                if self._is_same_candle_timeframe(current_time):
                    logging.info(f"Aynı timeframe içinde zaten işlem yapıldı. İşlem atlanıyor. (Timeframe: {self.timeframe})")
                    self._clear_pending_signal()
                    return
                
                # İşlemi yap
                if self.process_signal(last_row):
                    self.last_trade_candle_start = self._get_candle_start_time(current_time)
                    logging.info(f"Onaylanan sinyal ile işlem yapıldı. Timeframe başlangıcı: {self.last_trade_candle_start}")
                else:
                    logging.error("Onaylanan sinyal ile işlem yapılamadı")
                
            else:
                logging.info(f"{self.pending_signal.upper()} sinyali artık aktif değil, işlem iptal ediliyor")
                
                # İptal edilen sinyali logla
                self._log_trade_activity_to_csv(
                    action="SIGNAL_CANCELLED",
                    side=self.pending_signal.upper(),
                    price=last_row['Close'],
                    details=f"{self.pending_signal} signal cancelled after {elapsed_time:.1f}s - no longer active",
                    signal_data=last_row
                )
            
            # Bekleyen sinyali temizle
            self._clear_pending_signal()
            
        except Exception as e:
            logging.error(f"Bekleyen sinyal işleme hatası: {e}")
            self._clear_pending_signal()

    def _clear_pending_signal(self):
        """Bekleyen sinyali temizler"""
        self.pending_signal = None
        self.pending_signal_time = None
        self.pending_signal_data = None

    def start_trading(self):
        """
        Sürekli çalışan ticaret döngüsü
        - Her 10 saniyede bir trade_logic metodunu çağırır
        - Hata yönetimi ve bildirim sistemi
        """
        try:
            logging.info("🟢 Trading bot başlatıldı")
            # Bot başlangıcını logla
            self._log_trade_activity_to_csv(
                action="BOT_START",
                details=f"Bot started - Symbol: {self.symbol}, Timeframe: {self.timeframe}, Leverage: {self.leverage}x"
            )
            self.telegram.send_notification("🟢 Trading bot aktif hale getirildi")
            
            # Periyodik NTP senkronizasyon thread'ini başlat
            self._start_ntp_sync_thread()

            while True:
                try:
                    # Asıl ticaret mantığını çalıştır
                    self.trade_logic()

                    # 10 saniye bekle
                    time.sleep(10)

                except Exception as cycle_error:
                    logging.error(f"Ticaret döngüsü hatası: {cycle_error}")
                    self._log_trade_activity_to_csv(
                        action="TRADING_ERROR",
                        details=f"Trading cycle error: {str(cycle_error)}"
                    )
                    self.telegram.send_notification(f"⚠️ Ticaret döngüsü hatası: {str(cycle_error)}")

                    # Hatadan sonra kısa bir süre bekle
                    time.sleep(30)

        except KeyboardInterrupt:
            logging.info("🔴 Bot manuel olarak durduruldu")
            self._log_trade_activity_to_csv(
                action="BOT_STOP",
                details="Bot manually stopped by user"
            )
            self.telegram.send_notification("🔴 Bot manuel olarak durduruldu")
            # NTP thread'ini durdur
            self._stop_ntp_sync_thread()

        except Exception as start_error:
            logging.critical(f"Bot başlatma hatası: {start_error}")
            self._log_trade_activity_to_csv(
                action="BOT_CRITICAL_ERROR",
                details=f"Critical bot error: {str(start_error)}"
            )
            self.telegram.send_notification(f"🚨 BOT BAŞLATMA HATASI: {str(start_error)}")
            # NTP thread'ini durdur
            self._stop_ntp_sync_thread()

