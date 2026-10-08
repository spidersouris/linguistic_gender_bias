import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import pyarrow.parquet as pq

from config import CANDIDATE_RE, SAMPLE_CAP, WORD_RE, WORKERS


def shards(corpus):
    """Return the list of files to read for a corpus"""
    if corpus["kind"] == "jsonl":
        return [corpus["path"]]
    return sorted(corpus["path"].glob("*.parquet"))


def read_texts(path, kind):
    if kind == "jsonl":
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)["text"]
        return

    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(batch_size=100_000, columns=["text"]):
        yield from batch.column("text").to_pylist()


def scan_shard(job):
    """Find the "@" words in one file. Count them and keep example contexts"""
    path, kind = job
    counts = Counter()
    samples = {}
    for text in read_texts(path, kind):
        # most texts have no "@", so skip them before running the regex
        if not text or "@" not in text:
            continue
        for match in CANDIDATE_RE.finditer(text):
            stem = match.group(1).lower()
            plural = bool(match.group(2))
            key = (stem, plural)
            counts[key] += 1
            contexts = samples.setdefault(key, [])
            if len(contexts) < SAMPLE_CAP:
                contexts.append((text, match.start(), match.end()))
    return counts, samples


def count_shard(job):
    """Count how many times each wanted word occurs in one file"""
    path, kind, wanted = job
    found = Counter()
    for text in read_texts(path, kind):
        if not text:
            continue
        for word in WORD_RE.findall(text):
            word = word.lower()
            if word in wanted:
                found[word] += 1
    return found


def run_shards(worker, jobs, label):
    """Run the worker on all the jobs, one process for each shard"""
    results = []
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        for done, result in enumerate(pool.map(worker, jobs), start=1):
            results.append(result)
            if done % 20 == 0 or done == len(jobs):
                print(f"{label} {done}/{len(jobs)} shards")
    return results


def scan(corpus):
    """Find the candidates in a corpus. Make one record for each stem and number"""
    jobs = [(shard, corpus["kind"]) for shard in shards(corpus)]
    counts = Counter()
    samples = {}
    for shard_counts, shard_samples in run_shards(scan_shard, jobs, "scanned"):
        counts.update(shard_counts)
        # keep no more than SAMPLE_CAP contexts for each candidate
        for key, contexts in shard_samples.items():
            kept = samples.setdefault(key, [])
            remaining = SAMPLE_CAP - len(kept)
            kept.extend(contexts[:remaining])
    return [
        {
            "stem": stem,
            "plural": plural,
            "freq": freq,
            "contexts": samples[(stem, plural)],
        }
        for (stem, plural), freq in counts.items()
    ]


def count_forms(corpus, wanted):
    """Count the wanted word forms.
    These counts are used to select the stem class"""
    files = shards(corpus)
    shard_limit = corpus["freq_shards"]
    if shard_limit is not None:
        files = files[:shard_limit]
    jobs = [(path, corpus["kind"], wanted) for path in files]
    freq = Counter()
    for found in run_shards(count_shard, jobs, "counted"):
        freq.update(found)
    return freq
