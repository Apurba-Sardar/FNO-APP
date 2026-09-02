class BacktestError(RuntimeError):
    pass


class HistoricalDataError(BacktestError):
    pass


class FutureDataAccess(BacktestError):
    pass
