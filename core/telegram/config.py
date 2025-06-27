import os

class Config:
    def __init__(self):
        self.bot_token='7956697051:AAErScGMFGVxOyt3dGiw0jrFoakBELRdtm4'
        self.chat_id='891700810'
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        # Environment configuration
        self.environment = os.getenv('ENV', 'TEST')  # Default olarak TEST, environment variable'dan alır