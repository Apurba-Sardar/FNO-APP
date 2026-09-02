class LiveExecutionError(Exception):
    pass


class LiveConfigurationError(LiveExecutionError):
    pass


class LiveAuthorizationError(LiveExecutionError):
    pass


class SafetyGateRejected(LiveExecutionError):
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))


class StaleSignedRequest(LiveExecutionError):
    pass


class UnknownOrderState(LiveExecutionError):
    pass


class ProtectionFailure(LiveExecutionError):
    pass
