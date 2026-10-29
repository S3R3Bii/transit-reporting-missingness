# Transit reporting gaps

When can a year-over-year bus-ridership increase be created by missing reports? This finite comparison tests dashboard summaries against captured published monthly unlinked passenger trips (UPT). Its reporting gaps are synthetic; they are not evidence of actual false agency reports or verified passenger changes.

Fixed stress. Mask prior-year reports from about 10% of service units chosen by largest 2019 boarding volume. These units account for 74.1–74.5% of baseline boardings, making this a concentrated-volume stress. Across 36 held months in 2023–2025, zero-fill mean absolute growth error is 319.349 percentage points, count rescaling 276.125 and matched-panel growth 1.289. Zero fill invents positive growth in four months. The matched panel misses one positive-growth month and changes the observed population.

Decision implication. Display reporting coverage, population and volume shares beside growth. Preserve zero, null and absent rows separately. Obtain service-status and reporting-vintage evidence before certifying an increase. Under illustrative twice-2019 component caps, all 972 aggregate intervals contain the benchmark, but 470 cases violate a cap. Containment alone does not validate assumptions.

Start with the [complete decision summary](DECISION_SUMMARY.md), [protocol](PROTOCOL.md), [freeze](FREEZE.json), [source manifest](data/source/manifest.json), [all results](results) and [independent manuscript](paper/manuscript.pdf).

![Fixed concentrated synthetic gap](figures/primary_growth.png)

```text
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python src/check_reproduction.py
python src/verify_summaries.py
python src/verify_figures.py
python src/verify_paper.py
python src/verify_public_package.py
```

Sixteen fixtures; 18 protected dependencies; 346,434 exact replay fields and three verification documents. Independent research, not peer reviewed. Formal-publication projects including Azure remain private.
