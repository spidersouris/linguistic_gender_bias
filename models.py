from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, TypedDict


@dataclass
class RestrictConfig:
    file: Path
    column: str


@dataclass
class LanguageConfig:
    code: str
    files: list[Path]
    key_column: str | None
    # French: strategy -> column. Spanish: list of columns. German: None
    columns: dict[str, str] | list[str] | None
    dedupe_ignore_case: bool
    restrict: RestrictConfig | None


@dataclass
class Config:
    logs_level: str
    corpora: list[str]
    language: LanguageConfig


class DataRow(NamedTuple):
    word: str
    header: str | None
    variant: str


class CorpusCount(TypedDict):
    count: int | None
    approx: bool | None


# word -> corpus -> count/approx
# e.g. {"word": {"corpus": {"count": 123, "approx": False}}}
WordsResults = dict[str, dict[str, CorpusCount]]

# word -> strategy -> corpus -> count/approx
# e.g. {"word": {"strategy": {"corpus": {"count": 123, "approx": False}}}}
VariantsResults = dict[str, dict[str, dict[str, CorpusCount]]]
