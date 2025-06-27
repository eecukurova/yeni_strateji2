# Environment Setup

Bu proje, Telegram bildirimlerinde environment bilgisini göstermek için `ENV` environment variable'ını kullanır.

## Environment Variable Ayarları

### 1. Environment Variable Tanımlama

Projenizde `ENV` environment variable'ını aşağıdaki değerlerden biriyle ayarlayabilirsiniz:

- `TEST` - Test ortamı (varsayılan)
- `PROD` - Production ortamı  
- `DEV` - Development ortamı

### 2. Environment Variable Ayarlama Yöntemleri

#### macOS/Linux Terminal:
```bash
# Geçici olarak (sadece mevcut terminal session için)
export ENV=TEST

# Kalıcı olarak (bash/zsh profile'a ekle)
echo 'export ENV=TEST' >> ~/.zshrc
source ~/.zshrc
```

#### Windows Command Prompt:
```cmd
# Geçici olarak
set ENV=TEST

# Kalıcı olarak
setx ENV TEST
```

#### Windows PowerShell:
```powershell
# Geçici olarak
$env:ENV = "TEST"

# Kalıcı olarak
[Environment]::SetEnvironmentVariable("ENV", "TEST", "User")
```

### 3. Environment Variable Kontrolü

Environment variable'ın doğru ayarlandığını kontrol etmek için:

```bash
# macOS/Linux
echo $ENV

# Windows Command Prompt
echo %ENV%

# Windows PowerShell
echo $env:ENV
```

### 4. Telegram Mesaj Formatı

Environment variable ayarlandıktan sonra, tüm Telegram mesajları şu formatta görünecektir:

```
🧪 [TEST]

🤖 Bot başlatıldı
Sembol: BNBUSDT
Timeframe: 15m
Kaldıraç: 10x
```

### 5. Environment Emojileri

- 🧪 `TEST` - Test ortamı
- 🚀 `PROD` - Production ortamı
- 🔧 `DEV` - Development ortamı

### 6. Test Etme

Environment ayarlarını test etmek için:

```bash
python test_telegram_env.py
```

Bu script farklı environment'larda test mesajları gönderecektir.

## Örnek Kullanım

```python
import os
from core.telegram.telegram_notifier import TelegramNotifier

# Environment variable'ı ayarla
os.environ['ENV'] = 'PROD'

# Telegram notifier'ı oluştur
telegram = TelegramNotifier()

# Mesaj gönder (otomatik olarak [PROD] prefix'i eklenecek)
telegram.send_notification("Bot başlatıldı!")
```

## Not

- Environment variable ayarlanmazsa, varsayılan olarak `TEST` kullanılır
- Environment variable değişikliği, TelegramNotifier instance'ı oluşturulduktan sonra yapılırsa etkili olmaz
- Her yeni TelegramNotifier instance'ı, o anki environment variable değerini kullanır 