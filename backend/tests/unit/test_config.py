import pytest
from pydantic import ValidationError

from app.config import Settings


def test_trading_defaults_to_paper():
    assert Settings(_env_file=None).trading_mode == "paper"


def test_unknown_trading_mode_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, trading_mode="maybe")


def test_phase10_accepts_live_label_but_keeps_submission_fail_closed():
    settings = Settings(_env_file=None, trading_mode="live")
    assert settings.live.submission_configured is False


def test_phase9_paper_environment_names_are_centralized():
    settings = Settings(
        _env_file=None,
        paper_initial_equity=50_000,
        paper_entry_slippage_bps=7,
        paper_funding_enabled=True,
    )
    assert settings.paper.initial_equity == 50_000
    assert settings.paper.entry_slippage_bps == 7
    assert settings.paper.funding_enabled is True
