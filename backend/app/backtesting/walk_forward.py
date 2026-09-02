from datetime import datetime, timedelta

from pydantic import BaseModel


class WalkForwardWindow(BaseModel):
    in_sample_start: datetime
    in_sample_end: datetime
    out_of_sample_start: datetime
    out_of_sample_end: datetime


def build_walk_forward_windows(start, end, train_days: int, test_days: int):
    windows = []
    cursor = start
    while cursor + timedelta(days=train_days + test_days) <= end:
        split = cursor + timedelta(days=train_days)
        test_end = split + timedelta(days=test_days)
        windows.append(
            WalkForwardWindow(
                in_sample_start=cursor,
                in_sample_end=split,
                out_of_sample_start=split,
                out_of_sample_end=test_end,
            )
        )
        cursor += timedelta(days=test_days)
    return windows
