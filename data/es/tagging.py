from collections import defaultdict

import spacy

from config import BATCH_SIZE, SENTENCE_END, SPACY_MODEL


def surface_masculine(candidate):
    return candidate["masc_pl"] if candidate["plural"] else candidate["masc_sg"]


def cased_for_context(text, start, word):
    """Write the word with a capital letter if it starts a sentence."""
    before = text[:start].rstrip()
    if not before or before.endswith(SENTENCE_END):
        return word.capitalize()
    return word


def rewrite_to_masculine(text, occurrences):
    """Put the masculine form in place of each "@" word. Returns the new text and spans."""
    pieces = []
    spans = []
    cursor = 0
    offset = 0
    for candidate, start, end in occurrences:
        replacement = cased_for_context(text, start, surface_masculine(candidate))
        pieces.append(text[cursor:start])
        pieces.append(replacement)
        spans.append((candidate, start + offset, start + offset + len(replacement)))
        # adjust later spans by the change in length of this replacement
        offset += len(replacement) - (end - start)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces), spans


def token_at(doc, start, end):
    """Returns the last token of the span"""
    span = doc.char_span(start, end, alignment_mode="expand")
    return span[-1] if span else None


def load_tagger():
    try:
        on_gpu = spacy.require_gpu()
    except Exception:
        on_gpu = False
    print(f"spaCy loaded on {'GPU' if on_gpu else 'CPU'}")
    return spacy.load(SPACY_MODEL, disable=["parser", "lemmatizer"])


def keep_nouns(candidates):
    """Keep only the candidates that the tagger marks as a noun in the context."""
    # group the occurrences by text
    by_text = defaultdict(list)
    for candidate in candidates:
        for text, start, end in candidate["contexts"]:
            by_text[text].append((candidate, start, end))

    rewritten = []
    for text, occurrences in by_text.items():
        occurrences.sort(key=lambda occurrence: occurrence[1])
        rewritten.append(rewrite_to_masculine(text, occurrences))

    nlp = load_tagger()
    nouns = set()  # ids of the candidates tagged as a noun at least once
    docs = nlp.pipe([text for text, _ in rewritten], batch_size=BATCH_SIZE)
    for doc, (_, spans) in zip(docs, rewritten, strict=True):
        for candidate, start, end in spans:
            token = token_at(doc, start, end)
            if token is not None and token.pos_ == "NOUN":
                nouns.add(id(candidate))
    return [candidate for candidate in candidates if id(candidate) in nouns]
