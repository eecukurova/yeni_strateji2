#!/bin/bash

# Dashboard Başlatma Scripti
# Bu script, trading bot dashboard'unu başlatır

echo "🚀 Trading Bot Dashboard Başlatılıyor..."

# Mevcut dizini kontrol et
if [ ! -f "dashboard.py" ]; then
    echo "❌ Hata: dashboard.py dosyası bulunamadı!"
    echo "Bu script'i dashboard.py dosyasının bulunduğu dizinde çalıştırın."
    exit 1
fi

# Logs dizinini oluştur
echo "📁 Logs dizini oluşturuluyor..."
mkdir -p logs

# Virtual environment kontrolü
if [ ! -d "venv" ]; then
    echo "🐍 Virtual environment oluşturuluyor..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Hata: Virtual environment oluşturulamadı!"
        exit 1
    fi
fi

# Virtual environment'ı aktifleştir
echo "🔧 Virtual environment aktifleştiriliyor..."
source venv/bin/activate

# Gerekli paketleri kontrol et ve yükle
echo "📦 Gerekli paketler kontrol ediliyor..."
if [ -f "dashboard_requirements.txt" ]; then
    echo "📦 Paketler yükleniyor..."
    pip install -r dashboard_requirements.txt
elif [ -f "requirements.txt" ]; then
    echo "📦 Paketler yükleniyor..."
    pip install -r requirements.txt
else
    echo "⚠️  requirements.txt dosyası bulunamadı, temel paketler yükleniyor..."
    pip install flask flask-login pandas psutil
fi

# Mevcut dashboard process'ini kontrol et ve durdur
echo "🔍 Mevcut dashboard process'i kontrol ediliyor..."
DASHBOARD_PID=$(pgrep -f "python3.*dashboard.py")
if [ ! -z "$DASHBOARD_PID" ]; then
    echo "🛑 Mevcut dashboard process'i durduruluyor (PID: $DASHBOARD_PID)..."
    kill $DASHBOARD_PID
    sleep 2
fi

# Dashboard'ı başlat
echo "🚀 Dashboard başlatılıyor..."
nohup python3 dashboard.py > logs/dashboard.log 2>&1 &

# Process ID'yi al
DASHBOARD_PID=$!
echo "✅ Dashboard başlatıldı! PID: $DASHBOARD_PID"

# Kısa bir bekleme
sleep 3

# Process'in çalışıp çalışmadığını kontrol et
if ps -p $DASHBOARD_PID > /dev/null; then
    echo "🎉 Dashboard başarıyla çalışıyor!"
    echo "📊 Dashboard URL: http://localhost:5000"
    echo "📝 Log dosyası: logs/dashboard.log"
    echo "🆔 Process ID: $DASHBOARD_PID"
    echo ""
    echo "Dashboard'ı durdurmak için: kill $DASHBOARD_PID"
    echo "Log'ları izlemek için: tail -f logs/dashboard.log"
else
    echo "❌ Hata: Dashboard başlatılamadı!"
    echo "Log dosyasını kontrol edin: logs/dashboard.log"
    exit 1
fi

# Virtual environment'ı deaktifleştir
deactivate

echo ""
echo "✅ Dashboard başlatma işlemi tamamlandı!" 