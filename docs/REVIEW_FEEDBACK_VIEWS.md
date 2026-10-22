# Review feedback: summary and exact details

The opening SSOT checkpoint and the accepted submission are the comparison
boundary. Intermediate gestures are not a second change log. Returning to the
opening persistent state produces no edit. Selection and hover are excluded by
the existing persistent-settings contract.

The complete protocol-1 checkpoint remains available. Summary and detail views
are read-only projections of that checkpoint; they do not render, mutate the
source, revise the approval or replace exact retained-edit validation.

## Read the summary first

```sh
python -m figgyplot.review feedback CACHE WORK_ID --summary
```

`Session.feedback_summary(work_id)` provides the same JSON. It includes every
Figure's disposition, the batch lifecycle intent, source provenance, counts,
Figure-level comments and objects with changes or targeted comments. Unchanged
accepted Figures remain listed with empty object lists. Accepted Figures with
human edits still require source reconciliation.
`data_changed` compares complete cached source references, including data whose
axis bounds did not change; inspect the full checkpoint's references when true.

Each object has its stable editor/comment `target`, label, scope, property
summaries and separate comments. Native editor ownership provides its SSOT
bindings. Panel, secondary-axis, series and annotation addresses are resolved
against both snapshots; removed objects remain inspectable. A shared or
unclassified property remains at panel/Figure scope instead of being assigned to
an unrelated leaf object.

Rich text character/style operations are grouped into one property with
`text_changed` and `formatting_changed`. Identical displayed text does not imply
identical formatting. Every original operation ID remains in `operation_ids`.
Values and labels longer than 160 characters have an explicit truncation flag;
exact values remain in the detail snapshots and raw changes. Natural-language
comments remain separate instructions rather than annotation text or SSOT edits.

## Inspect the listed changes when needed

```sh
# All exact changes for one Figure, in their original order:
python -m figgyplot.review feedback CACHE WORK_ID --figure line

# One object, using the ID returned in its summary/details selector:
python -m figgyplot.review feedback CACHE WORK_ID --figure line --target panel/main/chart_title

# One original operation, scoped to its Figure:
python -m figgyplot.review feedback CACHE WORK_ID --figure line --change CHANGE_ID

# Original full checkpoint and protocol/schema discovery remain available:
python -m figgyplot.review feedback CACHE WORK_ID
python -m figgyplot.review protocol
```

Python callers use `Session.feedback_details(work_id, figure_id, target=None,
change_id=None)` with keyword filters. Details include the exact ordered
`changes`, comments, object summaries and their complete before/after SSOT roots.
`selection` records the filters. A change filter narrows the operation list;
object snapshots still describe the complete opening/submitted object.

`target` is the same address used by the editor and element comments. Raw diff
`object_id` remains unchanged for compatibility. Change IDs identify exact diff
operations and must be queried with their Figure ID; identical edits in separate
Figures can have identical operation hashes. Unknown Figures, objects without
feedback, unknown operation IDs and stale work IDs fail explicitly.

The bundled review skill starts with summary, requests relevant details before
reproducing truncated values or formatting, retains approved human edits, and
continues through the existing claim/regenerate/finish/subscription workflow.

## Validation

The two-Figure sample from the feedback audit produces 42,610 bytes of complete
feedback and about 1.8 KB of summary JSON.
The six exact character operations for `Before` to `AFTER!` become one summary
property and remain six identical operations in details. This is an example of
payload reduction, not a measurement of model or renderer execution speed.

Tests account for each `(figure_id, change_id)` exactly once, preserve original
operation order and values, and check source snapshots remain unchanged. Coverage
includes additions, removals, ordering, reverted edits, long text with differences
beyond the preview, formatting-only changes, stable panels/secondary axes/series,
all four bounded families, comments without edits, unchanged accepted Figures,
finish intent, scoped operation hashes, CLI filters and JSON Schema validation.
The real native/Jupyter comment regression also follows the UI's actual target
into summary and exact detail. Existing native text, history, review recovery,
property editing and typing checks remain applicable.
