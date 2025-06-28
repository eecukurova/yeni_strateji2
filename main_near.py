import logging
import os
import importlib
from core.logging_config import LoggingConfig

class MainNEAR:
    pass

# Kullanım örneği
if __name__ == "__main__":
    logger = None
    try:
        # Loglama ayarları - Artık INFO seviyesinde loglar da yazılacak
        logging_config = LoggingConfig()
        logger = logging_config.setup_logging("main_near")
        
        # Environment variables'dan leverage, trade_amount ve strategy oku
        leverage = int(os.getenv('LEVERAGE', 10))
        trade_amount = int(os.getenv('TRADE_AMOUNT', 100))
        strategy = os.getenv('STRATEGY', 'psar_atr_strategy')
        
        logger.info("NEAR Trading Bot başlatılıyor...")
        logger.info(f"Sembol: NEARUSDT, Timeframe: 15m, Leverage: {leverage}, Trade Amount: {trade_amount}, Strategy: {strategy}")

        # Strategy'yi dinamik olarak import et
        strategy_module = importlib.import_module(f'strategies.{strategy}')
        bot = strategy_module.Bot(symbol='NEARUSDT', timeframe='15m', leverage=leverage, trade_amount=trade_amount)
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
