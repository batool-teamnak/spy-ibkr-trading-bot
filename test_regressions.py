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

    def test_invalid_timed_pnl_preserves_state(self):
        risk = RiskManager(10000)
        for pnl in (None, float('nan'), float('inf')):
            self.assertFalse(risk.check_noon(pnl))
            self.assertFalse(risk.done)
        self.assertTrue(risk.check_noon(400))

    def test_trailing_profit_gap_and_retrace(self):
        risk = RiskManager(10000)
        risk.check(0)
        self.assertIsNone(risk.check(3050))
        self.assertAlmostEqual(risk._tp2_peak_pct, .305)
        self.assertAlmostEqual(risk._tp2_trail, 3000)
        self.assertIn('tp2', risk.check(2999))
        huge = RiskManager(10000)
        huge.check(0)
        huge.check(1e12)
        self.assertGreater(huge._tp2_trail, 1e11)

    def test_insufficient_margin_returns_no_position(self):
        self.assertEqual(utils.calc_leg_qty(100, 200), 0)
        self.assertEqual(utils.calc_leg_qty(1000, 100), 9)

    def test_sizing_invalid_inputs_are_zero(self):
        for equity, margin in ((float('nan'),100),(100,float('inf')),(100,0),(-1,100),(None,100)):
            self.assertEqual(utils.calc_leg_qty(equity,margin), 0)
