from collections import Counter

from config import CORPORA, GRAMMAR, SKIP, WORDLIST
from language import keep_spanish
from lexicon import load_exclusions, load_lexicon
from morphology import lexicon_class, resolve
from scan import count_forms, scan
from tagging import keep_nouns
from wordlist import merge, to_lemmas, write

FORM_KEYS = ("masc_sg", "fem_sg", "masc_pl", "fem_pl")


def forms_to_count(candidates, lexicon):
    """Returns the word forms that the corpus must count"""
    forms = set()
    for candidate in candidates:
        stem = candidate["stem"]
        # only the stems that the lexicon cannot classify need corpus counts
        if lexicon_class(stem, lexicon) is None:
            forms.update([stem + "o", stem + "os", stem + "es"])
    return forms


def reconstruct(candidates, lexicon, freq, min_fallback_hits):
    """Adds the gender forms to each candidate. Removes candidates with no forms."""
    reconstructed = []
    for candidate in candidates:
        paradigm = resolve(candidate["stem"], lexicon, freq, min_fallback_hits)
        if paradigm:
            reconstructed.append({**candidate, **paradigm})
    return reconstructed


def is_filtered_out(candidate, exclusions):
    """Checks whether a candidate is a known non-noun or false positive"""
    # one of the gender forms is in the lexicon's exclusion lists
    if any(candidate[key] in exclusions for key in FORM_KEYS):
        return True
    # a determiner or pronoun, not a noun
    if candidate["masc_sg"] in GRAMMAR or candidate["masc_pl"] in GRAMMAR:
        return True
    # a known false positive
    return candidate["masc_sg"] in SKIP


def extract(corpus, lexicon, exclusions):
    """Finds the inclusive nouns in one corpus. Returns one row for each lemma."""
    print(f"Scanning {corpus['name']}")
    candidates = scan(corpus)
    tokens = sum(c["freq"] for c in candidates)
    print(f"{len(candidates)} candidate types / {tokens} tokens")

    candidates = [c for c in candidates if c["freq"] >= corpus["min_freq"]]
    print(f"{len(candidates)} candidates with occurrences >= {corpus['min_freq']}")

    wanted = forms_to_count(candidates, lexicon)
    freq = count_forms(corpus, wanted) if wanted else Counter()

    candidates = reconstruct(candidates, lexicon, freq, corpus["min_fallback_hits"])
    candidates = [c for c in candidates if not is_filtered_out(c, exclusions)]
    print(f"{len(candidates)} candidates after general filtering")

    candidates = keep_nouns(candidates)
    print(f"{len(candidates)} confirmed nouns in context")

    candidates = keep_spanish(candidates, lexicon)
    print(f"{len(candidates)} after the language filter")

    lemmas = to_lemmas(candidates, corpus["name"])
    print(f"{len(lemmas)} lemmas")
    return lemmas


def main():
    lexicon = load_lexicon()
    exclusions = load_exclusions()
    rows = merge([extract(corpus, lexicon, exclusions) for corpus in CORPORA])
    write(rows, WORDLIST)
    print(f"{len(rows)} lemmas saved to {WORDLIST}")


if __name__ == "__main__":
    main()
