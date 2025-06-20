class Config:
    def __init__(self):
        # PSAR parametreleri
        self.psar_start = 2  # PSAR başlangıç değeri
        self.psar_increment = 2  # PSAR artış değeri
        self.psar_maximum = 2  # PSAR maksimum değeri

        # ATR Zone parametreleri
        self.zone_length = 10  # ATR Zone uzunluğu
        self.zone_multiplier = 3.0  # ATR Zone çarpanı

        # Donchian Channel parametreleri
        self.donchian_length = 20  # Donchian Channel uzunluğu

        # EMA parametreleri
        self.ema_lower_period = 9  # Düşük periyot EMA
        self.ema_medium_period = 27  # Orta periyot EMA
        self.hma_long_period = 200  # Uzun periyot HMA

        # Trade parametreleri
        self.take_profit_percent = 0.005  # %0.5 kar
        self.stop_loss_percent = 0.02  # %2.0 zarar
        self.min_time_between_trades = 60  # Minimum işlemler arası süre (dakika)
        self.waiting_period = 2 * 60  # 2 dakika (saniye cinsinden)
        
        # Sinyal onay parametreleri
        self.signal_confirmation_delay = 30  # Sinyal onay bekleme süresi (saniye)
        
        # Market condition filtreleri
        self.min_atr = 10  # Minimum ATR değeri
        self.max_atr = 50  # Maksimum ATR değeri
        self.rsi_length = 14  # RSI periyodu
        self.atr_length = 14  # ATR periyodu
        self.ema_trend_short = 50  # Trend EMA kısa periyot
        self.ema_trend_long = 200  # Trend EMA uzun periyot
        
        # Score filter parametreleri
        self.bad_signal_tolerance = 5  # Kötü sinyal toleransı
        self.max_bad_signals = 20  # Maksimum kötü sinyal kaydı 