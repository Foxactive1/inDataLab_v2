from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseRuntime(ABC):

    @abstractmethod
    def execute(self, cell) -> Dict[str, Any]:
        pass