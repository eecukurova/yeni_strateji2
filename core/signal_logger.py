import csv
import os
from datetime import datetime
import logging
import uuid

class SignalLogger:
    """Tüm stratejiler için ortak sinyal kontrol CSV logger'ı"""
    
    def __init__(self):
        self.csv_filename = 'logs/sinyal_kontrol.csv'
        self._ensure_csv_file()
    
    def _ensure_csv_file(self):
        """CSV dosyasını oluştur ve header'ı ekle"""
        try:
            # logs klasörü yoksa oluştur
            os.makedirs('logs', exist_ok=True)
            
            # Dosya yoksa header ile oluştur
            if not os.path.exists(self.csv_filename):
                with open(self.csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    header = [
                        'signal_id', 'timestamp', 'strategy', 'symbol', 'bar_index', 'signal_type',
                        'close', 'high', 'low', 'pSAR_UpValue', 'pSAR_DownValue',
                        'zoneATR', 'upZone', 'downZone', 'zoneDecider',
                        'greenZone', 'redZone', 'middleDonchian', 'upperDonchian',
                        'lowerDonchian', 'emaLower', 'emaMedium', 'hmaLong',
                        'position_opened', 'entry_price', 'exit_price', 'pnl_usdt', 'pnl_percent', 'position_closed_at'
                    ]
                    writer.writerow(header)
            else:
                # Mevcut dosyada yeni alanlar var mı kontrol et
                self._check_and_update_headers()
                    
        except Exception as e:
            logging.error(f"Signal control CSV dosyası oluşturma hatası: {e}")
    
    def _check_and_update_headers(self):
        """Mevcut CSV dosyasının header'ını kontrol et ve gerekirse güncelle"""
        try:
            # Mevcut header'ı oku
            with open(self.csv_filename, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                existing_header = next(reader, [])
            
            # Yeni header
            new_header = [
                'signal_id', 'timestamp', 'strategy', 'symbol', 'bar_index', 'signal_type',
                'close', 'high', 'low', 'pSAR_UpValue', 'pSAR_DownValue',
                'zoneATR', 'upZone', 'downZone', 'zoneDecider',
                'greenZone', 'redZone', 'middleDonchian', 'upperDonchian',
                'lowerDonchian', 'emaLower', 'emaMedium', 'hmaLong',
                'position_opened', 'entry_price', 'exit_price', 'pnl_usdt', 'pnl_percent', 'position_closed_at'
            ]
            
            # Header farklıysa dosyayı güncelle
            if existing_header != new_header:
                # Mevcut verileri oku
                with open(self.csv_filename, 'r', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    next(reader)  # Header'ı atla
                    existing_data = list(reader)
                
                # Dosyayı yeni header ile yeniden yaz
                with open(self.csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(new_header)
                    
                    # Mevcut verileri yeni formata dönüştür
                    for row in existing_data:
                        # Eksik alanları boş string ile doldur
                        while len(row) < len(new_header):
                            row.append('')
                        
                        # signal_id yoksa oluştur
                        if not row[0] or row[0] == 'timestamp':  # Eski format
                            row.insert(0, str(uuid.uuid4())[:8])  # signal_id ekle
                        
                        writer.writerow(row)
                
                logging.info("Signal control CSV header güncellendi")
                
        except Exception as e:
            logging.error(f"CSV header güncelleme hatası: {e}")
    
    def log_signal(self, strategy_name, symbol, signal_data):
        """
        Sinyal verilerini CSV'ye kaydet
        
        Args:
            strategy_name (str): Strateji adı
            symbol (str): Trading sembolü
            signal_data (dict): Sinyal verileri
            
        Returns:
            str: Signal ID
        """
        try:
            # Unique signal ID oluştur
            signal_id = str(uuid.uuid4())[:8]
            
            # Timestamp
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Bar index (eğer yoksa current timestamp kullan)
            bar_index = signal_data.get('bar_index', timestamp)
            
            # Signal type (buy/sell)
            signal_type = 'BUY' if signal_data.get('buy', False) else 'SELL'
            
            # Fiyat bilgileri
            close = signal_data.get('Close', signal_data.get('close', 0))
            high = signal_data.get('High', signal_data.get('high', 0))
            low = signal_data.get('Low', signal_data.get('low', 0))
            
            # PSAR değerleri
            psar_up = signal_data.get('pSAR_UpValue', signal_data.get('psar', 0))
            psar_down = signal_data.get('pSAR_DownValue', signal_data.get('psar', 0))
            
            # ATR Zone bilgileri
            zone_atr = signal_data.get('zoneATR', signal_data.get('atr', 0))
            up_zone = signal_data.get('upZone', signal_data.get('atr_upper', signal_data.get('upper_zone', 0)))
            down_zone = signal_data.get('downZone', signal_data.get('atr_lower', signal_data.get('lower_zone', 0)))
            zone_decider = signal_data.get('zoneDecider', signal_data.get('zone_decider', 0))
            
            # Zone değişimleri
            green_zone = signal_data.get('greenZone', signal_data.get('buy_signal', False))
            red_zone = signal_data.get('redZone', signal_data.get('sell_signal', False))
            
            # Donchian Channel
            middle_donchian = signal_data.get('middleDonchian', signal_data.get('middle_donchian', 0))
            upper_donchian = signal_data.get('upperDonchian', signal_data.get('upper_donchian', 0))
            lower_donchian = signal_data.get('lowerDonchian', signal_data.get('lower_donchian', 0))
            
            # EMA/HMA değerleri
            ema_lower = signal_data.get('emaLower', signal_data.get('ema_lower', signal_data.get('ema_9', 0)))
            ema_medium = signal_data.get('emaMedium', signal_data.get('ema_medium', signal_data.get('ema_21', 0)))
            hma_long = signal_data.get('hmaLong', signal_data.get('hma_long', 0))
            
            # CSV verisi hazırla
            csv_data = [
                signal_id, timestamp, strategy_name, symbol, bar_index, signal_type,
                f"{close:.4f}" if close else "",
                f"{high:.4f}" if high else "",
                f"{low:.4f}" if low else "",
                f"{psar_up:.4f}" if psar_up else "",
                f"{psar_down:.4f}" if psar_down else "",
                f"{zone_atr:.6f}" if zone_atr else "",
                f"{up_zone:.4f}" if up_zone else "",
                f"{down_zone:.4f}" if down_zone else "",
                str(zone_decider) if zone_decider != 0 else "",
                str(green_zone).lower() if isinstance(green_zone, bool) else "",
                str(red_zone).lower() if isinstance(red_zone, bool) else "",
                f"{middle_donchian:.4f}" if middle_donchian else "",
                f"{upper_donchian:.4f}" if upper_donchian else "",
                f"{lower_donchian:.4f}" if lower_donchian else "",
                f"{ema_lower:.4f}" if ema_lower else "",
                f"{ema_medium:.4f}" if ema_medium else "",
                f"{hma_long:.4f}" if hma_long else "",
                "", "", "", "", "", ""  # Pozisyon bilgileri boş
            ]
            
            # CSV'ye yaz
            with open(self.csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(csv_data)
            
            logging.info(f"Sinyal kontrol CSV'ye kaydedildi: {strategy_name} - {symbol} - {signal_type} - ID: {signal_id}")
            
            return signal_id
            
        except Exception as e:
            logging.error(f"Sinyal kontrol CSV kaydetme hatası: {e}")
            return None
    
    def update_position_opened(self, signal_id, entry_price):
        """Pozisyon açıldığında sinyal kaydını güncelle"""
        try:
            self._update_signal_record(signal_id, {
                'position_opened': 'true',
                'entry_price': f"{entry_price:.4f}" if entry_price else ""
            })
            logging.info(f"Signal {signal_id} pozisyon açılış bilgisi güncellendi: {entry_price}")
        except Exception as e:
            logging.error(f"Pozisyon açılış güncelleme hatası: {e}")
    
    def update_position_closed(self, signal_id, exit_price, pnl_usdt, pnl_percent):
        """Pozisyon kapandığında kar/zarar bilgilerini güncelle"""
        try:
            close_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self._update_signal_record(signal_id, {
                'exit_price': f"{exit_price:.4f}" if exit_price else "",
                'pnl_usdt': f"{pnl_usdt:.4f}" if pnl_usdt else "",
                'pnl_percent': f"{pnl_percent:.2f}%" if pnl_percent else "",
                'position_closed_at': close_time
            })
            logging.info(f"Signal {signal_id} pozisyon kapanış bilgisi güncellendi: PnL USDT: {pnl_usdt}, PnL %: {pnl_percent}")
        except Exception as e:
            logging.error(f"Pozisyon kapanış güncelleme hatası: {e}")
    
    def _update_signal_record(self, signal_id, update_data):
        """Belirli bir signal ID'ye sahip kaydı güncelle"""
        try:
            # Mevcut verileri oku
            rows = []
            header = []
            
            with open(self.csv_filename, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                header = next(reader)
                rows = list(reader)
            
            # Signal ID'yi bul ve güncelle
            updated = False
            for i, row in enumerate(rows):
                if len(row) > 0 and row[0] == signal_id:
                    # Güncelleme verilerini uygula
                    for field, value in update_data.items():
                        if field in header:
                            field_index = header.index(field)
                            if field_index < len(row):
                                row[field_index] = value
                            else:
                                # Row eksik kolonlara sahipse, uzat
                                while len(row) <= field_index:
                                    row.append('')
                                row[field_index] = value
                    updated = True
                    break
            
            if updated:
                # Dosyayı güncelle
                with open(self.csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(header)
                    writer.writerows(rows)
            else:
                logging.warning(f"Signal ID {signal_id} bulunamadı")
                
        except Exception as e:
            logging.error(f"Signal record güncelleme hatası: {e}")

# Global instance
signal_logger = SignalLogger() 