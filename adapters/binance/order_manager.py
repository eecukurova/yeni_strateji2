import logging
from binance.exceptions import BinanceAPIException
import time

class OrderManager:
    def __init__(self, client, symbol):
        self.client = client
        self.symbol = symbol
        self.active_orders = {}
        self.order_relationships = {}  # Ana emir ve bağlı emirler arasındaki ilişkiyi tutar
        self.max_retries = 3  # Maksimum yeniden deneme sayısı
        self.retry_delay = 2  # Denemeler arası bekleme süresi (saniye)
        self.price_adjustment = 0.0001  # Her denemede fiyat ayarlama miktarı

    def create_order(self, side, type, quantity, price=None, stop_price=None, take_profit=None, parent_order_id=None):
        """Emir oluşturur ve takip eder"""
        try:
            order_params = {
                'symbol': self.symbol,
                'side': side,
                'type': type,
                'quantity': quantity,
                'timeInForce': 'GTC'
            }

            if price:
                order_params['price'] = price
            if stop_price:
                order_params['stopPrice'] = stop_price
            if take_profit:
                order_params['takeProfitPrice'] = take_profit

            order = self.client.futures_create_order(**order_params)
            self.active_orders[order['orderId']] = order

            # Emir ilişkilerini kaydet
            if parent_order_id:
                if parent_order_id not in self.order_relationships:
                    self.order_relationships[parent_order_id] = []
                self.order_relationships[parent_order_id].append(order['orderId'])

            return order
        except Exception as e:
            logging.error(f"Emir oluşturma hatası: {e}")
            return None

    def cancel_order(self, order_id):
        """Belirli bir emri iptal eder"""
        try:
            result = self.client.futures_cancel_order(
                symbol=self.symbol,
                orderId=order_id
            )
            if order_id in self.active_orders:
                del self.active_orders[order_id]
            return result
        except Exception as e:
            logging.error(f"Emir iptal hatası: {e}")
            return None

    def cancel_all_orders(self):
        """Tüm emirleri iptal eder"""
        try:
            result = self.client.futures_cancel_all_open_orders(symbol=self.symbol)
            self.active_orders.clear()
            return result
        except Exception as e:
            logging.error(f"Tüm emirleri iptal hatası: {e}")
            return None

    def get_order_status(self, order_id):
        """Emir durumunu kontrol eder"""
        try:
            return self.client.futures_get_order(
                symbol=self.symbol,
                orderId=order_id
            )
        except Exception as e:
            logging.error(f"Emir durumu kontrol hatası: {e}")
            return None

    def cancel_related_orders(self, order_id):
        """Bir emirle ilişkili tüm emirleri iptal eder"""
        try:
            # İlişkili emirleri bul
            related_orders = self.order_relationships.get(order_id, [])

            # İlişkili emirleri iptal et
            for related_order_id in related_orders:
                if related_order_id in self.active_orders:
                    try:
                        # Önce emir durumunu kontrol et
                        order_status = self.get_order_status(related_order_id)
                        if order_status and order_status['status'] in ['NEW', 'PARTIALLY_FILLED']:
                            self.cancel_order(related_order_id)
                            logging.info(f"İlişkili emir iptal edildi: {related_order_id}")
                        else:
                            logging.info(f"İlişkili emir zaten gerçekleşmiş veya iptal edilmiş: {related_order_id}")
                    except BinanceAPIException as e:
                        if e.code == -2011:  # Unknown order
                            logging.info(f"İlişkili emir zaten gerçekleşmiş: {related_order_id}")
                        else:
                            logging.error(f"İlişkili emir iptal hatası: {e}")

            # İlişkiyi temizle
            if order_id in self.order_relationships:
                del self.order_relationships[order_id]

            # Ana emri iptal etmeyi dene
            try:
                if order_id in self.active_orders:
                    order_status = self.get_order_status(order_id)
                    if order_status and order_status['status'] in ['NEW', 'PARTIALLY_FILLED']:
                        self.cancel_order(order_id)
                        logging.info(f"Ana emir iptal edildi: {order_id}")
                    else:
                        logging.info(f"Ana emir zaten gerçekleşmiş veya iptal edilmiş: {order_id}")
            except BinanceAPIException as e:
                if e.code == -2011:  # Unknown order
                    logging.info(f"Ana emir zaten gerçekleşmiş: {order_id}")
                else:
                    logging.error(f"Ana emir iptal hatası: {e}")

        except Exception as e:
            logging.error(f"İlişkili emirleri iptal hatası: {e}")

    def monitor_order_status(self, order_id, max_wait=30, check_interval=5):
        """Emir durumunu sürekli kontrol eder ve ilişkili emirleri yönetir"""
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                order_status = self.get_order_status(order_id)
                if not order_status:
                    return False

                if order_status['status'] == 'FILLED':
                    # Emir gerçekleştiyse ilişkili emirleri kontrol et ve iptal et
                    self.cancel_related_orders(order_id)
                    return True
                elif order_status['status'] in ['CANCELED', 'REJECTED', 'EXPIRED']:
                    # Emir iptal edildiyse ilişkili emirleri de iptal et
                    self.cancel_related_orders(order_id)
                    return False
                elif order_status['status'] == 'PARTIALLY_FILLED':
                    # Kısmi gerçekleşme durumunda devam et
                    pass

                # Kalan süreyi hesapla
                remaining_time = max_wait - (time.time() - start_time)
                sleep_time = min(check_interval, remaining_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except BinanceAPIException as e:
                if e.code == -2011:  # Unknown order
                    logging.info(f"Emir zaten gerçekleşmiş veya iptal edilmiş: {order_id}")
                    return True
                else:
                    logging.error(f"Emir durumu kontrol hatası: {e}")
                    return False

        return False

    def create_order_with_retry(self, side, type, quantity, price=None, stop_price=None, take_profit=None,
                                parent_order_id=None, max_retries=None):
        """Emri birkaç kez deneyerek oluşturur"""
        if max_retries is None:
            max_retries = self.max_retries

        for attempt in range(max_retries):
            try:
                # Her denemede fiyatı biraz ayarla
                if attempt > 0:
                    if price:
                        price = float(price) * (1 + self.price_adjustment * attempt)
                    if stop_price:
                        stop_price = float(stop_price) * (1 + self.price_adjustment * attempt)
                    if take_profit:
                        take_profit = float(take_profit) * (1 + self.price_adjustment * attempt)

                order = self.create_order(
                    side=side,
                    type=type,
                    quantity=quantity,
                    price=price,
                    stop_price=stop_price,
                    take_profit=take_profit,
                    parent_order_id=parent_order_id
                )

                if order:
                    logging.info(f"Emir başarıyla oluşturuldu (Deneme {attempt + 1}/{max_retries})")
                    return order
                else:
                    logging.warning(f"Emir oluşturulamadı (Deneme {attempt + 1}/{max_retries})")
                    time.sleep(self.retry_delay)

            except Exception as e:
                logging.error(f"Emir oluşturma hatası (Deneme {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(self.retry_delay)

        return None

    def verify_position(self, expected_side, expected_quantity, max_retries=3):
        """Pozisyonu doğrular"""
        for attempt in range(max_retries):
            try:
                positions = self.client.futures_position_information(symbol=self.symbol)
                if positions:
                    position = positions[0]
                    position_amount = float(position['positionAmt'])
                    position_size = abs(position_amount)

                    # Pozisyon yönünü kontrol et
                    if expected_side == 'BUY' and position_amount > 0:
                        direction_match = True
                    elif expected_side == 'SELL' and position_amount < 0:
                        direction_match = True
                    else:
                        direction_match = False

                    # Pozisyon miktarını kontrol et (hafif tolerans ile)
                    quantity_match = abs(position_size - expected_quantity) < 0.00001

                    if direction_match and quantity_match:
                        logging.info(f"Pozisyon doğrulandı: {expected_side} @ {position_size}")
                        return True
                    else:
                        logging.warning(f"Pozisyon doğrulanamadı (Deneme {attempt + 1}/{max_retries})")
                        logging.warning(f"Beklenen: {expected_side} @ {expected_quantity}")
                        logging.warning(f"Gerçek: {position_amount}")

                time.sleep(self.retry_delay)

            except Exception as e:
                logging.error(f"Pozisyon doğrulama hatası (Deneme {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(self.retry_delay)

        return False

    def link_orders(self, main_order_id, sl_order_id, tp_order_id):
        """Emirler arasında ilişki kurar"""
        try:
            if main_order_id not in self.order_relationships:
                self.order_relationships[main_order_id] = []

            # SL ve TP emirlerini ana emirle ilişkilendir
            self.order_relationships[main_order_id].extend([sl_order_id, tp_order_id])

            # SL ve TP emirlerini birbirleriyle ilişkilendir
            if sl_order_id not in self.order_relationships:
                self.order_relationships[sl_order_id] = []
            if tp_order_id not in self.order_relationships:
                self.order_relationships[tp_order_id] = []

            self.order_relationships[sl_order_id].append(tp_order_id)
            self.order_relationships[tp_order_id].append(sl_order_id)

            logging.info(f"Emirler ilişkilendirildi: Ana={main_order_id}, SL={sl_order_id}, TP={tp_order_id}")

        except Exception as e:
            logging.error(f"Emir ilişkilendirme hatası: {e}")

    def get_current_price(self):
        """Mevcut fiyatı alır"""
        try:
            ticker = self.client.futures_symbol_ticker(symbol=self.symbol)
            return float(ticker['price'])
        except Exception as e:
            logging.error(f"Mevcut fiyat alma hatası: {e}")
            return None

    def get_position_info(self):
        """Pozisyon bilgilerini alır"""
        try:
            positions = self.client.futures_position_information(symbol=self.symbol)
            if positions:
                position = positions[0]
                position_amount = float(position['positionAmt'])
                if abs(position_amount) > 0:
                    return {
                        'size': abs(position_amount),
                        'side': 'LONG' if position_amount > 0 else 'SHORT',
                        'entry_price': float(position['entryPrice']),
                        'unrealized_pnl': float(position['unRealizedProfit'])
                    }
            return None
        except Exception as e:
            logging.error(f"Pozisyon bilgisi alma hatası: {e}")
            return None

    def get_open_orders(self):
        """Açık emirleri alır"""
        try:
            orders = self.client.futures_get_open_orders(symbol=self.symbol)
            return orders
        except Exception as e:
            logging.error(f"Açık emirleri alma hatası: {e}")
            return []

    def check_tp_sl_orders(self):
        """TP ve SL emirlerinin varlığını kontrol eder"""
        try:
            open_orders = self.get_open_orders()
            has_tp = False
            has_sl = False
            
            for order in open_orders:
                if order['type'] == 'TAKE_PROFIT_MARKET':
                    has_tp = True
                elif order['type'] == 'STOP_MARKET':
                    has_sl = True
            
            return has_tp, has_sl
        except Exception as e:
            logging.error(f"TP/SL kontrol hatası: {e}")
            return False, False

    def create_missing_tp_sl_orders(self, tp_price=None, sl_price=None, tp_percentage=None, sl_percentage=None):
        """Eksik TP ve SL emirlerini oluşturur"""
        try:
            position_info = self.get_position_info()
            if not position_info:
                logging.warning("Pozisyon bulunamadı, TP/SL emirleri oluşturulamıyor")
                return False, False

            current_price = self.get_current_price()
            if not current_price:
                logging.error("Mevcut fiyat alınamadı")
                return False, False

            position_size = position_info['size']
            position_side = position_info['side']
            entry_price = position_info['entry_price']

            # TP ve SL fiyatlarını hesapla
            if not tp_price and tp_percentage:
                if position_side == 'LONG':
                    tp_price = current_price * (1 + tp_percentage / 100)
                else:
                    tp_price = current_price * (1 - tp_percentage / 100)

            if not sl_price and sl_percentage:
                if position_side == 'LONG':
                    sl_price = current_price * (1 - sl_percentage / 100)
                else:
                    sl_price = current_price * (1 + sl_percentage / 100)

            # Mevcut TP/SL emirlerini kontrol et
            has_tp, has_sl = self.check_tp_sl_orders()
            
            tp_created = False
            sl_created = False

            # TP emri oluştur
            if not has_tp and tp_price:
                try:
                    tp_side = 'SELL' if position_side == 'LONG' else 'BUY'
                    tp_order = self.client.futures_create_order(
                        symbol=self.symbol,
                        side=tp_side,
                        type='TAKE_PROFIT_MARKET',
                        quantity=position_size,
                        stopPrice=tp_price,
                        timeInForce='GTC',
                        reduceOnly=True
                    )
                    logging.info(f"TP emri oluşturuldu: ID={tp_order['orderId']}, Fiyat={tp_price}")
                    tp_created = True
                except Exception as e:
                    logging.error(f"TP emri oluşturma hatası: {e}")

            # SL emri oluştur
            if not has_sl and sl_price:
                try:
                    sl_side = 'SELL' if position_side == 'LONG' else 'BUY'
                    sl_order = self.client.futures_create_order(
                        symbol=self.symbol,
                        side=sl_side,
                        type='STOP_MARKET',
                        quantity=position_size,
                        stopPrice=sl_price,
                        timeInForce='GTC',
                        reduceOnly=True
                    )
                    logging.info(f"SL emri oluşturuldu: ID={sl_order['orderId']}, Fiyat={sl_price}")
                    sl_created = True
                except Exception as e:
                    logging.error(f"SL emri oluşturma hatası: {e}")

            return tp_created, sl_created

        except Exception as e:
            logging.error(f"TP/SL emirleri oluşturma hatası: {e}")
            return False, False

    def monitor_and_ensure_tp_sl(self, tp_price=None, sl_price=None, tp_percentage=None, sl_percentage=None, delay=60):
        """Pozisyon açıldıktan sonra belirtilen süre bekleyip TP/SL emirlerini kontrol eder ve eksikleri oluşturur"""
        try:
            logging.info(f"TP/SL kontrol işlemi {delay} saniye sonra başlayacak...")
            time.sleep(delay)
            
            position_info = self.get_position_info()
            if not position_info:
                logging.warning("Pozisyon bulunamadı, TP/SL kontrol işlemi iptal ediliyor")
                return

            logging.info("TP/SL emirleri kontrol ediliyor...")
            has_tp, has_sl = self.check_tp_sl_orders()
            
            if has_tp and has_sl:
                logging.info("TP ve SL emirleri mevcut, ek işlem gerekmiyor")
                return
            
            if not has_tp:
                logging.warning("TP emri bulunamadı, yeni TP emri oluşturuluyor...")
            if not has_sl:
                logging.warning("SL emri bulunamadı, yeni SL emri oluşturuluyor...")
                
            tp_created, sl_created = self.create_missing_tp_sl_orders(
                tp_price=tp_price,
                sl_price=sl_price,
                tp_percentage=tp_percentage,
                sl_percentage=sl_percentage
            )
            
            if tp_created:
                logging.info("Eksik TP emri başarıyla oluşturuldu")
            if sl_created:
                logging.info("Eksik SL emri başarıyla oluşturuldu")
                
        except Exception as e:
            logging.error(f"TP/SL kontrol ve oluşturma hatası: {e}")
