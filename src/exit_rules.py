import pandas as pd


class SimpleExitRules:
    """
    Simple exit strategy:
    - Stop loss: 2% below entry
    - Profit target: 7% above entry  
    - Time stop: 10 days max hold
    """
    
    def __init__(
        self,
        stop_loss_pct: float = 0.02,
        profit_target_pct: float = 0.07,
        max_hold_days: int = 10
    ):
        self.stop_loss_pct = stop_loss_pct
        self.profit_target_pct = profit_target_pct
        self.max_hold_days = max_hold_days
    
    def calculate_exits(self, entry_price: float) -> dict:
        """Given an entry price, calculate stop and target levels"""
        return {
            'stop_loss': entry_price * (1 - self.stop_loss_pct),
            'profit_target': entry_price * (1 + self.profit_target_pct),
            'max_hold_days': self.max_hold_days
        }
