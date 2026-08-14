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

    def test_trading_hours_skip_corrupt_and_previous_sessions(self):
        day = datetime.datetime(2026,7,6,10,tzinfo=utils.ET)
        raw = '20260705:2000-20260706:0800;20260706:9999-20260706:1600;20260706:0930-20260706:1600'
        with patch.object(utils, 'now_et', return_value=day):
            sessions = utils.parse_trading_hours(raw)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0][0].hour, 9)

    def test_split_session_is_not_an_early_close(self):
        with patch.object(utils, 'now_et', return_value=datetime.datetime(2026,7,6,10,tzinfo=utils.ET)):
            self.assertFalse(utils.is_early_close('20260706:0930-20260706:1200;20260706:1300-20260706:1600'))
            self.assertTrue(utils.is_early_close('20260706:0930-20260706:1300'))

    def test_single_share_entry_has_no_empty_child(self):
        app = MagicMock()
        app.next_id.side_effect = range(1,100)
        manager = OrderManager(app, 1)
        manager._open = 500
        asyncio.run(manager._place_yz())
        self.assertEqual(app.placeOrder.call_count, 2)
        for call in app.placeOrder.call_args_list:
            self.assertEqual(call.args[2].totalQuantity, 1)
            self.assertTrue(call.args[2].transmit)

    def test_single_share_protective_stop(self):
        app = MagicMock()
        app.next_id.side_effect = range(1,100)
        manager = OrderManager(app,1)
        manager._pos_qty = 1
        asyncio.run(manager._place_stp3('SELL',499.99))
        app.placeOrder.assert_called_once()
        self.assertTrue(app.placeOrder.call_args.args[2].transmit)
        self.assertEqual(manager._s3_cid,0)

    def test_invalid_order_requests_are_rejected(self):
        for action, qty in (('buy',1),('BUY',0),('SELL',-1),('BUY',1.5),('SELL',True)):
            with self.assertRaises(ValueError):
                orders.mkt(action,qty,0,True)
        self.assertEqual(orders.mkt('BUY',2,0,True).totalQuantity,2)
