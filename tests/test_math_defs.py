"""USD conversion and gap / basis math."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.math_defs import (
    basis,
    convergence_shares,
    dislocation,
    price_at,
    same_sign,
    simple_return,
    to_usd,
)


def test_to_usd_passthrough_and_stables():
    assert to_usd(100.0, "USD") == 100.0
    assert abs(to_usd(100.0, "USDT", usdt_usd=0.999) - 99.9) < 1e-9
    assert abs(to_usd(100.0, "USDC", usdc_usd=1.001) - 100.1) < 1e-9


def test_basis_and_dislocation():
    assert abs(basis(2650.0, 2600.0) - (2650 / 2600 - 1)) < 1e-12
    b_weekday = 0.005
    d = dislocation(2610.0, 2600.0, b_weekday)
    # (2610/2600 - 1) - 0.005 ≈ -0.0011538
    assert abs(d - ((2610 / 2600 - 1) - 0.005)) < 1e-12


def test_simple_return_and_same_sign():
    assert abs(simple_return(110.0, 100.0) - 0.1) < 1e-12
    assert same_sign(0.01, 0.02) is True
    assert same_sign(0.01, -0.02) is False
    assert np.isnan(same_sign(0.0, 0.01))


def test_convergence_shares():
    gold_s, tok_s = convergence_shares(d=-0.01, gap=-0.004, r_post=0.005)
    # gold share = (-0.004)/(-0.01)=0.4; token = -0.005/(-0.01)=0.5
    assert abs(gold_s - 0.4) < 1e-12
    assert abs(tok_s - 0.5) < 1e-12


def test_price_at_tolerance_no_lookahead_fill():
    idx = pd.to_datetime(
        ["2025-01-10 22:00:00", "2025-01-10 22:01:00", "2025-01-10 22:05:00"], utc=True
    )
    s = pd.Series([100.0, 101.0, 105.0], index=idx)
    assert price_at(s, pd.Timestamp("2025-01-10 22:00:00", tz="UTC")) == 100.0
    # within 2 min
    assert price_at(s, pd.Timestamp("2025-01-10 22:02:00", tz="UTC"), tolerance_min=2) == 101.0
    # beyond tolerance → NaN (do not silently use 22:05)
    assert np.isnan(price_at(s, pd.Timestamp("2025-01-10 22:03:30", tz="UTC"), tolerance_min=1))
