import csv
import os
from datetime import datetime
import logging

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
                        'timestamp', 'strategy', 'symbol', 'bar_index', 'signal_type',
                        'close', 'high', 'low', 'pSAR_UpValue', 'pSAR_DownValue',
                        'zoneATR', 'upZone', 'downZone', 'zoneDecider',
                        'greenZone', 'redZone', 'middleDonchian', 'upperDonchian',
                        'lowerDonchian', 'emaLower', 'emaMedium', 'hmaLong'
                    ]
                    writer.writerow(header)
                    
        except Exception as e:
            logging.error(f"Signal control CSV dosyası oluşturma hatası: {e}")
    
    def log_signal(self, strategy_name, symbol, signal_data):
        """
        Sinyal verilerini CSV'ye kaydet
        
        Args:
            strategy_name (str): Strateji adı
            symbol (str): Trading sembolü
            signal_data (dict): Sinyal verileri
        """
        try:
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
                timestamp, strategy_name, symbol, bar_index, signal_type,
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
                f"{hma_long:.4f}" if hma_long else ""
            ]
            
            # CSV'ye yaz
            with open(self.csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(csv_data)
            
            logging.info(f"Sinyal kontrol CSV'ye kaydedildi: {strategy_name} - {symbol} - {signal_type}")
            
        except Exception as e:
            logging.error(f"Sinyal kontrol CSV kaydetme hatası: {e}")

# Global instance
signal_logger = SignalLogger() 