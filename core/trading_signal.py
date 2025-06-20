
class TradingSignal:
    def __init__(self, side, quantity, entry_price, stop_loss, take_profit):
        self.side = side
        self.quantity = quantity
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit = take_profit
