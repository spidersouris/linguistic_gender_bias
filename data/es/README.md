The following corpora must be added to /resources before running:

1. https://huggingface.co/datasets/agentlans/bluesky - subset "es" | folder "resources/bluesky-es"
2. https://huggingface.co/datasets/pysentimiento/spanish-tweets

```bash
uv sync
uv run python extract.py
```

## Sources

- Lexicon and rules: [`rabble/nobinarie`](https://github.com/rabble/nobinarie), MIT, commit
  `bbfdcfe0abf4822a6141ce84a9efee9e6c1374ed`.