#!/bin/bash

# Dashboard Durdurma Scripti
# Bu script, çalışan dashboard process'ini durdurur

echo "🛑 Trading Bot Dashboard Durduruluyor..."

# Dashboard process'ini bul
DASHBOARD_PID=$(pgrep -f "python3.*dashboard.py")

if [ -z "$DASHBOARD_PID" ]; then
    echo "ℹ️  Çalışan dashboard process'i bulunamadı."
    exit 0
fi

echo "🔍 Dashboard process'i bulundu: PID $DASHBOARD_PID"

# Process'i durdur
echo "🛑 Process durduruluyor..."
kill $DASHBOARD_PID

# Kısa bir bekleme
sleep 2

# Process'in durup durmadığını kontrol et
if ps -p $DASHBOARD_PID > /dev/null 2>&1; then
    echo "⚠️  Process hala çalışıyor, zorla durduruluyor..."
    kill -9 $DASHBOARD_PID
    sleep 1
fi

# Son kontrol
if ps -p $DASHBOARD_PID > /dev/null 2>&1; then
    echo "❌ Hata: Dashboard durdurulamadı!"
    exit 1
else
    echo "✅ Dashboard başarıyla durduruldu!"
fi 