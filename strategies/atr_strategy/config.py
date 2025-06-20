class Config:
    def __init__(self):
        # TradingView parametreleri
        self.key_value = 1  # ATR hassasiyeti
        self.atr_period = 10  # ATR periyodu
        self.super_trend_factor = 1.5  # Super Trend çarpanı
        self.min_time_between_trades = 60  # İşlemler arası minimum süre (dakika)

        # Trade parametreleri
        self.take_profit_percent = 0.005  # %0.5 kar
        self.stop_loss_percent = 0.02  # %2 zarar
        self.waiting_period = 2 * 60  # 2 dakika (saniye cinsinden)
        self.leverage = 10  # Varsayılan kaldıraç oranı
        
        # Sinyal onay parametreleri
        self.signal_confirmation_delay = 30  # Sinyal onay bekleme süresi (saniye)