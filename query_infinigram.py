#!/usr/bin/env python3
"""Count gender-inclusive word forms across the training corpora of open LLMs
using the Infini-gram API: https://infini-gram.readthedocs.io/en/latest/api.html

Use:
uv run query_infinigram.py language=[fr|de|es]

Counts go to results/<lang>/results.json after every word.
Forms already counted are not queried again.
"""

import csv
import json
import logging
import time
from collections.abc import Iterator
from pathlib import Path

import coloredlogs
import hydra
import requests
from tqdm import tqdm

from models import (
    CorpusCount,
    DataRow,
    LanguageConfig,
    VariantsResults,
    WordsResults,
)

logger = logging.getLogger("infinigram")

ROOT = Path(__file__).parent
API = "https://api.infini-gram.io/"
QUERY_RETRIES = 5
WRITE_RETRIES = 7
SAVE_EVERY = 200  # save every X cells


def count(index: str, query: str) -> CorpusCount:
    """Return count and approximation status, both None if all retries fail."""
    for attempt in range(QUERY_RETRIES):
        try:
            response = requests.post(
                API,
                # see https://infini-gram.readthedocs.io/en/latest/api.html
                # for json structure to POST
                json={"index": index, "query_type": "count", "query": query},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            # check if request was successful
            if "error" not in data:
                return {"count": data["count"], "approx": data["approx"]}
            err = data["error"]
        except Exception as e:
            err = e
        time.sleep(min(2**attempt, 20))

    logger.error(f"{query} in {index}: {err}")
    return {"count": None, "approx": None}


def save(results: WordsResults | VariantsResults, out: Path, tmp: Path) -> None:
    """Saves results to a temporary file
    and then renames it to the final output path."""
    for attempt in range(WRITE_RETRIES):
        try:
            tmp.write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp.replace(out)
            return
        # can happen if the file is locked
        except PermissionError:
            if attempt == WRITE_RETRIES - 1:
                raise
            logger.warning(f"{out} is locked, retrying…")
            time.sleep(2**attempt)


def read_rows(path: Path) -> Iterator[dict[str, str]]:
    """Reads a CSV or text file and yields rows as dicts."""
    path = ROOT / path
    if path.suffix == ".csv":
        with open(path, encoding="utf-8", newline="") as f:
            yield from csv.DictReader(f)
        return

    with open(path, encoding="utf-8") as f:
        for line in f:
            word = line.strip()
            if word and not word.startswith("#"):
                yield {"word": word}


def caps(word: str) -> int:
    """Returns the number of uppercase letters in a word."""
    return sum(c.isupper() for c in word)


def load_words(lang: LanguageConfig) -> list[DataRow]:
    columns = lang.columns if lang.columns else ["word"]
    words = []
    for path in lang.files:
        for row in read_rows(path):
            for column in columns:
                word = row[column].strip()
                if word:
                    words.append(word)

    # Star forms are written inconsistently
    # (e.g., "Abiturient*Innen" and "Abiturient*innen")
    # keep the least capitalized spelling of each word
    best = {}
    for word in words:
        key = word.lower() if lang.dedupe_ignore_case else word
        if key not in best or caps(word) < caps(best[key]):
            best[key] = word

    logger.info(f"{len(best)} words from {len(words)} forms")
    return [DataRow(word, None, word) for word in best.values()]


def load_variants(lang: LanguageConfig) -> list[DataRow]:
    rows = {}
    for path in lang.files:
        for row in read_rows(path):
            key = row[lang.key_column].strip()
            if key:
                rows.setdefault(key, row)

    if lang.restrict:
        restriction = lang.restrict
        wanted = set()
        for row in read_rows(restriction.file):
            word = row[restriction.column].strip()
            if word:
                wanted.add(word)
        rows = {word: row for word, row in rows.items() if word in wanted}
        logger.info(f"{len(rows)}/{len(wanted)} words found")
        missing = wanted - set(rows)
        if missing:
            logger.warning(f"{len(missing)} words not found: {sorted(missing)[:10]}")

    variants = []
    for word, row in rows.items():
        for header, column in lang.columns.items():
            variant = row[column].strip()
            if variant:
                variants.append(DataRow(word, header, variant))
    return variants


@hydra.main(version_base=None, config_path="conf", config_name="config")
def main(cfg):
    coloredlogs.install(level=cfg.logs_level, logger=logger)
    lang: LanguageConfig = cfg.language  # e.g. conf/language/fr.yaml
    # load variants only for languages with a key column (e.g. French)
    # for other languages (German, Spanish), load words instead
    queries: list[DataRow] = (
        load_variants(lang) if lang.key_column else load_words(lang)
    )

    out: Path = ROOT / "results" / lang.code / "results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp: Path = out.with_suffix(".tmp")
    results = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}

    new = saved = 0
    for word, header, variant in tqdm(queries, unit="query"):
        cells = results.setdefault(word, {})
        # French: word -> strategy -> corpus. Other languages: word -> corpus
        if header:
            cells = cells.setdefault(header, {})

        for corpus in cfg.corpora:
            if cells.get(corpus, {}).get("count") is not None:
                continue
            cells[corpus] = count(corpus, variant)
            new += 1
            time.sleep(0.05)

        if new - saved >= SAVE_EVERY:
            save(results, out, tmp)
            saved = new

    if new > saved:
        save(results, out, tmp)
    logger.info(f"{new} new cells saved to {out}")


if __name__ == "__main__":
    main()
