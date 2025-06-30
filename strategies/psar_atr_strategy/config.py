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
        self.stop_loss_percent = 0.015  # %1.5 zarar
        self.min_time_between_trades = 60  # Minimum işlemler arası süre (dakika)
        self.waiting_period = 2 * 60  # 2 dakika (saniye cinsinden)
        
        # Sinyal onay parametreleri
        self.signal_confirmation_delay = 60  # Sinyal onay bekleme süresi (saniye) 