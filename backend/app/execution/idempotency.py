from .models import ExecutionIntent


class ExecutionIdempotencyGuard:
    @staticmethod
    def find_existing(intents: dict, setup_id: str) -> ExecutionIntent | None:
        return next((intent for intent in intents.values() if intent.setup_id == setup_id), None)
