# Transit reporting gaps: fixed retrospective design

## Decision and acceptance criteria

When can a displayed year-over-year bus-ridership recovery be created by a reporting gap? The deliverable is a reproducible, finite comparison of dashboard summaries on captured published NTD monthly unlinked passenger trips (UPT). UPT is a boarding count, not unique travelers, reliability, passenger benefit or latent demand. No deployment, causal, savings, new estimator or exhaustive novelty claim is intended.

Success requires a protocol before count retrieval; source rights/schema/version/key/control reconciliation; complete comparisons and exclusion exports; independent exact math and isolated replay; readable executive framing and original checked figures; reviewed independent manuscript; scoped canonical/privacy audit; exact-head Linux success, matching merged tree and annotated remote tag. Unverified required source/math/privacy evidence blocks a release.

## Source, grain and privacy

Use official DOT Monthly Modal Time Series 5 ti2-5 uiv, MB mode only, calendar2019-2025. Schema and PUBLIC_DOMAIN license were inspected before values. Retrieve only NTD agency ID, type of service, year, month timestamp and UPT. Do not retrieve safety events, private contacts or individual passengers. The unit is agency-service/month; DO/PT and other source service types remain distinct. Require uniqueness, nonnegative integer UPT or explicit null and matching year/date fields. Preserve explicit zero, explicit null and absent row separately. Independent server agency-year and monthly counts, non-null counts and sums must reconcile; before/after metadata revisions must match.

FTA describes explicit null monthly service entries as late reporting. An absent row can also reflect entry, exit or reporting-scope change, so absence is not asserted to be delinquency. Published counts may be revised; available estimation/provenance flags are not supplied in this projection. Treat the benchmark as captured published entries, not verified passenger truth or the original historical information set. Do not compare national totals with a broader or incompatible reporting population.

## Fixed cohort, phases and synthetic gaps

The baseline roster contains every MB agency-service key with twelve nonnegative integer entries and positive annual UPT in2019. For each target year2020-2025, retain a paired complete benchmark only when that key has all24 prior/current monthly entries; export every inclusion/exclusion. This conditions on complete published records and can exclude entering, exiting or incomplete services. It is a retrospective finite benchmark, not a prospective prediction sample.

Development targets2020-2022; held targets2023-2025. Freeze executable source/protocol/code and any derived roster bytes before held analytical summaries. Raw inputs and source-quality checks are visible without blinding. No model is fitted and no policy is selected.

For each eligible year-pair, mask ceil(p*n) service units, with p in{1/20,1/10,1/5}. Rank by baseline2019 annual UPT descending, ascending or identifier; volume ties break by agency ID then service type. Mask all twelve months in the prior year, current year or both. These27 persistent block gaps are deterministic stress scenarios, not estimated real missingness mechanisms or random samples. Preserve all cases. The primary scenario is10% of units, descending baseline volume, prior-year-only gap; other settings are sensitivity cases.

## Summaries, assumptions and metrics

Compare three point views against the unmasked complete published-cohort monthly year-over-year growth: zero-filled sums; period totals rescaled by full/observed unit counts separately; and a matched-unit panel with both monthly values present. Matched panels have a different observed population and rescaling assumes representativeness; neither is claimed unbiased under informative missingness. Growth is current/prior minus1; prior total0 makes a percentage undefined, which must be exported rather than coerced to0. Positive, zero and negative signs remain distinct.

For each missing unit, assume only0 <= UPT <= gamma times its same-calendar-month2019 UPT, gamma in{1,2,4}. These untuned caps are explicit sensitivity assumptions, not confidence intervals, validated capacity limits or universal physical bounds. Sum component lower/upper totals. The conditional growth interval is current_lower/prior_upper-1 through current_upper/prior_lower-1 when denominators are positive; zero denominators yield the explicit undefined/unbounded endpoint states. Record every actual hidden value violating its assigned cap. An interval with a violated assumption cannot be certified valid merely because it happens to contain aggregate truth. With nonnegativity alone, no finite missing-count upper bound follows.

Retain exact rational point errors, conditional interval endpoints, strict/weak sign comparisons, width, truth inclusion, component bound violations, observed/hidden unit counts and2019-volume coverage. Primary summaries use equal monthly weighting, with every year/month and scenario visible; no p-values, inferred population coverage or future-performance claim. Development checks may repair defects without selecting narrative outcomes; any post-held correction must be labeled retrospective.

## Independent checks and presentation

Fixtures cover null versus zero, missing keys, key collisions, fraction rounding, ranking ties, both-period masking, growth signs, no denominator and interval endpoint logic. An independent SQLite/integer/rational checker must not import production analysis helpers. Reconstruct masks, eligibility, all totals, point views and bounds from source projection. An isolated replay must reproduce deterministic exports. Original figures require actual-artist numeric and export-hash checks; manuscript numbers must be recomputed independently and every final page rendered and viewed. Source/model assumptions, actual choices, failed scenarios and selection limitations remain visible.

Reviewed independent program manuscript publication is authorized. Formal-publication projects, including Azure optimization, stay private. All50 completion requires actual releases; protocols and source holds are not completed studies.
