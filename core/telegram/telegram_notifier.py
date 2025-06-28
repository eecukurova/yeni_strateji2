import requests
import logging
import csv
import os
from datetime import datetime
from .config import Config

class TelegramNotifier:
    def __init__(self, symbol=None):
        self.config = Config()
        self.bot_token = self.config.bot_token
        self.chat_id = str(self.config.chat_id)  # Chat ID string olmalı
        self.base_url = self.config.base_url
        self.environment = self.config.environment
        self.symbol = symbol  # Trading symbol (e.g., 'BNB', 'ETH')

    def _format_message_with_env(self, message):
        """Mesaja environment bilgisini ekler"""
        env_emoji = "🧪" if self.environment == "TEST" else "🚀" if self.environment == "PROD" else "🔧"
        env_prefix = f"{env_emoji} <b>[{self.environment}]</b>\n\n"
        return env_prefix + message

    def _log_to_csv(self, message, status, error_msg=None):
        """Telegram mesajını CSV dosyasına loglar"""
        try:
            # Logs dizinini oluştur
            logs_dir = os.path.join(os.getcwd(), 'logs')
            os.makedirs(logs_dir, exist_ok=True)
            
            # CSV dosya adını belirle
            if self.symbol:
                csv_filename = os.path.join(logs_dir, f'telegram_{self.symbol.lower()}.csv')
            else:
                csv_filename = os.path.join(logs_dir, 'telegram_general.csv')
            
            # CSV verisi
            csv_data = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Tarih/Saat
                self.symbol or 'GENERAL',                       # Sembol
                self.environment,                              # Environment
                message[:100] + '...' if len(message) > 100 else message,  # Mesaj (kısaltılmış)
                status,                                        # Durum (SUCCESS/ERROR)
                error_msg or ''                                # Hata mesajı
            ]
            
            # Dosya yoksa header ekle
            file_exists = os.path.exists(csv_filename)
            
            with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Header yazma (sadece dosya yoksa)
                if not file_exists:
                    header = ['Tarih/Saat', 'Sembol', 'Environment', 'Mesaj', 'Durum', 'Hata Mesajı']
                    writer.writerow(header)
                
                # Veri yazma
                writer.writerow(csv_data)
            
            logging.debug(f"Telegram mesajı CSV'ye kaydedildi: {csv_filename}")
            
        except Exception as e:
            logging.error(f"Telegram CSV log kaydetme hatası: {e}")

    def send_notification(self, message):
        try:
            # Mesaja environment bilgisini ekle
            formatted_message = self._format_message_with_env(message)
            
            # Mesajı HTML formatında gönder
            payload = {
                'chat_id': self.chat_id,
                'text': formatted_message,
                'parse_mode': 'HTML'  # HTML formatını kullan
            }

            response = requests.post(
                self.base_url,
                data=payload,
                timeout=10
            )
            response.raise_for_status()
            if response.status_code == 200:
                logging.info(f"Telegram bildirimi başarıyla gönderildi (ENV: {self.environment})")
                # Başarılı mesajı CSV'ye logla
                self._log_to_csv(message, 'SUCCESS')
                return True
            else:
                error_msg = f"Telegram API Hatası: {response.status_code} - {response.text}"
                logging.error(error_msg)
                # Hatalı mesajı CSV'ye logla
                self._log_to_csv(message, 'ERROR', error_msg)
                return False

        except requests.exceptions.RequestException as e:
            error_msg = f"Telegram bildirim hatası: {str(e)}"
            logging.error(error_msg)
            # Hatalı mesajı CSV'ye logla
            self._log_to_csv(message, 'ERROR', error_msg)
            return False
        except Exception as e:
            error_msg = f"Beklenmeyen Telegram hatası: {str(e)}"
            logging.error(error_msg)
            # Hatalı mesajı CSV'ye logla
            self._log_to_csv(message, 'ERROR', error_msg)
            return False

