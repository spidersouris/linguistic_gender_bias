import re
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = CURRENT_DIR / "resources"
OUT = CURRENT_DIR / "words"

WORDLIST = OUT / "es_nouns.csv"

EXCLUSIONS = RESOURCES_DIR / "rabble__nobinarie__exclusions.json"
INVARIABLES = RESOURCES_DIR / "rabble__nobinarie__invariables.txt"
LEXICON_DICS = [
    RESOURCES_DIR / "rabble__nobinarie__es-AR_inclusive_conservative_@.dic",
    RESOURCES_DIR / "rabble__nobinarie__es-MX_inclusive_conservative_@.dic",
]

# min_freq: the smallest count for a candidate to stay
# min_fallback_hits: the smallest count to select the stem class
# freq_shards: how many shards to count. None counts all the shards
CORPORA = [
    {
        "name": "bluesky",
        "kind": "jsonl",
        "path": RESOURCES_DIR / "bluesky-es" / "es.jsonl",
        "min_freq": 1,
        "min_fallback_hits": 1,
        "freq_shards": None,
    },
    {
        "name": "tweets",
        "kind": "parquet",
        "path": RESOURCES_DIR / "spanish-tweets" / "data",
        "min_freq": 10,
        "min_fallback_hits": 2,
        "freq_shards": 10,
    },
]

ACCENTS = "áéíóúüñ"
# finds a word that ends with "@" or "@s", for example "amig@s"
CANDIDATE_RE = re.compile(
    rf"(?<![\w@])([a-z{ACCENTS}]{{3,}})@(s?)(?![\w@])(?!\.[\w@])", re.IGNORECASE
)
# finds plain words
# used by scan.py to count known word forms
WORD_RE = re.compile(rf"[a-z{ACCENTS}]+", re.IGNORECASE)
VOWELS = frozenset("aeiouáéíóú")

# the largest number of example contexts to keep for each candidate
SAMPLE_CAP = 40
WORKERS = 12
BATCH_SIZE = 256

SPACY_MODEL = "es_dep_news_trf"
SENTENCE_END = tuple(".!?\n:¡¿…")

# determiners and pronouns that can take an "@" form but that are not nouns
GRAMMAR = frozenset(
    """todo todos otro otros mucho muchos poco pocos alguno algunos ninguno ningunos
    cuanto cuantos tanto tantos cierto ciertos vario varios demasiado demasiados
    este estos ese esos aquel aquellos mismo mismos propio propios
    uno unos nosotros vosotros ellos nuestro nuestros vuestro vuestros suyo suyos
    junto juntos solo solos ambos sendos""".split()
)

# known false positives
SKIP = frozenset({"mierdo", "lucho", "culo", "orto", "cubo", "cielo", "elemento"})

# config options to only keep Spanish examples, using module py3langid
# (not Gallician, Portuguese or other similar languages)
LANG_CANDIDATES = ["es", "ca", "gl", "pt", "en", "eu"]
# a candidate stays if this share of its contexts is Spanish
MIN_SPANISH_SHARE = 0.5
# ignore contexts that are shorter than this
MIN_CHARS_FOR_LANGID = 20
