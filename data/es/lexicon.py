import json
import unicodedata

from config import EXCLUSIONS, INVARIABLES, LEXICON_DICS, WORD_RE


def deaccent(word):
    """Removes the accents from a word"""
    return "".join(
        c for c in unicodedata.normalize("NFD", word) if unicodedata.category(c) != "Mn"
    )


def load_lexicon():
    """Reads the lexicon and maps each unaccented word to its written form"""
    lexicon = {}
    for path in LEXICON_DICS:
        for line in path.read_text(encoding="utf-8").splitlines():
            word = line.strip().split("/")[0].lower()
            if not word or "@" in word or not WORD_RE.fullmatch(word):
                continue
            lexicon.setdefault(deaccent(word), word)
    return lexicon


def load_exclusions():
    excluded = set()
    for words in json.loads(EXCLUSIONS.read_text(encoding="utf-8")).values():
        excluded.update(word.lower() for word in words)
    for line in INVARIABLES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            excluded.add(line.lower())
    return excluded
