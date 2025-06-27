import requests
import logging
from .config import Config

class TelegramNotifier:
    def __init__(self):
        self.config = Config()
        self.bot_token = self.config.bot_token
        self.chat_id = str(self.config.chat_id)  # Chat ID string olmalı
        self.base_url = self.config.base_url
        self.environment = self.config.environment

    def _format_message_with_env(self, message):
        """Mesaja environment bilgisini ekler"""
        env_emoji = "🧪" if self.environment == "TEST" else "🚀" if self.environment == "PROD" else "🔧"
        env_prefix = f"{env_emoji} <b>[{self.environment}]</b>\n\n"
        return env_prefix + message

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
                return True
            else:
                logging.error(f"Telegram API Hatası: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logging.error(f"Telegram bildirim hatası: {str(e)}")
            return False
        except Exception as e:
            logging.error(f"Beklenmeyen Telegram hatası: {str(e)}")
            return False

