import logging
from strategies import eralp_strateji2
from core.logging_config import LoggingConfig


class MainEIGEN2:
    pass


    # Kullanım örneği
    if __name__ == "__main__":
        logger = None
        try:
            # Loglama ayarları - Artık INFO seviyesinde loglar da yazılacak
            logging_config = LoggingConfig()
            logger = logging_config.setup_logging("main_eigen2")
            
            logger.info("EIGEN Trading Bot (Eralp Strategy 2) başlatılıyor...")
            logger.info("Sembol: EIGENUSDT, Timeframe: 15m, Leverage: 10, Trade Amount: 200")

            bot = eralp_strateji2.Bot(symbol='EIGENUSDT', timeframe='15m', leverage=10, trade_amount=200)
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
