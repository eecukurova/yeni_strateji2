#!/usr/bin/env python3
"""
Telegram Environment Test Script
Bu script, telegram mesajlarına environment bilgisinin eklendiğini test eder.
"""

import os
from core.telegram.telegram_notifier import TelegramNotifier

def test_telegram_with_env():
    """Farklı environment'larda telegram mesajlarını test eder"""
    
    # Test 1: ENV=TEST (default)
    print("=== Test 1: ENV=TEST (default) ===")
    telegram = TelegramNotifier()
    telegram.send_notification("🧪 Bu bir test mesajıdır (TEST environment)")
    
    # Test 2: ENV=PROD
    print("\n=== Test 2: ENV=PROD ===")
    os.environ['ENV'] = 'PROD'
    telegram_prod = TelegramNotifier()
    telegram_prod.send_notification("🚀 Bu bir production mesajıdır (PROD environment)")
    
    # Test 3: ENV=DEV
    print("\n=== Test 3: ENV=DEV ===")
    os.environ['ENV'] = 'DEV'
    telegram_dev = TelegramNotifier()
    telegram_dev.send_notification("🔧 Bu bir development mesajıdır (DEV environment)")
    
    # Test 4: ENV değişkenini kaldır (default TEST'e döner)
    print("\n=== Test 4: ENV removed (defaults to TEST) ===")
    if 'ENV' in os.environ:
        del os.environ['ENV']
    telegram_default = TelegramNotifier()
    telegram_default.send_notification("🧪 Bu bir default test mesajıdır")

if __name__ == "__main__":
    print("Telegram Environment Test başlatılıyor...")
    test_telegram_with_env()
    print("\nTest tamamlandı!") 