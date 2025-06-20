import logging
from strategies.atr_strategy import Bot
from core.logging_config import LoggingConfig

class MainAS:
    pass

# Kullanım örneği
if __name__ == "__main__":
    logger = None
    try:
        # Loglama ayarları - Artık INFO seviyesinde loglar da yazılacak
        logging_config = LoggingConfig()
        logger = logging_config.setup_logging("main_as")
        
        logger.info("AS (ATR Strategy) Trading Bot başlatılıyor...")
        logger.info("Sembol: ETHUSDT, Timeframe: 15m, Leverage: 10, Trade Amount: 100")
        
        # Botu başlat
        bot = Bot(symbol='ETHUSDT', timeframe='15m', leverage=10, trade_amount=100)
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