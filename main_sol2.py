import logging
from strategies import eralp_strateji2
from core.logging_config import LoggingConfig


class MainSOL2:
    pass


    # Kullanım örneği
    if __name__ == "__main__":
        logger = None
        try:
            # Loglama ayarları - Artık INFO seviyesinde loglar da yazılacak
            logging_config = LoggingConfig()
            logger = logging_config.setup_logging("main_sol2")
            
            logger.info("SOL Trading Bot (Eralp Strategy 2) başlatılıyor...")
            logger.info("Sembol: SOLUSDT, Timeframe: 15m, Leverage: 20, Trade Amount: 2000")

            bot = eralp_strateji2.Bot(symbol='SOLUSDT', timeframe='15m', leverage=10, trade_amount=200)
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
