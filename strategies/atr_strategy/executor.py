import logging
from binance.exceptions import BinanceAPIException
import time
import subprocess
import ntplib
import socket
from core import TradingSignal
from adapters.binance.order_manager import OrderManager
from strategies.atr_strategy.config import Config


class Executor:
    def __init__(self, client, symbol, trade_amount, leverage=None):
        self.config = Config()
        self.client = client
        self.symbol = symbol
        self.trade_amount = trade_amount
        self.recv_window = 10000  # 10 saniye
        self.time_offset = 0
        self.last_sync_time = 0
        self.sync_interval = 30  # 30 saniye
        self.max_sync_retries = 5  # Maksimum senkronizasyon deneme sayısı
        self.sync_retry_delay = 2  # Senkronizasyon denemeleri arası bekleme süresi (saniye)
        self.time_tolerance = 60000  # Zaman farkı toleransı 60000ms (60 saniye) - önceden 10000ms idi

        # Leverage değerini öncelikle constructor'dan gelen değere göre ayarla
        if leverage is not None:
            self.config.leverage = leverage

        self.monitor_thread = None
        self.order_manager = OrderManager(client.client, self.symbol)
        self.pending_signal = None
        self.last_signal_time = None

        # NTP senkronizasyonunu önce yap
        self._sync_ntp_time()

        # Windows zaman senkronizasyonunu yap
        self._sync_windows_time()

        # İlk zaman senkronizasyonunu yap ve leverage ayarını yap
        self._initialize()

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

    def _sync_windows_time(self):
        """Windows sistem zamanını senkronize eder"""
        try:
            # Windows zaman senkronizasyonunu başlat
            subprocess.run(['w32tm', '/resync'], check=True, capture_output=True)
            logging.info("Windows zaman senkronizasyonu başlatıldı")

            # Senkronizasyonun tamamlanmasını bekle
            time.sleep(5)

        except subprocess.CalledProcessError as e:
            logging.error(f"Windows zaman senkronizasyonu hatası: {e}")
            raise
        except Exception as e:
            logging.error(f"Windows zaman senkronizasyonu hatası: {e}")
            raise

    def _initialize(self):
        """Başlangıç ayarlarını yapar"""
        try:
            # Zaman senkronizasyonunu yap
            self._initialize_time_sync()

            # Leverage ayarını yap
            self._initialize_leverage()

        except Exception as e:
            logging.critical(f"Bot başlatma hatası: {e}")
            raise

    def _initialize_time_sync(self):
        """Başlangıç zaman senkronizasyonunu yapar"""
        for attempt in range(self.max_sync_retries):
            try:
                # Sunucu zamanını al
                server_time = self.client.client.get_server_time()
                local_time = int(time.time() * 1000)

                # İlk offset hesapla
                self.time_offset = server_time['serverTime'] - local_time
                self.last_sync_time = time.time()

                logging.info(f"İlk zaman senkronizasyonu tamamlandı. Offset: {self.time_offset}ms")
                return

            except Exception as e:
                if attempt < self.max_sync_retries - 1:
                    logging.warning(f"Zaman senkronizasyonu denemesi {attempt + 1} başarısız: {e}")
                    time.sleep(self.sync_retry_delay)
                else:
                    logging.error(f"Zaman senkronizasyonu başarısız oldu: {e}")
                    raise

    def _sync_time(self):
        """Zaman senkronizasyonunu yapar"""
        try:
            # Windows zaman senkronizasyonunu kontrol et
            if abs(self.time_offset) > self.time_tolerance:  # 60 saniyeden fazla fark varsa
                self._sync_windows_time()

            # Sunucu zamanını al
            server_time = self.client.client.get_server_time()
            local_time = int(time.time() * 1000)

            # Yeni offset hesapla
            new_offset = server_time['serverTime'] - local_time

            # Offset değeri önemli ölçüde değiştiyse logla
            if abs(new_offset - self.time_offset) > self.time_tolerance:  # 60 saniyeden fazla fark varsa
                logging.info(f"Zaman senkronizasyonu güncellendi. Yeni offset: {new_offset}ms")

            self.time_offset = new_offset
            self.last_sync_time = time.time()

        except Exception as e:
            logging.error(f"Zaman senkronizasyonu hatası: {e}")
            raise

    def _get_timestamp(self):
        """Senkronize edilmiş zaman damgası döndürür"""
        current_time = time.time()

        # Son senkronizasyondan bu yana yeterli süre geçtiyse veya offset çok büyükse
        # Sadece büyük farklar için senkronizasyon yap (60 saniye yerine 30 saniye kontrolü)
        if (current_time - self.last_sync_time > self.sync_interval * 2 or  # 60 saniye geçtiyse
                abs(self.time_offset) > self.time_tolerance):  # 60 saniyeden fazla fark varsa
            try:
                self._sync_time()
            except Exception as e:
                logging.warning(f"Zaman senkronizasyonu başarısız, mevcut offset kullanılıyor: {e}")

        return int(time.time() * 1000) + self.time_offset

    def _initialize_leverage(self):
        """Başlangıç leverage ayarını yapar"""
        if not hasattr(self.config, 'leverage'):
            logging.error("Config sınıfında leverage özelliği bulunamadı")
            return

        try:
            # Leverage ayarını yap
            self.client.client.futures_change_leverage(
                symbol=self.symbol,
                leverage=self.config.leverage,
                timestamp=self._get_timestamp(),
                recvWindow=self.recv_window
            )
            logging.info(f"Leverage başarıyla {self.config.leverage}x olarak ayarlandı")

        except BinanceAPIException as e:
            if e.code == -1021:  # Timestamp hatası
                logging.error(f"Leverage ayarı başarısız oldu: {e}")
                raise
            else:
                logging.error(f"Leverage ayarı hatası: {e}")
                raise
        except Exception as e:
            logging.error(f"Leverage ayarı hatası: {e}")
            raise

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

            # Ana emrin gerçekleşmesini bekle
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

            # Fiyat hassasiyetini hesapla (örn: 0.1 için 1, 0.01 için 2)
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

    def is_position_open(self, symbol, max_retries=3, retry_delay=5):
        """Pozisyon durumunu kontrol eder"""
        for attempt in range(max_retries):
            try:
                positions = self.client.client.futures_position_information(symbol=symbol)
                if positions:
                    position = positions[0]
                    position_amount = float(position['positionAmt'])
                    position_size = abs(position_amount)

                    if position_size > 0:
                        logging.info(f"Açık pozisyon bulundu: {position_amount}")
                        return True
                    else:
                        logging.info("Açık pozisyon yok")
                        return False

                time.sleep(retry_delay)

            except Exception as e:
                logging.error(f"Pozisyon kontrolü hatası (Deneme {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(retry_delay)

        return None

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

    def check_and_manage_position(self, symbol, order_ids=None):
        """Pozisyon durumunu kontrol eder ve yönetir"""
        try:
            # Pozisyon bilgisini al
            positions = self.client.client.futures_position_information(symbol=symbol)
            if not positions:
                logging.warning("Pozisyon bilgisi alınamadı")
                # Açık emirleri kontrol et ve temizle
                open_orders = self.client.client.futures_get_open_orders(symbol=symbol)
                if open_orders:
                    logging.warning(f"Pozisyon bilgisi yok ama {len(open_orders)} açık emir var")
                    self.force_cancel_all_orders()
                return None  # Pozisyon bilgisi alınamadığında None döndür

            position = positions[0]
            position_amount = float(position['positionAmt'])
            unrealized_profit = float(position.get('unRealizedProfit', 0))

            # Pozisyon kapalıysa veya çok küçükse
            if abs(position_amount) < 0.00001 or (position_amount == 0 and unrealized_profit == 0):
                # Açık emirleri kontrol et
                open_orders = self.client.client.futures_get_open_orders(symbol=symbol)
                if open_orders:
                    logging.warning(f"Pozisyon kapalı ama {len(open_orders)} açık emir var")
                    # Tüm emirleri temizle
                    self.force_cancel_all_orders()
                return False  # Pozisyon kapalı

            return True  # Pozisyon açık

        except Exception as e:
            logging.error(f"Pozisyon kontrol hatası: {e}")
            return None  # Hata durumunda None döndür

    def monitor_position_status(self, symbol, max_retries=3, retry_delay=5):
        """Pozisyon durumunu sürekli kontrol eder"""
        for attempt in range(max_retries):
            try:
                # Pozisyon bilgisini al
                positions = self.client.client.futures_position_information(symbol=symbol)
                if not positions:
                    logging.warning("Pozisyon bilgisi alınamadı")
                    # Açık emirleri kontrol et ve temizle
                    open_orders = self.client.client.futures_get_open_orders(symbol=symbol)
                    if open_orders:
                        logging.warning(f"Pozisyon bilgisi yok ama {len(open_orders)} açık emir var")
                        self.force_cancel_all_orders()
                    return None

                position = positions[0]
                position_amount = float(position['positionAmt'])
                unrealized_profit = float(position.get('unRealizedProfit', 0))

                # Pozisyon kapalıysa veya çok küçükse
                if abs(position_amount) < 0.00001 or (position_amount == 0 and unrealized_profit == 0):
                    # Açık emirleri kontrol et
                    open_orders = self.client.client.futures_get_open_orders(symbol=symbol)
                    if open_orders:
                        logging.warning(f"Pozisyon kapalı ama {len(open_orders)} açık emir var")
                        # Tüm emirleri temizle
                        self.force_cancel_all_orders()
                    return False

                # Pozisyon açıksa
                logging.info(f"Aktif pozisyon bulundu: {position_amount}")
                return True

            except Exception as e:
                logging.error(f"Pozisyon kontrolü hatası (Deneme {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    return None

        return None

    def execute_strategy(self):
        """Stratejiyi çalıştırır ve sinyal doğrulama mantığını uygular"""
        try:
            # Önce pozisyon kontrolü yap
            position_status = self.monitor_position_status(self.symbol)

            # Eğer pozisyon kontrolü başarısız olduysa (None)
            if position_status is None:
                logging.warning("Pozisyon bilgisi alınamadı, sinyal kontrolü yapılıyor...")
                # Mevcut fiyatı al
                current_price = float(self.client.client.futures_symbol_ticker(symbol=self.symbol)['price'])

                # Strateji sinyallerini al
                df = self.get_strategy_data()
                signal = self.strategy.get_trade_signal(df)

                # Eğer yeni bir sinyal varsa
                if signal in ['buy', 'sell'] and self.pending_signal is None:
                    self.pending_signal = signal
                    self.last_signal_time = time.time()
                    logging.info(f"Yeni sinyal alındı: {signal}. 1 dakika bekleniyor...")

                # Bekleyen sinyal varsa ve 1 dakika geçtiyse
                elif self.pending_signal is not None and self.last_signal_time is not None:
                    time_diff = time.time() - self.last_signal_time
                    if time_diff >= 60:  # 1 dakika geçtiyse
                        if signal == self.pending_signal:
                            # Pozisyon durumunu tekrar kontrol et
                            position_status = self.monitor_position_status(self.symbol)
                            if position_status is True:  # Pozisyon açıksa
                                self._execute_confirmed_signal(signal, current_price)
                                self.pending_signal = None
                                self.last_signal_time = None
                            else:
                                logging.warning("Pozisyon durumu uygun değil, sinyal iptal ediliyor")
                                self.pending_signal = None
                                self.last_signal_time = None
                        else:
                            logging.info("Sinyal artık geçerli değil, bekleyen sinyal iptal ediliyor")
                            self.pending_signal = None
                            self.last_signal_time = None
                return

            # Eğer pozisyon kapalıysa (False)
            elif position_status is False:
                logging.warning("Pozisyon kapalı, yeni sinyal aranıyor...")
                # Mevcut fiyatı al
                current_price = float(self.client.client.futures_symbol_ticker(symbol=self.symbol)['price'])

                # Strateji sinyallerini al
                df = self.get_strategy_data()
                signal = self.strategy.get_trade_signal(df)

                # Eğer yeni bir sinyal varsa
                if signal in ['buy', 'sell'] and self.pending_signal is None:
                    self.pending_signal = signal
                    self.last_signal_time = time.time()
                    logging.info(f"Yeni sinyal alındı: {signal}. 1 dakika bekleniyor...")
                return

            # Pozisyon açıksa (True) normal akışa devam et
            current_price = float(self.client.client.futures_symbol_ticker(symbol=self.symbol)['price'])
            df = self.get_strategy_data()
            signal = self.strategy.get_trade_signal(df)

            current_time = time.time()

            # Eğer bekleyen bir sinyal varsa ve 1 dakika geçtiyse
            if self.pending_signal is not None and self.last_signal_time is not None:
                time_diff = current_time - self.last_signal_time

                if time_diff >= 60:  # 1 dakika geçtiyse
                    # Sinyal hala geçerli mi kontrol et
                    if signal == self.pending_signal:
                        # Pozisyon durumunu tekrar kontrol et
                        position_status = self.monitor_position_status(self.symbol)
                        if position_status is True:  # Pozisyon açıksa
                            # Sinyal hala geçerliyse işlemi gerçekleştir
                            self._execute_confirmed_signal(signal, current_price)
                            self.pending_signal = None
                            self.last_signal_time = None
                        else:
                            logging.warning("Pozisyon durumu uygun değil, sinyal iptal ediliyor")
                            self.pending_signal = None
                            self.last_signal_time = None
                    else:
                        # Sinyal artık geçerli değilse, bekleyen sinyali temizle
                        logging.info("Sinyal artık geçerli değil, bekleyen sinyal iptal ediliyor")
                        self.pending_signal = None
                        self.last_signal_time = None

            # Yeni sinyal geldiğinde
            elif signal in ['buy', 'sell'] and self.pending_signal is None:
                # Pozisyon durumunu kontrol et
                position_status = self.monitor_position_status(self.symbol)
                if position_status is True:  # Pozisyon açıksa
                    self.pending_signal = signal
                    self.last_signal_time = current_time
                    logging.info(f"Yeni sinyal alındı: {signal}. 1 dakika bekleniyor...")
                else:
                    logging.warning("Pozisyon durumu uygun değil, yeni sinyal alınmayacak")

        except Exception as e:
            logging.error(f"Strateji çalıştırma hatası: {e}")
            # Hata durumunda bekleyen sinyali sıfırla
            self.pending_signal = None
            self.last_signal_time = None

    def _execute_confirmed_signal(self, signal, current_price):
        """Doğrulanmış sinyali işleme alır"""
        try:
            side = 'BUY' if signal == 'buy' else 'SELL'

            # Take profit ve stop loss hesapla
            take_profit, stop_loss = self.calculate_take_profit_stop_loss(current_price, side)

            if take_profit is None or stop_loss is None:
                logging.error("Take profit veya stop loss hesaplanamadı")
                return

            # İşlem miktarını hesapla
            quantity = self.trade_amount / current_price

            # İşlemi gerçekleştir
            success = self.execute_trade(side, quantity, current_price, stop_loss, take_profit)

            if success:
                logging.info(f"İşlem başarıyla gerçekleştirildi: {side} @ {current_price}")
            else:
                logging.error(f"İşlem gerçekleştirilemedi: {side} @ {current_price}")

        except Exception as e:
            logging.error(f"Sinyal işleme hatası: {e}")