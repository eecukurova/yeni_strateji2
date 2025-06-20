import logging
from strategies import psar_atr_strategy
from core.logging_config import LoggingConfig

class MainTON:

    # Kullanım örneği
    if __name__ == "__main__":
        try:
            # Loglama ayarları - Sadece hata logları için
            logging_config = LoggingConfig()
            logger = logging_config.setup_logging("main_ton")
            
            bot = psar_atr_strategy.Bot(symbol='TONUSDT', timeframe='15m', leverage=10, trade_amount=1000)
            bot.start_trading()

        except Exception as e:
            logger.error(f"Bot çalıştırma hatası: {e}")