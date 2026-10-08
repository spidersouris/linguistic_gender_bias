import argparse
import json
import logging
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import coloredlogs
import plotly.graph_objects as go

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("plot")
coloredlogs.install(level=logging.INFO, logger=logger)

# corpora metadata (release date, token count, short name) for plotting
CORPORA_DATES = {
    "v4_olmo-2-0325-32b-instruct_llama": "2025-03",
    # "v4_olmo-mix-1124_llama": "2024-11",
    "v4_dclm-baseline_llama": "2024-06",
    "v4_dolma-v1_7_llama": "2024-01",
    "v4_rpj_llama_s4": "2023-04",
    "v4_c4train_llama": "2021-06-16",
    "v4_piletrain_llama": "2020-12-31",
}

CORPORA_TOKENS = {
    "v4_olmo-2-0325-32b-instruct_llama": 4_610_629_088_477,
    # "v4_olmo-2-1124-13b-instruct_llama": 4_610_749_614_285,
    # "v4_olmoe-0125-1b-7b-instruct_llama": 4_610_737_979_121,
    # "v4_olmo-mix-1124_llama": 4_575_475_702_047,
    "v4_dclm-baseline_llama": 4_341_627_197_578,
    "v4_dolma-v1_7_llama": 2_604_642_372_173,
    "v4_rpj_llama_s4": 1_385_942_948_192,
    "v4_c4train_llama": 198_079_554_945,
    "v4_piletrain_llama": 383_299_322_520,
}

SHORT_NAMES = {
    "v4_olmo-2-0325-32b-instruct_llama": "OLMo-2",
    # "v4_olmo-2-1124-13b-instruct_llama": "OLMo-2",
    # "v4_olmoe-0125-1b-7b-instruct_llama": "OLMo-E",
    # "v4_olmo-mix-1124_llama": "OLMo-M",
    "v4_dclm-baseline_llama": "DCLM",
    "v4_dolma-v1_7_llama": "Dolma",
    "v4_rpj_llama_s4": "RPJ",
    "v4_c4train_llama": "C4",
    "v4_piletrain_llama": "Pile",
}

# variants columns for French,
# with the queries to add and subtract to get the final count
FRENCH_COLUMNS = [
    ("paren sg.", ["paren_sg"], ["paren"]),
    ("paren pl.", ["paren"], []),
    ("brackets sg.", ["brackets_sg"], ["brackets"]),
    ("brackets pl.", ["brackets"], []),
    ("middot sg.", ["middot_sg"], ["middot_pl2"]),
    ("middot pl.", ["middot", "middot_pl2"], []),
    ("dot (doubled)", ["dot_pl2"], []),
    ("slash (doubled)", ["slash_pl2"], []),
]

NORMALIZE_BY_TOKENS = True
TOKENS_PER_UNIT = 1_000_000_000

# plot settings
LANGUAGE_LABELS = {"fr": "French", "de": "German", "es": "Spanish"}
LANGUAGE_COLORS = {"fr": "#CC79A7", "de": "#009E73", "es": "#E69F00"}
LANGUAGE_MARKERS = {"fr": "circle", "de": "square", "es": "diamond"}

LINE_DASH = "solid"
COLUMN_WIDTH_IN = 3.3
FIG_HEIGHT_IN = 2.55

BASE_DPI = 96
EXPORT_DPI = 300

WIDTH_PX = round(COLUMN_WIDTH_IN * BASE_DPI)
HEIGHT_PX = round(FIG_HEIGHT_IN * BASE_DPI)

FONT_FAMILY = "Futura Book BT, Helvetica, Arial, sans-serif"

AXIS_FONT_SIZE = 10
TICK_FONT_SIZE = 9
DATE_FONT_SIZE = 8
LEGEND_FONT_SIZE = 9


def parse_lang_arg(arg: str) -> tuple[str, Path]:
    if "=" not in arg:
        raise argparse.ArgumentTypeError(f"Expected LANG=PATH, got {arg!r}")
    lang, _, path = arg.partition("=")
    return lang.strip().lower(), Path(path.strip())


def axis_title_for(normalize: bool) -> str:
    return (
        "Forms per billion tokens (log scale)"
        if normalize
        else "Gender-inclusive forms (count, log scale)"
    )


def normalize_word_entry(entry: dict) -> dict:
    # the first value determines whether the entry has a strategy level (like French) or is just a single count (like German/Spanish)
    for first_value in entry.values():
        if isinstance(first_value, dict):
            if "count" in first_value and "approx" in first_value:
                return {"_all": entry}
        break
    return entry


def resolve_numbers(raw):
    resolved = {}
    clamped = 0
    for label, queries_to_add, queries_to_subtract in FRENCH_COLUMNS:
        corpora = set()
        for query in queries_to_add + queries_to_subtract:
            corpora.update(raw.get(query, {}))
        column = {}
        for corpus in corpora:
            added = 0
            for query in queries_to_add:
                added += raw.get(query, {}).get(corpus, 0)
            subtracted = 0
            for query in queries_to_subtract:
                subtracted += raw.get(query, {}).get(corpus, 0)
            value = added - subtracted
            if value < 0:
                clamped += 1
                value = 0
            column[corpus] = value
        resolved[label] = column
    if clamped:
        logger.warning(f"{clamped} negative cell(s) clamped to zero")
    return resolved


def aggregate(data: dict):
    """Sum counts across words for the data of a language."""
    strategy_by_corpus = defaultdict(lambda: defaultdict(int))
    has_strategies = False

    for _word, raw_entry in data.items():
        entry = normalize_word_entry(raw_entry)
        if set(entry.keys()) != {"_all"}:
            has_strategies = True
        for strategy, corpora in entry.items():
            for corpus, leaf in corpora.items():
                count = leaf.get("count", 0)
                if count is None:
                    raise ValueError(
                        f"Missing count for {strategy}/{corpus} in word {_word}"
                    )
                strategy_by_corpus[strategy][corpus] += count

    french_queries = set()
    for _, queries_to_add, queries_to_subtract in FRENCH_COLUMNS:
        french_queries.update(queries_to_add)
        french_queries.update(queries_to_subtract)
    if french_queries.intersection(strategy_by_corpus):
        strategy_by_corpus = resolve_numbers(strategy_by_corpus)

    corpus_totals = defaultdict(int)
    for corpora in strategy_by_corpus.values():
        for corpus, count in corpora.items():
            corpus_totals[corpus] += count

    return corpus_totals, strategy_by_corpus, has_strategies


def parse_date(date_str: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {date_str!r}")


def rate(corpus_totals, corpus):
    raw = corpus_totals.get(corpus, 0)
    if not NORMALIZE_BY_TOKENS:
        return raw
    return raw / CORPORA_TOKENS[corpus] * TOKENS_PER_UNIT


def compute_log_ticks(values, pad_decades: float = 0.15):
    positive = [v for v in values if v and v > 0]
    if not positive:
        # nothing plottable
        logger.error("No positive values to plot!!")
        return [1, 10], [0.0, 1.0]

    log_min = math.log10(min(positive))
    log_max = math.log10(max(positive))
    if log_min == log_max:
        log_min -= 0.5
        log_max += 0.5

    range_min = log_min - pad_decades
    range_max = log_max + pad_decades

    ticks = []
    exp = math.floor(range_min) - 1
    while exp <= math.ceil(range_max) + 1:
        for base in (1, 2, 5):
            tick = base * (10**exp)
            if range_min <= math.log10(tick) <= range_max:
                ticks.append(tick)
        exp += 1

    if not ticks:
        ticks = [min(positive), max(positive)]

    return sorted(set(ticks)), [range_min, range_max]


def make_figure(corpus_order, languages):
    xs = list(range(len(corpus_order)))
    fig = go.Figure()

    # collect positive values to size the log axis across all languages
    all_values = []
    for language in languages:
        for corpus in corpus_order:
            value = rate(language["corpus_totals"], corpus)
            if value and value > 0:
                all_values.append(value)
    tick_vals, axis_range = compute_log_ticks(all_values)

    for lang in languages:
        values = [rate(lang["corpus_totals"], corpus) for corpus in corpus_order]
        plotted_values = [value if value > 0 else None for value in values]

        fig.add_trace(
            go.Scatter(
                x=xs,
                y=plotted_values,
                mode="lines+markers",
                showlegend=False,
                line=dict(
                    width=1.5,
                    color=lang["color"],
                    dash="solid",
                ),
                marker=dict(
                    size=4.2,
                    color=lang["color"],
                    symbol=LANGUAGE_MARKERS.get(lang["code"], "circle"),
                    line=dict(
                        width=0.45,
                        color="white",
                    ),
                ),
                customdata=[
                    [
                        SHORT_NAMES.get(corpus, corpus),
                        parse_date(CORPORA_DATES[corpus]).strftime("%Y-%m"),
                    ]
                    for corpus in corpus_order
                ],
                connectgaps=False,
            )
        )

        # Separate invisible trace used for legend entries
        # to show one line per language
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="lines+markers",
                name=lang["label"],
                hoverinfo="skip",
                line=dict(
                    width=1,
                    color=lang["color"],
                    dash="solid",
                ),
                marker=dict(
                    size=8,
                    color=lang["color"],
                    symbol=LANGUAGE_MARKERS.get(lang["code"], "circle"),
                    line=dict(
                        width=0.6,
                        color="white",
                    ),
                ),
                showlegend=True,
            )
        )

    ticktext = []
    for corpus in corpus_order:
        name = SHORT_NAMES.get(corpus, corpus)
        date = parse_date(CORPORA_DATES[corpus]).strftime("%Y-%m")
        ticktext.append(
            f"<b>{name}</b><br>"
            f"<span style='font-size:{DATE_FONT_SIZE}px;"
            f"color:#666'>{date}</span>"
        )

    fig.update_xaxes(
        tickmode="array",
        tickvals=xs,
        ticktext=ticktext,
        tickangle=0,
        range=[-0.45, len(corpus_order) - 0.55],
        tickfont=dict(
            size=TICK_FONT_SIZE,
            family=FONT_FAMILY,
            color="#111",
        ),
        showgrid=False,
        showline=True,
        linecolor="#222",
        linewidth=1,
        mirror=False,
        ticks="outside",
        ticklen=3,
        tickwidth=1,
        tickcolor="#222",
        fixedrange=True,
    )

    fig.update_yaxes(
        title=dict(
            text=axis_title_for(NORMALIZE_BY_TOKENS),
            font=dict(
                size=AXIS_FONT_SIZE,
                family=FONT_FAMILY,
                color="#222",
            ),
            standoff=2,
        ),
        type="log",
        tickmode="array",
        tickvals=tick_vals,
        ticktext=[str(value) for value in tick_vals],
        range=axis_range,
        tickfont=dict(
            size=TICK_FONT_SIZE,
            family=FONT_FAMILY,
            color="#111",
        ),
        showgrid=True,
        gridcolor="#dddddd",
        gridwidth=0.7,
        zeroline=False,
        showline=True,
        linecolor="#222",
        linewidth=1,
        ticks="outside",
        ticklen=3,
        tickwidth=1,
        tickcolor="#222",
        fixedrange=True,
    )

    fig.update_layout(
        width=WIDTH_PX,
        height=HEIGHT_PX,
        template="plotly_white",
        font=dict(
            family=FONT_FAMILY,
            size=TICK_FONT_SIZE,
            color="#111",
        ),
        margin=dict(l=47, r=4, t=29, b=48),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="right",
            x=1.0,
            font=dict(
                size=9,
                family=FONT_FAMILY,
                color="#222",
            ),
            bgcolor="rgba(255,255,255,0)",
            borderwidth=0,
            itemsizing="constant",
            itemwidth=30,
            tracegroupgap=8,
        ),
        hoverlabel=dict(
            font=dict(
                family=FONT_FAMILY,
                size=11,
            )
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    return fig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "languages", nargs="+", type=parse_lang_arg, metavar="LANG=PATH"
    )
    parser.add_argument("--outdir-fig", type=Path, default=Path("figures"))
    parser.add_argument("--outdir-tables", type=Path, default=Path("tables"))
    parser.add_argument("--basename", type=str, default="evol")
    args = parser.parse_args()

    languages = []
    seen_corpora = set()
    for code, path in args.languages:
        if not path.exists():
            parser.error(f"File not found for language '{code}': {path}")
        with open(path, encoding="utf-8") as f:
            corpus_totals, strategy_by_corpus, has_strategies = aggregate(json.load(f))
        seen_corpora.update(corpus_totals)
        languages.append(
            {
                "code": code,
                "label": LANGUAGE_LABELS.get(code, code.upper()),
                "color": LANGUAGE_COLORS.get(code, "#000000"),
                "corpus_totals": corpus_totals,
                "strategy_by_corpus": strategy_by_corpus,
                "has_strategies": has_strategies,
            }
        )
        logger.info(
            f"[{code}] corpora: {len(corpus_totals)}, "
            f"total: {sum(corpus_totals.values())}"
        )
        if has_strategies:
            logger.info(f"strategy breakdown: {len(strategy_by_corpus)} strategies")

    # check if corpus is usable (has a release date, and optionally a token count)
    usable = seen_corpora & set(CORPORA_DATES)
    if NORMALIZE_BY_TOKENS:
        usable = usable.intersection(CORPORA_TOKENS)
    dropped = seen_corpora - usable
    if dropped:
        reason = "date/token count" if NORMALIZE_BY_TOKENS else "release date"
        logger.warning(f"no {reason} for {sorted(dropped)}, excluded from plot")
    corpus_order = sorted(usable, key=lambda c: parse_date(CORPORA_DATES[c]))
    if not corpus_order:
        parser.error("No corpora with a configured release date were found.")

    fig = make_figure(corpus_order, languages)
    args.outdir_fig.mkdir(parents=True, exist_ok=True)
    pdf_path = args.outdir_fig / f"{args.basename}.pdf"
    png_path = args.outdir_fig / f"{args.basename}.png"
    fig.write_image(str(pdf_path), format="pdf")
    logger.info(f"\nSaved PDF to {pdf_path}")
    fig.write_image(str(png_path), format="png", scale=EXPORT_DPI / BASE_DPI)
    logger.info(f"\nSaved PNG to {png_path}")


if __name__ == "__main__":
    main()
