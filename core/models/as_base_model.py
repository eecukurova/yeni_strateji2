from adapters.binance_adapter import binance_adapter
from data_layer.repositories.model_repository import model_repository
from data_layer.repositories.model_component_repository import model_component_repository
from data_layer.repositories.brokerage_account_repository import brokerage_account_repository
from data_layer.repositories.component_repository import component_repository
from data_layer.repositories.job_repository import job_repository
from indicators import bollinger_bands, average_volume,ema
from dataframes import get_last,get_last_limit
from utils import event_logger, get_duration, get_decimalpartlength,_time
import decimal
from math import pow
from datetime import datetime,timedelta
from tkinter.tix import Tree
from unittest import result
from decimal import Decimal
from datetime import datetime
from enums import Intervals,PriceType,ModelEvent
logging = event_logger().get_logger('model')

class as_base_model:
    broker:binance_adapter
    task_duration = 2
    
    def __init__(self,model_id,brokerage_account_id):
        self.IsDebugMode = False
        self.model_id = model_id
        self.brokerage_account_id = brokerage_account_id
        model_repo = model_repository()
        model = model_repo.get_by_id(self.model_id)
       
        self.component_id_money = model.component_id_money
        self.min_candle_volume = model.min_candle_volume
        self.target_profit_margin = model.target_profit_margin
        
        self.component_repo = component_repository()
        component_money = self.component_repo.get_by_id(self.component_id_money)
        self.symbol_money = component_money.code  
        self.interval = Intervals().get_byId(model.interval_id)   
        self.leverage = model.leverage
        self.startup_budget = model.startup_budget
        brokerage_account_repo = brokerage_account_repository()
        brokerage_account = brokerage_account_repo.get_by_id(self.brokerage_account_id)
        self.market_type_id = brokerage_account.market_type_id
        self.broker = binance_adapter(brokerage_account.api_key,brokerage_account.api_secret)

    # ... [Diğer metodlar aynı kalacak] 