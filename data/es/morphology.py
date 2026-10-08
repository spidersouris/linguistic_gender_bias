from config import VOWELS
from lexicon import deaccent

VOWEL_STEM = "A"  # Masculine form ending with -o, for example "amigo"
CONSONANT_STEM = "B"  # Masculine form is the bare stem, for example "chaval"
AGENTIVE_OR = "B-or"  # A class B stem that ends with -or, for example "profesor"


def lexicon_class(stem, lexicon):
    """Finds the class from the lexicon or the -or ending, else returns None"""
    if deaccent(stem + "o") in lexicon:
        return VOWEL_STEM
    if deaccent(stem) in lexicon:
        return CONSONANT_STEM
    if stem.endswith("or"):
        return AGENTIVE_OR
    return None


def inflection_class(stem, lexicon, freq, min_fallback_hits):
    """Finds the class of a stem. Returns None if the class cannot be guessed"""
    known = lexicon_class(stem, lexicon)
    if known:
        return known
    # when neither the lexicon nor the "or" ending determines the class,
    # the corpus counts decide the class
    vowel_stem_hits = freq.get(stem + "os", 0) + freq.get(stem + "o", 0)
    consonant_stem_hits = freq.get(stem + "es", 0)
    if max(vowel_stem_hits, consonant_stem_hits) < min_fallback_hits:
        return None
    # ties keep the consonant class
    if vowel_stem_hits > consonant_stem_hits:
        return VOWEL_STEM
    return CONSONANT_STEM


def vowel_stem(stem, lexicon):
    """Make the four forms of a class A noun: amigo, amiga, amigos, amigas"""
    masculine_sg = lexicon.get(deaccent(stem + "o"), stem + "o")
    base = masculine_sg[:-1]
    return {
        "masc_sg": masculine_sg,
        "fem_sg": base + "a",
        "masc_pl": base + "os",
        "fem_pl": base + "as",
    }


def consonant_stem(stem, masculine_sg):
    """Make the four forms of a class B noun: chaval, chavala, chavales, chavalas"""
    return {
        "masc_sg": masculine_sg,
        "fem_sg": stem + "a",
        "masc_pl": stem + "es",
        "fem_pl": stem + "as",
    }


def resolve(stem, lexicon, freq, min_fallback_hits):
    """Make the four gender forms of a stem. Returns None if the forms are unclear"""
    infl_class = inflection_class(stem, lexicon, freq, min_fallback_hits)

    if infl_class is None:
        return None

    if infl_class == VOWEL_STEM:
        return vowel_stem(stem, lexicon)

    # A class B noun cannot end with a vowel
    if stem[-1] in VOWELS:
        return None

    accented = lexicon.get(deaccent(stem))
    if accented:
        return consonant_stem(stem, accented)
    if infl_class == AGENTIVE_OR:
        return consonant_stem(stem, stem)
    return None
