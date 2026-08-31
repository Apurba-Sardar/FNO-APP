import pytest
from pydantic import ValidationError

from app.config import Settings


def test_trading_defaults_to_paper():
    assert Settings(_env_file=None).trading_mode == "paper"


def test_unknown_trading_mode_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, trading_mode="maybe")
