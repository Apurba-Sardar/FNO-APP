from abc import ABC, abstractmethod


class TradeExecutor(ABC):
    @abstractmethod
    def execute_entry(self, *args, **kwargs): ...

    @abstractmethod
    def execute_exit(self, *args, **kwargs): ...

    @abstractmethod
    def cancel_order(self, *args, **kwargs): ...
