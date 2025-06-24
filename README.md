# CoinMatik - Kripto Para Trading Bot

Bu proje, çeşitli kripto para çiftleri için otomatik trading stratejileri uygulayan bir Python tabanlı trading bot sistemidir.

## 🚀 Özellikler

- **Çoklu Coin Desteği**: ARB, AS, BNB, BTC, EIGEN, ENA, ETH, FET, INJ, JUP, NEAR, SOL, TON gibi popüler kripto paralar
- **Farklı Trading Stratejileri**: ATR, PSAR-ATR, ve özel stratejiler
- **Binance Entegrasyonu**: Binance API ile gerçek zamanlı trading
- **Telegram Bildirimleri**: Trading işlemleri için anlık bildirimler
- **Logging Sistemi**: Detaylı log kayıtları

## 📁 Proje Yapısı

```
coin_matik_yedek_2406/
├── adapters/           # Exchange adaptörleri
│   └── binance/       # Binance API entegrasyonu
├── core/              # Temel bileşenler
│   ├── models/        # Veri modelleri
│   └── telegram/      # Telegram bildirim sistemi
├── strategies/        # Trading stratejileri
│   ├── atr_strategy/
│   ├── eralp_strateji2/
│   └── psar_atr_strategy/
├── logs/              # Log dosyaları
└── main_*.py          # Her coin için ana script
```

## 🛠️ Kurulum

1. Repository'yi klonlayın:
```bash
git clone https://github.com/ahmeteralp/coinmatik.git
cd coinmatik
```

2. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

3. Konfigürasyon dosyalarını ayarlayın:
   - `adapters/binance/config.py` - Binance API anahtarları
   - `core/telegram/config.py` - Telegram bot token'ı

## 📊 Kullanım

Her coin için ayrı bir main script bulunmaktadır:

```bash
# Örnek kullanım
python main_btc.py    # Bitcoin trading
python main_eth.py    # Ethereum trading
python main_bnb.py    # BNB trading
```

## 🔧 Konfigürasyon

### Binance API Ayarları
`adapters/binance/config.py` dosyasında API anahtarlarınızı ayarlayın:

```python
API_KEY = "your_api_key"
API_SECRET = "your_api_secret"
```

### Telegram Bildirimleri
`core/telegram/config.py` dosyasında bot token'ınızı ayarlayın:

```python
BOT_TOKEN = "your_bot_token"
CHAT_ID = "your_chat_id"
```

## 📈 Trading Stratejileri

### ATR Stratejisi
- Average True Range tabanlı volatilite analizi
- Dinamik stop-loss ve take-profit seviyeleri

### PSAR-ATR Stratejisi
- Parabolic SAR ve ATR kombinasyonu
- Trend takibi ve momentum analizi

### Eralp Strateji 2
- Özel geliştirilmiş strateji
- Çoklu indikatör analizi

## ⚠️ Uyarılar

- Bu bot sadece eğitim amaçlıdır
- Gerçek para ile trading yapmadan önce test edin
- Kripto para trading yüksek risk içerir
- API anahtarlarınızı güvenli tutun

## 📝 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add amazing feature'`)
4. Branch'inizi push edin (`git push origin feature/amazing-feature`)
5. Pull Request oluşturun

## 📞 İletişim

- GitHub: [@ahmeteralp](https://github.com/ahmeteralp)
- Repository: [https://github.com/ahmeteralp/coinmatik.git](https://github.com/ahmeteralp/coinmatik.git)
