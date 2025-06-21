import logging
from strategies import psar_atr_strategy
from core.logging_config import LoggingConfig

class MainETH:
    pass

# Kullanım örneği
if __name__ == "__main__":
    logger = None
    try:
        # Loglama ayarları - Artık INFO seviyesinde loglar da yazılacak
        logging_config = LoggingConfig()
        logger = logging_config.setup_logging("main_eth")
        
        logger.info("ETH Trading Bot başlatılıyor...")
        logger.info("Sembol: ETHUSDT, Timeframe: 15m, Leverage: 20, Trade Amount: 2000")

        bot = psar_atr_strategy.Bot(symbol='ETHUSDT', timeframe='15m', leverage=15, trade_amount=3000)
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
