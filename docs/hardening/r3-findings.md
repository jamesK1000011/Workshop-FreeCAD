<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Window review round 3: Workshop findings and fixes

Source: the round 3 window review (Workshop section: pictures 1009-7041)
and the faults listed with it. Worked from the code and FreeCAD 1.1.3's
source; no FreeCAD here, so each item has a live check.

## 1. dfm_check, part_review, slice, slice_with, fea_frame keep an earlier caption

**Cause (fairly sure).** All five are `heavy: true` reads
(`workshop_make/data/tools.json`), so Agent Link runs them as jobs
(`agentlink/jobs.py wanted()`). Every stale caption in the review (here and
in Texturizer) is a heavy read; the reads that are not heavy (`cut_check`,
`mill_check`, `thread_lookup`, `hw_pauses`) got their own words. Two of
them (`dfm_check`, `part_review`) are even in `SHOWN`, whose words come
before the call: so the echo did not run for these calls at all, which
points at the job path in the hub. Second cause, Workshop's own: no
`PHRASES`, so even when the words come they are the tool's name ("Dfm
check on Bracket"), and `dfm_check`'s answer had no verdict to show.

**Change.**

- `workshop_make/api.py dfm()`: `verdict` ("printable", "printable, 2
  warnings", "not printable: 1 problem, 1 warning", from the findings not
  waived; `dfm_verdict`). Description: the fact added.
- `PHRASES` (Agent Link's activity templates, filled from the arguments and
  the answer): `fam_make.py` dfm_check ("Checked {body} for printing:
  {verdict}"), part_review ("Reviewed {body}: {verdict}"), slice ("Sliced
  {body} with {slicer}: {time}, {filamentG} g"); `fam_slicing.py`
  slice_with, slicer_presets; `fam_frame.py` fea_frame ("Solved the frame
  under {loadTotalN} N: least safe member {worst}").
- `SELECTS` (`fam_make.py`, `fam_slicing.py`): the answer key of what a
  read checked or sliced (`body`).
- Tests: `tests/make/test_echo_words.py` (fills the templates with Agent
  Link's own `activity.did` when its checkout is at hand).

**Hub side (not here).** (1) Words, selection and result for a read run as
a job: when its answer comes back in the call, and at `job_status` for one
that ends later (`job_status` is `WATCH`, which keeps the earlier caption).
(2) `echo.declare` reads `SELECTS`; `_read_shown` selects
`body[SELECTS[name]]`, a Part Design body included for these checks (today
it skips `PartDesign::Body`).

**Live check.** `dfm_check { body: "Bracket" }` then `session_state`: the
echo trace has `words: "Checked Bracket for printing: printable…"`. If the
trace is still the earlier call's, the hub's job path is confirmed as the
cause. Same for `slice_with { body: "Bracket", slicer: "orcaslicer",
project: true }`.

## 2. mill_export leaves every part hidden and only a wireframe stock box

**Cause (sure, from FreeCAD's source).** `camjob.sanity_report` runs CAM's
Sanity report. With the window up its `GuiImageBuilder`
(`src/Mod/CAM/Path/Main/Sanity/ImageBuilder.py`) calls
`record_visibility()` before EACH picture: it records what is shown, then
sets `Visibility = False` on every object of the document, and shows only
the picture's object. Its `restore_visibility()` runs only in `__del__`
and only for the LAST record — taken when everything was already hidden
but the previous picture's object. So the parts stay hidden and the
stock (drawn by `Path/Main/Stock.py SetupStockObject` as a 90 %
transparent wireframe) stays shown. Also `camjob.make_job` replaced the
Job's stock with `PathStock.CreateBox`, which is shown, where CAM's own
`setupStock` hides its stock.

**Change.**

- `workshop_make/camjob.py`: `visibility(doc)`, `restore_visibility(doc,
  before)`, `hide_new_shapes(doc, had, keep)`. `make_job` hides the new
  shaped objects (the box stock, the tool bit's model), the Job kept.
  `sanity_report` lets the Sanity object go (`del`, `gc.collect()`) before
  it returns, so CAM's own `__del__` restore runs before Make's.
- `workshop_make/handlers/mill.py mill_export`: records every object's
  Visibility before CAM runs and puts it back after the report (in a
  `finally`), hides what the report left shown of the new Job, and settles
  what CAM made (`settle_new`) after the report too. `camJob.shownAgain`:
  how many objects were put back (only when any).
- Description: facts added. Test: `tests/make/test_camjob.py
  SanityLeavesTheViewAsItWas` (CAM's builder stood in as FreeCAD 1.1 has
  it).

**How sure.** Sure of CAM's behaviour from its source; the fix is tested
with a stand-in only.

**Live check.** `mill_export { body: "Block", name: "block-mill" }` →
answer `camJob.shownAgain` > 0 (on a document with other parts); then
`object_list {}` / `view_snapshot`: Block and the brackets shown, the Job's
Stock hidden; `session_state` health has no `needRecompute`.

## 3. gen_make shows an empty view; gen_part's baseplate does not show

**What the code does.** `workshop_parts/api.py make()` adds each piece as a
top-level `Part::Feature` with its Shape set and recomputes: shown by
default, in the tree. Nothing in Parts hides it or makes another document
active. The answer names the made bodies under `bodies`, a key Agent
Link's echo does not read (`echo.OUT_KEYS`), so the echo frames "what is
new in the document" (`Echo._new_objects`), which needs the agent's
document to be the one in front before and after the call; if it is not,
`Echo._after` only writes the words (`FreeCAD.ActiveDocument.Name !=
doc.Name` branch): no selection, no fit. Both pictures match that branch
(words, nothing selected, view not framed), but 4006 `body_check` right
after selected the bin, so the document was in front then.

**Change.** `workshop_parts/fam_parts.py`: `OUT_MORE = {"gen_make":
("bodies",), "gen_part": ("bodies",)}` for the echo to merge into its
`OUT_MORE`.

**How sure.** Not settled: the parts are made shown and in the tree; why
the echo did not frame them needs the trace.

**Hub side.** `echo.declare` merges a family's `OUT_MORE`.

**Live check.** `doc_new { name: "PartsModel" }`, `gen_make { params: {
x: 2, y: 1, z: 4 } }`, then `session_state`: the echo trace's `made`,
`madeFrom`, `selected`, `fit` (or `namedError` / `newObjectsError` /
`afterError`); `object_get { object: "<the label in bodies>" }`
(Visibility true). Then `gen_part { generator: "gridfinity_baseplate" }`,
`session_state` again.

## 4. After fastener_set { length: 20 } the screw sits below the body

**What the code does.** `workshop_fasteners/api.py change()` sets only
`Length` (`_set_length`, the nearest standard length when the length is a
list), recomputes, then `keep.adopt()` re-reads the anchor from
`BaseObject` and relabels (`Label` is an Output property: no touch, no
move). Placement is never written by Workshop on this path; Fasteners'
own `execute` places an attached screw on its `BaseObject` edge. The model
(`docs/hardening/workshop-fasteners-model.json`) expects only "changed[0]
length 20, the same object name; label M6x20-Screw". With a 10 mm body and
the head on the top edge, an M6x20's shank stands 10 mm out of the bottom
(the M6x16 stood 6 mm out); without see-through the picture may show the
shank below the body as "the screw below it".

**Change.** None to the placement (no tool fault found in Workshop's code).

**How sure.** Not settled.

**Live check.** Before and after `fastener_set { objects:
["M6x16-Screw"], length: 20 }`: `object_get { object: "M6x16-Screw" }`
and the answer's `changed[0]` — `attachedTo` ("Bracket.EdgeN"), `hole`
("kept"), `invert`, `offset`, and the object's `Placement.Base`. The head
should be at z = 10 (the top face) both times with Invert false. If
`Placement.Base.z` drops by the length change or `attachedTo` is gone, it
is Fasteners' execute (report it with those numbers); if `hole` is
"reattached" or "lost", it is `keep.check`.

## 5. mill_export and fastener_set leave objects touched

**Change.** `fastener_set`: `api.settle(doc, objs, was)` recomputes once
more when a fastener the call changed is touched after its last step and
was not before (test `tests/fasteners/test_settle.py`; description fact
added). `mill_export`: `camjob.settle_new` now runs after the Sanity report
as well as after making the Job (new objects left touched get one more
recompute).

**How sure.** Medium: what touches them was not found in the code (Label
and Visibility are Output properties; the record property is Output);
these recompute what the call itself changed or made.

**Live check.** `fastener_set { objects: ["M3x10-Screw"], label: "Spare
screw" }` and `mill_export { body: "Block", name: "block-mill-2" }`, each
followed by `recompute {}` — its answer (or the next call's health) lists
nothing as not recomputed yet. If something is still listed, `object_get
{ object: <it> }` and `doc_graph` show which.

## 6. drawing_make and patent_figures about 5 times slower

**Cause (likely, from code).** Added in 18489e6 and d35cd81:
`td_wait.PageExport.settle()` (`workshop_documents/td_wait.py:343-428`)
runs after the page's export. TechDraw's PDF export ends with
`DrawPage::redrawCommand`, which recomputes every part view and so restarts
each view's hidden-line work on another thread. `settle` then waits until
every dimension on such a view is seen recomputed again inside a turn this
module ran (`unseen()`, lines 387-394), turning the event loop
(`FreeCADGui.updateGui()`, every 20 ms) up to `_settle_timeout` =
max(5 s, 4 × viewsReadyIn + 2 s) (`handlers/drawing.py:400-409`).
TechDraw recomputes the dimensions after the hidden lines only when the
view does not extract faces (`DrawViewPart::postHlrTasks`,
`src/Mod/TechDraw/App/DrawViewPart.cpp:463-467`), else after face
extraction (`postFaceExtractionTasks`, 488-492): so the wait is a second
full hidden-line and face pass of every view, and a dimension whose late
recompute is not seen in one of this module's turns keeps it to the
timeout, at least 5 s — which matches 0.8 s becoming 4.6 to 5.7 s.
Patent pages carry balloons, not dimensions, so their wait loop does not
run; their extra time would be the turns (`page_scene_ready`, 4 turns, 8
for a second export; 3 more `QUIET_TURNS` after any restarted view), per
figure.

**Change.** None (the live timing decides between the two).

**Live check.** `drawing_make { bodies: ["Bracket"], file: "probe" }`:
read `timing` { page, export { wait, scene, svg, check, pdf }, settle,
turns, turnMs, total } and `page.settled` { waited, turns, turnMs, seen,
late }. `settle` near 5000 with `late` set = the timeout floor; `settle`
near `page.viewsReadyIn` = the second hidden-line pass. `patent_figures {
bodies: ["Bracket"], views: ["front"] }`: `timing` per call.

**Proposal.** Do not wait in the call: after the export, leave a one-shot
document observer that takes the mark off a dimension when TechDraw's late
recompute arrives (only TechDraw's own writes, as now) and removes itself
after the timeout; the call returns right after the export.

## 7. slicer_presets list: about 10 000 characters a call

**Cause.** `handlers/slicing.py` returned orcalink's `listing` as it is:
up to 60 names of each kind, and `from` (the four preset folders) and
`next` on every call. orcalink marks a person's preset `own: true` only in
its row object; nothing said how many there are.

**Change.** Each kind is `{ count, own, presets, more }`: the person's own
in full (`{ name, own: true }`), then the first `limit` other names as
plain strings (10 when neither kind nor query is given, else 50; `limit`
0-500), `more` when some are not shown. Every match is read from orcalink
(`limit` above 500) so `count` and `more` are whole; an orcalink without
its `limit` argument gives its own first 60 a kind. `from` and `next` come
on the first list of each slicer in a session and when the folders change,
else `saidBefore: ["from", "next"]`. `limit` in the schema; description
updated (facts added). Test: `tests/make/test_presets_list.py` (the first
list of 3 kinds of 70-90 names is under 2 500 characters).

**Live check.** `slicer_presets {}` twice: the second has no `from`;
`slicer_presets { kind: "filament", query: "pla", limit: 500 }` shows every
match; `own` counts the person's own presets.

# Second round: window review round 4

Source: the round 4 window review (Workshop pictures 1009-7041). A
picture's number is its section and its call's place in that section's
model (`docs/hardening/workshop-*-model.json`, `calls`, from 0): 5015 is
the fasteners model's call 15, 4001 the parts model's call 1. Worked from
the code, FreeCAD 1.1.3's source and Fasteners Workbench's source (read
only); no FreeCAD here.

## 8. fastener_set leaves the screw outside the body (5015, 6002)

**What the code does.** Fasteners places a part on its edge in every
recompute (`FastenersCmd.FSScrewObject.execute` →
`FastenerBase.FSMoveToObject(fp, edge, Invert, Offset, OffsetAngle)`): the
part's +Z (its head side; the shank runs to -Z) is turned onto the edge
circle's `Curve.Axis`, `Invert` turns it round, `Offset` moves it along
that way, and the placement is the circle's centre. Nothing else decides
the side. `fastener_set { length }` only sets Length; the placement comes
out of the same execute on the same edge, so a length change alone cannot
move the screw off its hole (the keeper re-finds an edge only within the
hole's radius, never the far rim 10 mm away).

Two things can put the screw "outside":

1. `fastener_add` never chose the side. The circle's axis of a hole's rim
   is OpenCASCADE's choice (a PartDesign Hole's revolved profile); when it
   points into the plate, Fasteners puts the head into the plate and the
   shank 16 mm up out of the top face. `hw_hole { screw }` always corrected
   this (`api.hole_screw`: Invert from the hole's direction);
   `fastener_add` with `edges` did not. Sure from the code; whether the
   Bracket's rim points down in FreeCAD 1.1.3 is for the probe.
2. The model itself asks for it: `fastener_set { length: 20 }` on an M6
   in a 10 mm plate leaves 10 mm of shank out of the bottom face (it was 6
   with 16), which reads as "the screw below the body" in a picture from
   above when the plate is not see-through.

**Change.** `workshop_fasteners/api.py`: `seat(obj, sub)` tells the open
side of a round edge from the shape (`isInside` just past the rim, a
little along either way of the axis): +1 along the circle's axis, -1
against it, 0 when it cannot tell. `seated_invert()`: Fasteners' Invert
for the head on the open side. `fastener_add` seats every part it attaches
(invert: turned end for end from seated); `fastener_set { edge }` seats it
on the new edge (keeping a turn it had); `fastener_set { invert }` is from
seated. `hole_screw` sets Invert either way from the hole's direction (it
only ever set it true). `describe()` adds `headSide` ("open side" | "in
the material") and `shankOut` (mm out of the hole's far rim). Tool data:
facts added. Tests: `tests/fasteners/test_seat.py` (a plate whose rim
circle points into it; a stand-in for Fasteners' execute that places as
FSMoveToObject does).

**Probe (exact).** In the fasteners model, after call 11 (`fastener_add`)
and again after call 15 (`fastener_set { objects: ["M6x16-Screw"], length:
20 }`):

1. `object_get { object: "M6x16-Screw" }` (after 15: `"M6x20-Screw"`):
   `Placement.Base` and `Placement.Rotation`, `BaseObject`, `Invert`.
2. The answer's `made[0]` / `changed[0]`: `attachedTo`, `headSide`,
   `shankOut`, `invert`, `at`.
3. `shape_query { body: "Bracket", kind: "edge", radius: 3.3 }`: the
   round edges of the hole, each with its centre and axis — the one named
   in `attachedTo` and its axis direction (+z or -z).

Read: `at` z 10 with `headSide` "open side" and `shankOut` 6 (then 10) is
right — the picture shows the 20 mm screw's shank out of the bottom, as
the model asks; make the plate see-through or set length 10 to see it
seated. `at` z 0 means the bottom rim was taken (report `attachedTo` with
the edge's centre). `headSide` "in the material" after this change means
`seat()` read the shape wrong (report the edge's axis and the Bracket's
`Shape.isInside` at [13.5, 20, 10.2] and [13.5, 20, 9.8]).

## 9. gen_make shows an empty view; gen_part shows the old Bin (4001, 4007)

**Settled (from the model).** 4001 is the parts model's call 1,
`gen_make { …, measure: true }`, and 4007 its call 7, `gen_part {
generator: "gridfinity_baseplate", …, measure: true }`: both build the part
only to answer its sizes and add nothing (`api.make`: `made: false`). The
empty view of the new document (4001) and the Bin made by call 2 (4007)
are what the window should show. Nothing is made in another document,
hidden or left unrecomputed (`make()` adds shown `Part::Feature`s to the
session's document and recomputes).

**Change.** Words that say so: `api.make` answers `kind` ("Gridfinity
bin") and `measured` ("83.5 x 41.5 x 32.4 mm", ", and a lid");
`fam_parts.PHRASES`: "Measured a Gridfinity bin, 83.5 x 41.5 x 32.4 mm:
nothing made" for measure, "Made Bin, a Gridfinity bin of …" for a made
part. `OUT_MORE` (bodies) stays. Test: `tests/parts/test_echo_words.py`.

**Live check.** Parts model calls 1 and 2: `session_state` echo words
"Measured a Gridfinity bin, …: nothing made", then "Made Bin, …" with
`made` ["Bin"] in the trace and Bin selected.

## 10. Stale captions on dfm_check, part_review, slice, slice_with, fea_frame

**Cause.** As item 1: heavy reads run as Agent Link's jobs; the hub is
adding words for job results and reading `SELECTS` / `OUT_MORE`.

**Change.** Declarations under the hub's names: `SELECTS` = {tool: the
answer's key of what it worked on} (a name, or a list of names):
`fam_make` dfm_check / part_review / slice → body, `fam_slicing`
slice_with → body, `fam_frame` fea_frame → bodies (new: the labels of
the bodies a frame was made from). `OUT_MORE` = {tool: (answer keys,)}:
`fam_parts` gen_make / gen_part → bodies. Each read answers a short
`verdict` (40 characters at most, Agent Link's result reads it):
dfm_check and part_review had theirs; slice and slice_with now "12m 3s,
3.21 g" (`api.slice_verdict`), fea_frame "least safety 2.4, Rafter"
(`api.frame_verdict`) with `loadN` (the load as one number: `loadTotalN`
is a vector and read as "0, 0 and -500"). `PHRASES` use them and have
words for a job's first answer ({ job, tool, status }): "Checking Bracket
for printing in the background", "Slicing …", "Solving the frame …".
Tool data: facts added. Tests: `tests/make/test_echo_words.py`.

**Live check.** `dfm_check { body: "Bracket" }`, `session_state`: words
"Checked Bracket for printing: printable…" (or "Checking … in the
background" then, at `job_status`, the result). `fea_frame` from bodies:
words "Solved the frame of … under … N: least safety …", the bodies
selected.
