"""エージェント基底クラス"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """エージェント実行結果"""
    agent_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    actions_required: list[str] = field(default_factory=list)
    summary: str = ""


class BaseAgent(ABC):
    """全エージェント共通の基底クラス"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self._results_history: list[AgentResult] = []

    @abstractmethod
    def analyze(self, **kwargs) -> AgentResult:
        """分析を実行し結果を返す"""
        ...

    @abstractmethod
    def generate_plan(self, **kwargs) -> dict[str, Any]:
        """計画を生成する"""
        ...

    @abstractmethod
    def identify_risks(self, **kwargs) -> list[str]:
        """リスクを特定する"""
        ...

    def store_result(self, result: AgentResult) -> None:
        self._results_history.append(result)

    @property
    def latest_result(self) -> AgentResult | None:
        return self._results_history[-1] if self._results_history else None
