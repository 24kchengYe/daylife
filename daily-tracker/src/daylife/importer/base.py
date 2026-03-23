"""导入器基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ImportResult:
    rows_imported: int = 0
    rows_skipped: int = 0
    errors: list[str] | None = None


class BaseImporter(ABC):
    @abstractmethod
    def preview(self, file_path: str, **kwargs) -> list[dict]:
        """预览导入数据"""
        ...

    @abstractmethod
    def execute(self, file_path: str, **kwargs) -> ImportResult:
        """执行导入"""
        ...
