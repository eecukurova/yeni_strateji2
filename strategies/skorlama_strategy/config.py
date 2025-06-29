"""
Skorlama Strategy Configuration

Bu dosya, Skorlama stratejisinin tüm parametrelerini ve ayarlarını içerir.
Pine Script'teki input değerlerine karşılık gelen Python parametreleri.
"""

class SkorlamaConfig:
    """Skorlama Stratejisi Konfigürasyonu"""
    
    # === PSAR AYARLARI ===
    PSAR_START = 2          # PSAR başlangıç değeri (0.02)
    PSAR_END = 2            # PSAR bitiş değeri (0.20)
    PSAR_MULTIPLIER = 2     # PSAR çarpanı (0.02)
    
    # === ATR ZONE AYARLARI ===
    ATR_ZONE_LENGTH = 10    # ATR Zone uzunluğu
    ATR_ZONE_MULTIPLIER = 3.0  # ATR Zone çarpanı
    
    # === DONCHIAN CHANNEL AYARLARI ===
    DONCHIAN_LENGTH = 20    # Donchian Channel uzunluğu
    
    # === MOVING AVERAGE AYARLARI ===
    EMA_FAST = 50           # Hızlı EMA
    EMA_SLOW = 200          # Yavaş EMA
    
    # === ADX AYARLARI ===
    ADX_LENGTH = 14         # ADX hesaplama uzunluğu
    
    # === RSI AYARLARI ===
    RSI_LENGTH = 14         # RSI hesaplama uzunluğu
    
    # === VOLUME AYARLARI ===
    VOLUME_MA_LENGTH = 20   # Volume MA uzunluğu
    
    # === SKORLAMA AYARLARI ===
    MIN_SCORE = 71          # Minimum skor (sinyal için)
    ADX_MIN = 20            # Minimum ADX değeri
    ADX_STRONG = 25         # Güçlü trend ADX değeri
    
    # === ATR VOLATILITE AYARLARI ===
    ATR_LENGTH = 20         # ATR hesaplama uzunluğu
    ATR_MA_LENGTH = 20      # ATR MA uzunluğu
    
    # === RSI AYARLARI ===
    RSI_MIN = 55            # RSI minimum değeri (skor için)
    
    # === TRADE AYARLARI ===
    TAKE_PROFIT_PERCENT = 0.005  # %0.5 take profit
    STOP_LOSS_PERCENT = 0.02     # %2 stop loss
    
    # === SKORLAMA PONDERASYONU ===
    SCORE_ADX_WEIGHT = 30   # ADX > 25 için skor
    SCORE_TREND_WEIGHT = 20 # Trend durumu için skor
    SCORE_RSI_WEIGHT = 20   # RSI > 55 için skor
    SCORE_VOLUME_WEIGHT = 30 # Volume > MA için skor 