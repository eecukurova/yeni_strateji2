import logging
import logging.handlers
import sys
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

class LoggingConfig:
    def __init__(self):
        self.log_dir = "logs"
        self.log_level = logging.INFO  # ERROR'den INFO'ya değiştirdim
        self.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        self.date_format = "%Y-%m-%d %H:%M:%S"
        self.max_bytes = 10 * 1024 * 1024  # 10 MB
        self.backup_count = 5

    def setup_logging(self, name):
        """
        Loglama yapılandırmasını kurar
        Args:
            name: Logger adı ve log dosya adı
        Returns:
            logger: Yapılandırılmış logger objesi
        """
        # Log dizinini oluştur
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        # Logger oluştur
        logger = logging.getLogger(name)
        logger.setLevel(self.log_level)

        # Eğer handler zaten varsa, yeniden ekleme
        if logger.handlers:
            return logger

        # Formatter oluştur
        formatter = logging.Formatter(self.log_format, self.date_format)

        # Dosya handler oluştur
        log_file = os.path.join(self.log_dir, f"{name}.txt")
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(formatter)

        # Konsol handler oluştur
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(formatter)

        # Handler'ları logger'a ekle
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        # İlk log mesajı
        logger.info(f"Logger '{name}' başlatıldı - Log dosyası: {log_file}")

        return logger

# Standalone setup_logging function for direct import
def setup_logging(name):
    """
    Loglama yapılandırmasını kurar (standalone function)
    Args:
        name: Logger adı ve log dosya adı
    Returns:
        logger: Yapılandırılmış logger objesi
    """
    config = LoggingConfig()
    return config.setup_logging(name)
        