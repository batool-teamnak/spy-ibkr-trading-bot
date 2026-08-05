import asyncio
import contextlib
import datetime
import importlib
import io
import math
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import config
import utils
from risk.manager import RiskManager
from risk import report
from market.candle import Candle, CandleBuilder
from market.sim_sl import SimStopLoss, CandleRecord
from strategy import orders
from strategy.manager import OrderManager

class TradingTests(unittest.TestCase):
    def setUp(self):
        orders.set_account('')


    def test_equity_baseline_validation(self):
        for equity in (0, -1, float('nan'), float('inf'), None, True):
            with self.assertRaises(ValueError):
                RiskManager(equity)
        risk = RiskManager(10000)
        risk.check(100)
        self.assertIn('hard_sl', risk.check(-101))

    def test_invalid_pnl_does_not_poison_risk_state(self):
        risk = RiskManager(10000)
        for pnl in (None, float('nan'), float('inf')):
            self.assertIsNone(risk.check(pnl))
        self.assertIsNone(risk._pnl_baseline)
        risk.check(100)
        self.assertIn('hard_sl', risk.check(-101))
