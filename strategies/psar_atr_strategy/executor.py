import logging
from binance.exceptions import BinanceAPIException
import time
import ntplib
import socket
from core import TradingSignal
from adapters.binance.order_manager import OrderManager
from strategies.psar_atr_strategy.config import Config

class Executor:
    def __init__(self, client, symbol, trade_amount):
        self.config = Config()
        self.client = client
        self.symbol = symbol
        self.trade_amount = trade_amount
        self.recv_window = 60000  # 60 saniye
        self.time_offset = 0
        self.time_tolerance = 60000  # Zaman farkı toleransı 60000ms (60 saniye) - önceden 10000ms idi

        self.monitor_thread = None
        self.order_manager = OrderManager(client.client, self.symbol)
        self.pending_signal = None
        self.last_signal_time = None
        
        # NTP senkronizasyonunu önce yap
        self._sync_ntp_time()
        
        # Zaman senkronizasyonunu başlat
        self._sync_time()

    def _sync_ntp_time(self):
        """NTP sunucusu ile sistem saatini senkronize eder"""
        ntp_servers = [
            'pool.ntp.org',
            'time.google.com',
            'time.cloudflare.com',
            'time.windows.com',
            'tr.pool.ntp.org'
        ]
        
        for server in ntp_servers:
            try:
                logging.info(f"NTP senkronizasyonu başlatılıyor: {server}")
                
                # NTP client oluştur
                client = ntplib.NTPClient()
                
                # NTP sunucusundan zaman al (5 saniye timeout)
                response = client.request(server, version=3, timeout=5)
                
                # NTP zamanını al
                ntp_time = response.tx_time
                
                # Sistem zamanı ile NTP zamanı arasındaki farkı hesapla
                system_time = time.time()
                time_diff = ntp_time - system_time
                
                logging.info(f"NTP senkronizasyonu başarılı: {server}")
                logging.info(f"Sistem zamanı ile NTP zamanı arasındaki fark: {time_diff:.3f} saniye")
                
                # Eğer fark 1 saniyeden fazlaysa uyarı ver
                if abs(time_diff) > 1.0:
                    logging.warning(f"Sistem zamanında {time_diff:.3f} saniye fark tespit edildi!")
                
                # İlk başarılı NTP senkronizasyonundan sonra çık
                return
                
            except (socket.timeout, socket.gaierror, ntplib.NTPException) as e:
                logging.warning(f"NTP sunucusu {server} ile bağlantı kurulamadı: {e}")
                continue
            except Exception as e:
                logging.warning(f"NTP senkronizasyonu hatası {server}: {e}")
                continue
        
        logging.error("Hiçbir NTP sunucusu ile bağlantı kurulamadı!")

    def _sync_time(self):
        """Binance sunucusu ile zaman senkronizasyonu yapar"""
        try:
            server_time = self.client.client.get_server_time()
            local_time = int(time.time() * 1000)
            self.time_offset = server_time['serverTime'] - local_time
            logging.info(f"Zaman senkronizasyonu tamamlandı. Offset: {self.time_offset}ms")
        except Exception as e:
            logging.error(f"Zaman senkronizasyonu hatası: {e}")
            self.time_offset = 0

    def _get_timestamp(self):
        """Senkronize edilmiş zaman damgası döndürür"""
        # Büyük offset farkı varsa yeniden senkronize et (sadece kritik durumlar için)
        if abs(self.time_offset) > self.time_tolerance:  # 60 saniyeden fazla fark varsa
            try:
                self._sync_time()
            except Exception as e:
                logging.warning(f"Zaman senkronizasyonu başarısız, mevcut offset kullanılıyor: {e}")
        
        return int(time.time() * 1000) + self.time_offset

    def create_signal(self, side, quantity, entry_price, stop_loss, take_profit):
        """Yeni bir Signal objesi oluşturur"""
        return TradingSignal(side, quantity, entry_price, stop_loss, take_profit)

    def execute_trade(self, side, quantity, entry_price, stop_loss, take_profit):
        """Trade'i başlatır"""
        signal = self.create_signal(side, quantity, entry_price, stop_loss, take_profit)
        return self._execute_trade(signal)

    def _execute_trade(self, signal):
        """Asıl trade işlemini gerçekleştirir"""
        try:
            # Ana pozisyon emri
            main_order = self.order_manager.create_order_with_retry(
                side=signal.side,
                type='LIMIT',
                quantity=signal.quantity,
                price=signal.entry_price
            )

            if not main_order:
                logging.error("Ana emir oluşturulamadı")
                return False

            logging.info(f"Ana emir durumu: {main_order}")

            # Ana emrin gerçekleşmesini bekle
            max_wait = 30  # 30 saniye
            wait_interval = 5  # 5 saniyede bir kontrol

            if self.order_manager.monitor_order_status(main_order['orderId'], max_wait, wait_interval):
                logging.info("Ana emir başarıyla gerçekleşti")

                # 10 saniye bekle
                time.sleep(10)

                # Pozisyon doğrulama
                if not self.order_manager.verify_position(signal.side, signal.quantity):
                    logging.error("Pozisyon doğrulanamadı, TP/SL emirleri oluşturulmayacak")
                    return False

                # Stop Loss emri
                sl_order = self.order_manager.create_order_with_retry(
                    side='SELL' if signal.side == 'BUY' else 'BUY',
                    type='STOP_MARKET',
                    quantity=signal.quantity,
                    stop_price=signal.stop_loss
                )

                if not sl_order:
                    logging.error("Stop Loss emri oluşturulamadı")
                    return False

                logging.info(f"Stop Loss emri oluşturuldu: {sl_order}")

                # Take Profit emri
                tp_order = self.order_manager.create_order_with_retry(
                    side='SELL' if signal.side == 'BUY' else 'BUY',
                    type='TAKE_PROFIT_MARKET',
                    quantity=signal.quantity,
                    stop_price=signal.take_profit
                )

                if not tp_order:
                    logging.error("Take Profit emri oluşturulamadı")
                    # SL emrini iptal et
                    if sl_order:
                        self.order_manager.cancel_order(sl_order['orderId'])
                    return False

                logging.info(f"Take Profit emri oluşturuldu: {tp_order}")

                # Emirleri ilişkilendir
                self.order_manager.link_orders(
                    main_order['orderId'],
                    sl_order['orderId'],
                    tp_order['orderId']
                )

                # Arka planda TP/SL kontrol mekanizmasını başlat
                import threading
                tp_sl_check_thread = threading.Thread(
                    target=self.order_manager.monitor_and_ensure_tp_sl,
                    args=(signal.take_profit, signal.stop_loss, None, None, 60),
                    daemon=True
                )
                tp_sl_check_thread.start()
                logging.info("TP/SL kontrol mekanizması başlatıldı (60 saniye sonra kontrol edilecek)")

                return True

            else:
                logging.warning("Ana emir gerçekleşmedi, tüm emirler iptal ediliyor")
                self.order_manager.cancel_order(main_order['orderId'])
                return False

        except Exception as e:
            logging.error(f"Trade execution error: {e}")
            if 'main_order' in locals():
                self.order_manager.cancel_order(main_order['orderId'])
            return False

    def calculate_take_profit_stop_loss(self, entry_price, side):
        """Take profit ve stop loss fiyatlarını hesaplar"""
        try:
            if entry_price is None or entry_price <= 0:
                logging.error("Geçersiz giriş fiyatı.")
                return None, None

            # Sembol bilgilerini al
            symbol_info = self.client.client.futures_exchange_info()
            symbol_data = next((item for item in symbol_info['symbols'] if item['symbol'] == self.symbol), None)

            if not symbol_data:
                logging.error(f"Sembol bilgisi alınamadı: {self.symbol}")
                return None, None

            # Fiyat hassasiyeti (tick size) ve lot size bilgilerini al
            price_filter = next((f for f in symbol_data['filters'] if f['filterType'] == 'PRICE_FILTER'), None)
            lot_filter = next((f for f in symbol_data['filters'] if f['filterType'] == 'LOT_SIZE'), None)

            if not price_filter or not lot_filter:
                logging.error("Fiyat veya lot size filtresi bulunamadı")
                return None, None

            tick_size = float(price_filter['tickSize'])
            min_qty = float(lot_filter['minQty'])
            max_qty = float(lot_filter['maxQty'])
            step_size = float(lot_filter['stepSize'])

            # Fiyat hassasiyetini hesapla
            price_precision = len(str(tick_size).split('.')[-1]) if '.' in str(tick_size) else 0
            quantity_precision = len(str(step_size).split('.')[-1]) if '.' in str(step_size) else 0

            # Take profit ve stop loss hesaplama
            if side == 'BUY':
                take_profit_price = entry_price * (1 + self.config.take_profit_percent)
                stop_loss_price = entry_price * (1 - self.config.stop_loss_percent)
            else:  # SELL
                take_profit_price = entry_price * (1 - self.config.take_profit_percent)
                stop_loss_price = entry_price * (1 + self.config.stop_loss_percent)

            # Fiyatları Binance hassasiyetine göre yuvarla
            take_profit_price = round(take_profit_price, price_precision)
            stop_loss_price = round(stop_loss_price, price_precision)

            # Miktar hesaplama ve hassasiyet kontrolü
            quantity = self.trade_amount / entry_price
            quantity = round(quantity, quantity_precision)

            # Lot size limitlerini kontrol et
            if quantity < min_qty:
                logging.error(f"Hesaplanan miktar minimum lot size'dan küçük: {quantity} < {min_qty}")
                return None, None
            if quantity > max_qty:
                logging.error(f"Hesaplanan miktar maksimum lot size'dan büyük: {quantity} > {max_qty}")
                return None, None

            # Fiyat ve miktar bilgilerini logla
            logging.info(f"""
            Emir Detayları:
            - Giriş Fiyatı: {entry_price}
            - Take Profit: {take_profit_price}
            - Stop Loss: {stop_loss_price}
            - Miktar: {quantity}
            - Fiyat Hassasiyeti: {price_precision} ondalık basamak
            - Miktar Hassasiyeti: {quantity_precision} ondalık basamak
            - Lot Size: {min_qty} - {max_qty} (Step: {step_size})
            """)

            return take_profit_price, stop_loss_price

        except Exception as e:
            logging.error(f"Take profit/Stop loss hesaplama hatası: {e}")
            return None, None

    def check_price_distance(self, current_price, stop_price, price, position):
        """Fiyatlar arasındaki mesafeyi kontrol eder"""
        if current_price is None or stop_price is None or price is None:
            return False

        # Long pozisyon için stopPrice, current_price'tan düşük olmalı
        if position == 1 and stop_price > current_price:
            logging.error("Stop price, current price'tan düşük olmalı (Long pozisyon).")
            return False

        # Short pozisyon için stopPrice, current_price'tan yüksek olmalı
        if position == -1 and stop_price < current_price:
            logging.error("Stop price, current price'tan yüksek olmalı (Short pozisyon).")
            return False

        return True

    def get_position_direction(self, symbol):
        """Pozisyon yönünü belirler (1: Long, -1: Short, 0: Yok)"""
        try:
            # Zaman senkronizasyonunu kontrol et
            if abs(self.time_offset) > self.time_tolerance:  # 60 saniyeden fazla fark varsa
                self._sync_time()

            # recvWindow parametresini ekle
            positions = self.client.client.futures_position_information(
                symbol=symbol,
                timestamp=self._get_timestamp(),
                recvWindow=self.recv_window
            )

            if not positions:
                logging.warning("API'den pozisyon bilgisi alınamadı")
                # Pozisyon bilgisi alınamadığında açık emirleri kontrol et
                open_orders = self.client.client.futures_get_open_orders(
                    symbol=symbol,
                    timestamp=self._get_timestamp(),
                    recvWindow=self.recv_window
                )
                if open_orders:
                    logging.warning(f"Pozisyon bilgisi yok ama {len(open_orders)} açık emir var")
                    # Açık emirleri temizle
                    self.force_cancel_all_orders()
                return 0

            position = positions[0]
            position_amount = float(position['positionAmt'])
            position_size = abs(position_amount)
            unrealized_profit = float(position.get('unRealizedProfit', 0))

            # Pozisyon miktarı çok küçükse veya pozisyon kapalıysa
            if position_size < 0.00001 or (position_amount == 0 and unrealized_profit == 0):
                logging.info("Pozisyon kapalı veya ihmal edilebilir seviyede")
                # Açık emirleri kontrol et ve temizle
                open_orders = self.client.client.futures_get_open_orders(
                    symbol=symbol,
                    timestamp=self._get_timestamp(),
                    recvWindow=self.recv_window
                )
                if open_orders:
                    logging.warning(f"Pozisyon kapalı ama {len(open_orders)} açık emir var")
                    self.force_cancel_all_orders()
                return 0

            if position_amount > 0:
                logging.info(f"Long pozisyon tespit edildi: {position_amount}")
                return 1
            elif position_amount < 0:
                logging.info(f"Short pozisyon tespit edildi: {position_amount}")
                return -1

            return 0

        except BinanceAPIException as e:
            if e.code == -1021:  # Timestamp hatası
                logging.warning("Zaman senkronizasyonu hatası, yeniden senkronize ediliyor...")
                self._sync_time()
                return self.get_position_direction(symbol)  # Tekrar dene
            else:
                logging.error(f"Pozisyon kontrolü hatası: {e}")
                return 0
        except Exception as e:
            logging.error(f"Pozisyon kontrolü hatası: {e}")
            return 0

    def monitor_position_status(self, symbol):
        """Pozisyon durumunu izler"""
        try:
            position = self.get_position_direction(symbol)
            
            if position == 0:
                return False  # Pozisyon kapalı
            else:
                return True  # Pozisyon açık
                
        except Exception as e:
            logging.error(f"Pozisyon izleme hatası: {e}")
            return None

    def force_cancel_all_orders(self):
        """Tüm açık emirleri iptal eder"""
        try:
            # Zaman senkronizasyonunu kontrol et
            if abs(self.time_offset) > self.time_tolerance:  # 60 saniyeden fazla fark varsa
                self._sync_time()

            # Tüm emirleri iptal et
            self.client.client.futures_cancel_all_open_orders(
                symbol=self.symbol,
                timestamp=self._get_timestamp(),
                recvWindow=self.recv_window
            )
            logging.info("Tüm açık emirler iptal edildi")
        except BinanceAPIException as e:
            if e.code == -1021:  # Timestamp hatası
                logging.warning("Zaman senkronizasyonu hatası, yeniden senkronize ediliyor...")
                self._sync_time()
                self.force_cancel_all_orders()  # Tekrar dene
            else:
                logging.error(f"Emir iptal hatası: {e}")
        except Exception as e:
            logging.error(f"Emir iptal hatası: {e}") 