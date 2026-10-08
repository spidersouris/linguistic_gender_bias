import re
from collections import Counter

import py3langid as langid

from config import LANG_CANDIDATES, MIN_CHARS_FOR_LANGID, MIN_SPANISH_SHARE
from lexicon import deaccent

URL_RE = re.compile(r"https?://\S+|www\.\S+")
HANDLE_RE = re.compile(r"[@#]\w+")
SPACE_RE = re.compile(r"\s+")


def strip_tweet_tokens(text):
    """Removes URLs, handles and hashtags"""
    text = URL_RE.sub(" ", text)
    text = HANDLE_RE.sub(" ", text)
    text = text.replace("_USER_", " ").replace("_URL_", " ")
    return SPACE_RE.sub(" ", text).strip().lower()


def context_votes(candidate):
    """Get one language vote for each context that is long enough"""
    votes = Counter()
    for text, _, _ in candidate["contexts"]:
        cleaned = strip_tweet_tokens(text)
        if len(cleaned) >= MIN_CHARS_FOR_LANGID:
            votes[langid.classify(cleaned)[0]] += 1
    return votes


def is_spanish(candidate, lexicon):
    """Checks if a candidate is Spanish based on the classifying votes"""
    votes = context_votes(candidate)
    if not votes:
        return True
    if votes["es"] / sum(votes.values()) >= MIN_SPANISH_SHARE:
        return True
    return deaccent(candidate["masc_sg"]) in lexicon


def keep_spanish(candidates, lexicon):
    """Removes the candidates that are not Spanish."""
    langid.set_languages(LANG_CANDIDATES)
    return [c for c in candidates if is_spanish(c, lexicon)]
