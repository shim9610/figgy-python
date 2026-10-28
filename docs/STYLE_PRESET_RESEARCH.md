# Style preset research and current gaps

Checked: 2026-10-26. This document separates verified source requirements,
measured implementation behavior, and product choices. The task profiles are now
implemented; none claims complete publication compliance.

## Current status

The six legacy presets are generic appearance starting points. None is a
validated journal profile or a complete dashboard design system. Existing tests
establish API behavior, data/text/domain preservation and transactional edits;
they do not establish editorial compliance, accessibility or task suitability.

The palette in `paper`, `report` and `colorblind` is identical. Their main
appearance difference is the grid. The standalone `colorblind` name does not
constitute a whole-chart accessibility guarantee. `monochrome` repeats three
grays and supplies no additional dash/marker discrimination for more series.
`dark` is a surface treatment; it is not an operational-monitoring profile.

Fourteen additional task profiles now implement the architecture below, with
execution-local declarations, construction-time inheritance, explicit argument
precedence, category keys and semantic roles. The [catalog](STYLE_PROFILES.md)
contains the actual rendered examples and source/implementation boundaries.
New light/dark palettes and semantic role colors measure above 4.5:1 against
their opaque profile backgrounds; this is not a CVD or whole-chart guarantee.
The [new profile measurements](measurements/style-profiles-20261026.json) retain
physical DPI, source guidance, palette/role contrasts and renderer provenance.

## Verified primary sources

| Source | Verified guidance | Consequence |
| --- | --- | --- |
| [Matplotlib customization](https://matplotlib.org/stable/users/explain/customizing.html) | Current default X/Y tick direction is outward; other directions are configurable. | A library default is not a universal editorial requirement. |
| [Korean Journal of Fisheries and Aquatic Sciences instructions](https://www.e-kfas.org/intro/instructions.asp) | Figures use a four-sided frame and inward ticks. | The current all-outward preset cannot claim this journal's style. |
| [Nature final submission](https://www.nature.com/nature/for-authors/final-submission) and [figure specifications](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/) | Typical final widths are 89/183 mm; ordinary figure lettering is 5–7 pt, with separate panel-letter rules. Standard sans-serif fonts and editable vector artwork/font handling matter. | A generic 11 pt preset is not a Nature profile. Validate at final physical size. Our current PNG-only export cannot establish editable-vector compliance. These sources do not establish a universal tick-direction rule. |
| [Proceedings of the IEEE figure guidelines](https://proceedingsoftheieee.ieee.org/resources/guidelines-for-figures-and-tables/) | Approximately 9–10 pt lettering is recommended, with consistent typography, sufficient margins and accessible colors. | This is a different target from Nature. Do not generalize these recommendations to every IEEE publication or imply an unspecified tick rule. |
| [Okabe and Ito: Color Universal Design](https://jfly.uni-koeln.de/color/index.html) | Guidance from the palette's authors addresses color-vision differences and figure/presentation design. | Palette provenance is useful, but does not replace checking background contrast and redundant identification in each use case. |
| [Carbon color palettes](https://www.carbondesignsystem.com/building-blocks/data-visualization/color-palettes) | Distinguishes categorical, sequential, diverging and alert palettes; gives separate light/dark choices and semantic examples. | Color policy must follow the data's meaning, not just a cycling list of hues. |
| [WCAG non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) and [use of color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html) | Essential graphical cues generally need 3:1 against adjacent colors. Meaning must not depend on hue alone. Context and equivalent information can affect the assessment. | Check actual rendered backgrounds/alpha and use labels, shapes, patterns or other sufficient alternatives. This is not a rule requiring every pair of category colors to have 3:1 contrast. |
| [Microsoft dashboard guidance](https://learn.microsoft.com/en-us/power-bi/create-reports/service-dashboards-design-tips) | Audience, viewing device, information hierarchy, consistent scales and category colors determine dashboard choices. | Dashboard purpose and viewing conditions need separate policies. A light/dark switch is insufficient. |
| [Grafana dashboard best practices](https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/) | USE, RED and the four golden signals address different observability questions. Dashboards should answer a question and reduce cognitive load. | Operational dashboards need stable semantics and meaningful status encodings rather than arbitrary category coloring. |

The main Science manuscript page returned HTTP 403 during this review. No
Science-specific quantitative profile was accepted from third-party summaries.
No APS-specific inward-tick requirement was verified. Requirements not found in
the checked sources must be marked as design choices, not attributed to a journal.

## Measured palette gaps

[Reproducible audit output](measurements/style-preset-audit-20261026.json) records
all current palettes and tick directions. With the current white background:

| Color | Contrast against white |
| --- | ---: |
| Yellow `#F0E442` | approximately 1.32:1 |
| Orange `#E69F00` | approximately 2.25:1 |
| Sky blue `#56B4E9` | approximately 2.31:1 |
| Monochrome gray `#A0A0A0` | approximately 2.61:1 |

These colors are below 3:1 as standalone marks on white. This observation is not
a blanket verdict on complete figures: borders, redundant labels or equivalent
information can change the assessment. It does establish that choosing a named
palette alone is insufficient to guarantee accessible thin lines. The audit
also does not simulate protanopia, deuteranopia or tritanopia.

## Profile architecture

Keep a reusable token, but resolve it from independent choices:

1. **Target:** a verified publication target or a screen task profile. Store
   source URL, checked date, explicit requirements, recommendations and our own
   design choices separately. Specify final print dimensions without treating
   window size as publication size.
2. **Surface and density:** light/dark, device/viewing distance, compact versus
   comfortable typography and spacing. Derive tick density from available space
   when the axis is Auto; retain explicitly fixed ticks and data domains.
3. **Color encoding:** categorical identity, sequential magnitude, diverging
   deviation with an explicit reference, semantic status, or a focus/comparison
   relationship. Semantic roles and divergence reference values come from the
   caller; do not infer thresholds, success direction or physical units.
4. **Bindings:** stable category/series roles across views. Reordering a series
   must not recolor the same entity in another panel. Exceeding a categorical
   palette's supported distinct count must not silently recycle colors; use
   additional encodings, require grouping, or report the limitation.
5. **Validation:** final-size font/line checks, contrast and CVD checks, grayscale
   discrimination, legend occlusion, clipping and dense-label tests on actual
   renders. Record unsupported export or renderer capabilities explicitly.

The token still applies appearance by default. Coordinate ranges, normalization
and wording remain opt-in. A profile does not manufacture KPIs, alert rules,
filter behavior or domain-specific values.

## Dashboard task profiles

This is a product taxonomy derived from the sources, not a universal standard.

| Profile | Question and visual priorities |
| --- | --- |
| `dashboard.executive` | Is performance on target? Sparse overview, strong KPI hierarchy, comparison context, consistent category identity. |
| `dashboard.operations` | What needs action now? Live trends, explicit units, stable resource/service colors, status reserved for supplied warning/critical roles. |
| `dashboard.analysis` | Why did a metric change? Multiple comparison views, detail and uncertainty, stable roles under filtering and selection. |
| `dashboard.instrument` | What is the measurement doing? Quantitative axes, units, linear/log control, dense signals, measurement/reference distinction. |
| `dashboard.public` | What should a broad audience understand? Plain structure, accessible labels and redundant encodings, useful static/exported views. |
| `dashboard.wallboard` | Can a distant viewer read the state? Larger marks and text, few panels, minimal precision, no reliance on hover. |
| `dashboard.mobile` | What matters on a small touch screen? Low density, clear hierarchy and reduced visual clutter. Responsive navigation belongs to the host, not the chart token. |

Dark appearance can be combined with several of these profiles; it does not
identify the task. Publication targets likewise need a specific journal and
output context, not the generic name `paper`.

## Validation scope

Use different realistic scenes: publication-sized figures,
color-mapped scalar fields, category comparisons, error bars, operational
latency/error panels, dense instruments and a wallboard. Rendering the same five
curves six times verifies visual differences but does not validate all use cases.
The gallery now covers these scenes through declared built-ins. Automated tests
cover native and notebook model inheritance, explicit/default-equal arguments,
existing-edit preservation, nested scopes and failure atomicity. Maintain
data/text/domain preservation checks alongside these visual and
source-based checks. A journal-inspired profile must not be labeled fully
compliant while required editable/vector output remains unsupported.
Final pixel/CVD inspection, long-label stress, responsive UI behavior and real
viewing-distance acceptance remain task-specific work, not established by the
token/model tests.
