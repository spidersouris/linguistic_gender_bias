import csv
import re
from collections import defaultdict

COLUMNS = [
    "masculine_sg",
    "feminine_sg",
    "inclusive_sg",
    "masculine_pl",
    "feminine_pl",
    "inclusive_pl",
    "number_attested",
    "source",
    "example",
]


def shortest_example(candidate):
    """Return the shortest context of a candidate as one line of text."""
    if not candidate["contexts"]:
        return ""
    text, _, _ = min(
        candidate["contexts"], key=lambda context: (len(context[0]), context[0])
    )
    return re.sub(r"\s+", " ", text).strip()


def join_numbers(numbers):
    """Join the attested numbers, remove the duplicates and put 'sg' before 'pl'"""
    return ";".join(number for number in ("sg", "pl") if number in numbers)


def to_lemmas(candidates, source):
    """Group the candidates by masculine singular, with one row for each lemma"""
    groups = defaultdict(list)
    for candidate in candidates:
        groups[candidate["masc_sg"]].append(candidate)

    lemmas = {}
    for masculine_sg, group in groups.items():
        # most frequent form, where a singular form wins the tie
        head = max(
            group, key=lambda candidate: (candidate["freq"], not candidate["plural"])
        )
        example = min(
            (shortest_example(c) for c in group if c["stem"] == head["stem"]), key=len
        )
        attested_numbers = ["pl" if c["plural"] else "sg" for c in group]
        lemmas[masculine_sg] = {
            "masculine_sg": masculine_sg,
            "feminine_sg": head["fem_sg"],
            "inclusive_sg": head["stem"] + "@",
            "masculine_pl": head["masc_pl"],
            "feminine_pl": head["fem_pl"],
            "inclusive_pl": head["stem"] + "@s",
            "number_attested": join_numbers(attested_numbers),
            "source": source,
            "example": example,
        }
    return lemmas


def merge(lemmas_by_source):
    """Merge the rows of all the corpora, and sort them by masculine singular"""
    merged = {}
    for lemmas in lemmas_by_source:
        for masculine_sg, row in lemmas.items():
            seen = merged.get(masculine_sg)
            if seen is None:
                merged[masculine_sg] = row
                continue
            seen["number_attested"] = join_numbers(
                seen["number_attested"].split(";") + row["number_attested"].split(";")
            )
            seen["source"] = "both"
            if len(row["example"]) < len(seen["example"]):
                seen["example"] = row["example"]
    return [merged[masculine_sg] for masculine_sg in sorted(merged)]


def write(rows, path):
    """Write the rows to a CSV file"""
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
