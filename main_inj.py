import logging
import os
from strategies import psar_atr_strategy
from core.logging_config import LoggingConfig

class MainINJ:
    pass

# Kullanım örneği
if __name__ == "__main__":
    logger = None
    try:
        # Loglama ayarları - Artık INFO seviyesinde loglar da yazılacak
        logging_config = LoggingConfig()
        logger = logging_config.setup_logging("main_inj")
        
        # Environment variables'dan leverage ve trade_amount oku
        leverage = int(os.getenv('LEVERAGE', 10))
        trade_amount = int(os.getenv('TRADE_AMOUNT', 100))
        
        logger.info("INJ Trading Bot başlatılıyor...")
        logger.info(f"Sembol: INJUSDT, Timeframe: 15m, Leverage: {leverage}, Trade Amount: {trade_amount}")

        bot = psar_atr_strategy.Bot(symbol='INJUSDT', timeframe='15m', leverage=leverage, trade_amount=trade_amount)
        logger.info("Bot başarıyla oluşturuldu")
        
        logger.info("Trading başlatılıyor...")
        bot.start_trading()

    except Exception as e:
        if logger:
            logger.error(f"Bot çalıştırma hatası: {e}")
            logger.exception("Detaylı hata bilgisi:")
        else:
            print(f"HATA - Logger oluşturulamadı: {e}")
    except KeyboardInterrupt:
        if logger:
            logger.info("Bot manuel olarak durduruldu (Ctrl+C)")
        else:
            print("Bot manuel olarak durduruldu")
