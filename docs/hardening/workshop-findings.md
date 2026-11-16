# Workshop-FreeCAD hardening pass: findings

Checkout: Workshop-FreeCAD at 1380d50. Nothing here ran on FreeCAD (it is not installed where this
pass ran): every fix was made by reading FreeCAD's source (tag 1.1.0; the Mac runs 1.1.3), the wiki
mirror and this add-on's own code. The plain-Python tests ran; the FreeCAD tests added are unrun.

Changes to the brief, by the owner's ruling of 16 Nov 2026: no length budget on descriptions (the
1500-character cap in tests/make/test_api.py is replaced by a floor), and each tools.json entry
carries the optional fields "workbench" (the FreeCAD workbench class) and "commands" (the commands
the tool does the work of). The copy of Agent Link read here (228d9fc) still refuses unknown
fields in agentlink/tooldata.py (check(): "unknown fields"), so these entries load only once the
format agent's change lands: "workbench" is a string, "commands" a list of strings (left out when
there is none). If the format takes another shape they are quick to change: the two fields are the
last keys of each entry. Parts' two tools are defined in code (workshop_parts/fam_parts.py, Tool(…)),
not in a tools.json, so they carry no such fields; their family module's WORKBENCHES and COMMANDS
say the same.

"commands" holds FreeCAD's own commands checked in the wiki mirror or source (PartDesign_Hole,
PartDesign_Pocket, Part_CheckGeometry, Std_SetMaterial, CAM_Job, CAM_Sanity, Arch_Nest,
FEM_SolverCalculixCxxtools, FEM_ElementGeometry1D, the TechDraw ones) and this add-on's own
commands checked in its commands.py (Workshop_Make_…, Workshop_Documents_…). BIM's nesting command
is Arch_Nest in 1.1 (FreeCAD 1.1 source: src/Mod/BIM/bimcommands/BimPanel.py), not BIM_Nest.

## The one bug that runs through several tools: a shape written into a parametric object is lost

Proven from source. Part::Feature::Shape is an ordinary property (FreeCAD 1.1 source:
src/Mod/Part/App/PartFeature.cpp, ADD_PROPERTY(Shape …), no Output flag), so `o.Shape = cut`
touches the object (src/App/DocumentObject.cpp, onChanged), and the `doc.recompute()` that follows
runs its execute(): a PartDesign Body takes its tip's shape again (src/Mod/PartDesign/App/Body.cpp,
Body::execute: Shape.setValue(tipShape)), a Part::Box, a boolean or an extrusion its own. Only a
plain Part::Feature keeps what was written. Before this pass hw_hole (the "Part solid" route),
thread_cut, hw_embed, hw_unembed, mass_ballast { cut: true }, and in Electronics printed_channel,
all did `o.Shape = …` on whatever session.body() gave: on a Body or a part_primitive box the reply
said the cut was made (removed, step, sound) and the model was unchanged, with the record (thread,
embed, ballast) kept. The add-on's FreeCAD tests only ever used Part::Feature bodies, so none
caught it.

Fixed: geo.rebuilt(o, what) in workshop_make/geo.py (and its twin in workshop_electronics/geo.py)
says when a written shape would not stay, and each of those tools refuses up front (invalid_state)
with the next step: part_transform { body, op: "move", by: [0, 0, 0], copy: true, name } makes a
plain copy; hw_hole and thread_cut also name pd_clone. thread_cut does more: in a PartDesign Body
it now leaves a real PartDesign::Hole (Threaded) on a sketch in the Body, as hw_hole always did.
Wish (not done: a new feature): hw_embed and mass_ballast in a PartDesign Body as real Pockets.

## Make (33 tools: all checked, all descriptions rewritten)

| tool | checked against | fixed | still doubtful / needs a live check | description |
|---|---|---|---|---|
| fit | workshop_make/api.py, fits.py, data/fits.json | — | calibrate writes a record though the tool is `changes: false` (no undo step, not shown as a change). The format's `reads` could mark size and stack as reads of a changing tool; left for the owner. | rewritten |
| hw_hole | FreeCAD 1.1 source: src/Mod/PartDesign/App/FeatureHole.cpp (enums, onChanged, updateHoleCutParams, updateDiameterParam, execute, addCutType), Resources/Hole/*.json; PartDesign_Hole.md | (1) parametric Part objects refused instead of losing the hole (above). (2) pick_cut takes "ISO 4762" by its exact name before "ISO 4762 + 7089": FreeCAD lists the cuts in the order it read their files, and the washer variant has a wider counterbore. | Property names, enum values (ThreadType None/ISOMetricProfile, ThreadFit Medium/Fine/Coarse, DepthType, DrillPoint, HoleCutType) all match 1.1.0. The 0.2 mm allowance is added when no calibration is kept, also to a body in a cut or mill setup (a machined hole is not printed small): by design? New Holes in 1.1 take BaseProfileType from the user's preference (points, circles and arcs): a HoleSketch has one circle, fine. | rewritten |
| thread_lookup | threads.py (read_freecad reads ThreadDiameter and Diameter off a scratch Hole), FeatureHole.cpp threadDescription | — | ThreadDiameter following ThreadSize on an unattached Hole is taken on trust (the tests' stand-in table matches the source rows for M3, M6). | rewritten |
| thread_identify | handlers/thread.py, Part.Cylinder surface reading | — | — | rewritten |
| thread_cut | FeatureHole.cpp (Threaded, ModelThread, ThreadDepthType "Hole Depth", UseCustomThreadClearance, guessNormalDirection, the cut that removes nothing), Body.cpp | In a PartDesign Body the thread is a kept PartDesign::Hole feature (route "PartDesign Hole", features); it was written into Body.Shape and lost at the recompute. Parametric Part objects refused. New FreeCAD tests: tests/make/test_thread.py test_5, test_6 (a moved Body), test_7. | RISKIEST change in Make: the Body route is new code, unrun. To check live: the sketch's placement in a Body that sits in an App::Part; a hole picked on a feature rather than the Body; undo. | rewritten |
| hw_embed | handlers/embed.py, embeds.py | Parametric objects and Bodies refused (above); a size without insert figures is a refusal, not a crash. Test: tests/make/test_embed.py test_5. | — | rewritten |
| hw_embed_list | handlers/embed.py | — | It drops dead records (a write) though listed as a read. | rewritten |
| hw_unembed | handlers/embed.py | Same guard on the fill. | — | rewritten |
| hw_pauses | handlers/embed.py | A bad layer height in the setup is a refusal naming setup set, not a crash. | mass_ballast's pockets are not in its list (the description now says so). | rewritten |
| setup | records.py, api.py | — | Bodies are kept by Label: a rename drops the body out of its setup silently. Make's new health reading says so after the next changing call. | rewritten |
| part_spec | api.py spec_set, fcmaterials.py (Std_SetMaterial.md) | The refusal for a wrong key lists all five limits (it named three; minSafety and minClearance were accepted and never said). | minClearance is accepted and nothing reads it. | rewritten |
| dfm_check | printability.py, Part_CheckGeometry.md | — | waive writes a record from a heavy read (it may run as a job): no undo step. | rewritten |
| part_review | handlers/make.py | — | Same for waive. `spec` in the schema lacks minSafety though the code judges it (schema left as it is: nothing is cut or added). | rewritten |
| slice | handlers/make.py; MeshPart.meshFromShape keywords (Shape, LinearDeflection, AngularDeflection, Relative) | — | Depends on Agent Link for OrcaSlicer (orcalink) and the slicers on the Mac. | rewritten |
| mass_calibrate | handlers/mass.py | — | — | rewritten |
| mass_properties | handlers/mass.py (Shape.MatrixOfInertia, CenterOfMass) | — | — | rewritten |
| mass_target | handlers/mass.py | mass 0 or under is a refusal (it divided by zero). | — | rewritten |
| mass_ballast | handlers/mass.py | cut: true refused on Bodies and parametric objects (above); the plan still works on any body. | The ballast record is kept in the session's meta only, not in the document: after a restart mass_properties no longer counts it. | rewritten |
| slicer_presets | handlers/slicing.py | — | `use` writes the setup though the tool is `changes: false`. | rewritten |
| slice_with | handlers/slicing.py | — | It reads only Make's filament record: a body whose FreeCAD material is a metal slices as PLA (slice refuses it). | rewritten |
| slice_read | handlers/slicing.py, threemf.py | — | — | rewritten |
| slice_open | handlers/slicing.py | — | — | rewritten |
| printer_add / printer_list / printer_status / printer_pause / printer_stop | handlers/printer.py, printers.py | — | Not run against a printer. | rewritten |
| printer_send | handlers/printer.py | Description only: it said "refused while the printer has a job"; that is checked only with start: true. | — | rewritten |
| cut_check | handlers/cut.py | — | — | rewritten |
| cut_export | handlers/cut.py, bimnest.py; FreeCAD 1.1 source: src/Mod/BIM/ArchNesting.py (Nester(container, shapes), ROTATIONS, run() → sheets of [hashCode, face], results) | — | ArchNesting matches. | rewritten |
| mill_check | handlers/mill.py | — | — | rewritten |
| mill_export | camjob.py; FreeCAD 1.1 source: src/Mod/CAM/Path/Main/Job.py (Create uses FreeCAD.ActiveDocument), Stock.py (CreateBox(job, extent, placement)), Sanity/Sanity.py (CAMSanity(job, output_file).get_output_report()) | The body's document is made the active one before the Job is made: Job.Create adds it to FreeCAD.ActiveDocument, which is another file when two are open. Test in tests/make/test_camjob.py. | — | rewritten |
| fea_frame | handlers/frame.py, frame.py | A member whose from or to is not [x, y, z] is a refusal (it was a KeyError). | workbench is given as FemWorkbench; it uses CalculiX directly, no FEM objects. | rewritten |

Other Make changes: tests/make/test_api.py no longer caps a description at 1500 characters.
README's tool table is regenerated from the descriptions (tools/gen_readme_tools.py, as its test asks).

### Health check: Make's reading (implemented)

workshop_make/services.py: health_reading(session, tool, changed), registered by
workshop_make/families.py with health.register("workshop_make", …) (families.py is loaded by Agent
Link only; services.py imports no Agent Link). After every changing call it reports, amber, with
the call that puts it right: a setup that names a body no longer in the document (deleted or
renamed); an encased part's record whose pocket is solid again in a body the call recomputed.
Plain-Python test: tests/make/test_services.py test_health_reading.

Wishes for the shared check (not done): Make keeps no record of the last slice, so it cannot say
"the G-code on disk is older than the body"; if slice kept { body, stats, gcode } as fea_solve
keeps its solve, the reading could say a sliced file is stale.

## Documents (5 tools: all checked, all descriptions rewritten)

| tool | checked against | fixed | still doubtful / needs a live check | description |
|---|---|---|---|---|
| drawing_make | FreeCAD 1.1 source: src/Mod/TechDraw/App/DrawPage.cpp (ProjectionType "First angle" / "Third angle"), DrawViewSection.cpp (BaseView, SectionNormal, SectionOrigin, SectionSymbol), DrawViewDimension.cpp and .pyi (Type DistanceX / DistanceY / Diameter / Radius, MeasureType Projected, References2D, getRawValue), DrawViewBalloon.cpp, ArrowPropEnum.cpp, AppTechDrawPy.cpp (writeDXFPage), Gui/AppTechDrawGuiPy.cpp (exportPageAsSvg, exportPageAsPdf); Basic_TechDraw_Tutorial.md | No code bug found: every property and enum it sets exists under that name in 1.1.0. The four plain-Python tests that failed at the checkout's HEAD (tests/documents/test_drawing_page_dims.py) were stale stand-ins: HEAD's commit reads each edge's FirstParameter / LastParameter and the stand-in edges had none. Brought up to date; 106 pass. | Every call adds a new page (the description now says to delete the old one). `e.LastParameter − e.FirstParameter` as the angle a view's edge covers holds for circles and arcs (radians); an ellipse or B-spline edge is passed over. Not a job, and it can wait 30 s a view. | rewritten: a new lead (what, inputs, traps, refusals, reply), then the whole of the former text under "Behaviour, in full", word for word: nothing cut |
| drawing_exploded | FreeCAD 1.1 source: src/Mod/Assembly/CommandCreateView.py (ExplodedView, ExplodedViewStep: References, MovementTransform, MoveType; the view's Group), UtilsAssembly.py (getViewGroup); Assembly_CreateView.md | It was `changes: false` though in an Assembly it adds an Exploded View, its moves and a TechDraw page: no undo step, no health check, and as a "read" Agent Link may send a slow one to a job. Now `changes: true`. | Every call adds another Exploded View and page. Not run in an Assembly here. | rewritten |
| patent_figures | drawing.py (_patent_page: blank template, DrawViewPart line-art properties, balloons with BubbleShape None and EndType None: both values exist) | Same: it adds a TechDraw page per figure and was `changes: false`. Now `changes: true` with `reads: { page: [false] }` (files only). | The reply's note speaks of pages also with page: false. | rewritten |
| patent_draft | drawing.py | — | It depends on the last patent_figures of the session (kept in the session, not the document). | rewritten |
| library_pack | handlers/share.py, libpack.py | — | ScanRuler's service route not run. | rewritten |

Documents' own runner (workshop_documents/runner.py) reads `changes` from the same file, so its
buttons now open an undo step for the two tools as well; it does not read `reads` (a page: false
call opens a transaction that stays empty).

### Health check: Documents' reading (implemented)

workshop_documents/td_wait.py: page_reading(session, tool, changed), registered by
workshop_documents/families.py as "workshop_documents". After a changing call: a drawing page with
no template (amber); a view whose Source is empty, its body deleted (red, with object_delete or
drawing_make again); a view the call recomputed, or whose source it recomputed, that TechDraw has
not drawn yet (amber: wait before td_export). At most 8 pages and 12 views asked a call.
Plain-Python test: tests/documents/test_drawing_views_ready.py HealthReading.

Wish for health.py (not edited): TechDraw dimensions whose References2D no longer name a vertex or
edge of their view after a model change are not red in FreeCAD's State flags; a shared reading of
"dimension measures 0 or its reference is gone" would catch drawings gone stale.

## Parts (2 tools: both checked, both descriptions rewritten)

| tool | checked against | fixed | still doubtful | description |
|---|---|---|---|---|
| gen_make | workshop_parts/api.py, gridfinity.py (Shape.optimalBoundingBox(useTriangulation, useShapeTolerance) exists in 1.1) | — | The geometry itself (lofted feet, lip) was not re-derived; the add-on's FreeCAD tests cover its sizes. | rewritten in fam_parts.py: each parameter now with its range, default and meaning, built from the generator's own table |
| gen_part | boxes.py, api.py | — | same | rewritten the same way |

No health reading wished for Parts: it makes plain solids, which the shared check already reads.

## Fasteners bridge (5 tools: all checked against the bridge's own code, all descriptions rewritten)

Fasteners Workbench's source is not among this pass's references (CI fetches it as fasteners-ref),
so what the bridge calls in it (screwMaker.GetAllDiams, GetAllLengths, FastenersCmd …) is NOT
verified here; tests/fasteners/ covers it where Fasteners is present.

| tool | checked against | fixed | still doubtful | description |
|---|---|---|---|---|
| fastener_types | workshop_fasteners/api.py types() | — | not verified against Fasteners' tables | rewritten |
| fastener_add | api.py add(), edge_near(), keep.py | — | — | rewritten |
| fastener_set | api.py change(), restore() | — | — | rewritten |
| fastener_list | api.py listing(), bom_sheet(), keep.sweep() | — | A plain listing re-attaches fasteners (keep.sweep) though the call is a read (`reads: { sheet: [false] }`): no undo step for that move. | rewritten |
| fastener_print | api.py print_settings() | — | It sets an application preference and recomputes every open document's threaded fasteners: history_undo does not take it back (the description says so). A call with no arguments only reads, yet runs as a changing call. | rewritten |

"commands" lists only the Fasteners commands that have a page in the wiki mirror
(Fasteners_ChangeParameters, Fasteners_Flip, Fasteners_Move, Fasteners_BOM, Fasteners_ScrewCalculator,
Fasteners_MatchTypeInner / Outer). The family module also names Fasteners_Search and
Fasteners_3dPrintSettings for its echo: not found in the mirror, left out.
Health reading wished for (not done): the keeper's "lost" state after a changing call (a screw
whose hole is gone) belongs in the shared check as a red line; keep.py already knows it
(keep.lost_note), it would be registered from workshop_fasteners/families.py.

## Electronics (4 tools: all checked, all descriptions rewritten)

| tool | checked against | fixed | still doubtful | description |
|---|---|---|---|---|
| kicad_import | handlers.py, kicad.py | A file that is no board, has no outline, or whose outline does not close raised ValueError out of the handler (no code, no message: an error, not a refusal). Now a refusal in the reader's words. FreeCAD test added. | Each import adds a new board and components. | rewritten |
| board_enclosure | handlers.py, enclosure.py | — | — | rewritten |
| pcb_order_package | handlers.py, pcb.py | — | DRC needs kicad-cli. | rewritten |
| printed_channel | handlers.py (Part.Wire.makePipeShell(shapes, makeSolid, isFrenet, transition)) | Refused on a PartDesign Body or a parametric Part object (the lost-shape bug above); awg is checked before anything is cut (it was refused after the channel was written). FreeCAD test added (test_5). | — | rewritten |

## Common (the workshop package)

No tools of its own (layout, placement of commands, material names, the Tutor lesson). Read:
workshop/agentlink_families.py (the one module Agent Link finds; it only joins the parts) and
workshop/tooldata.py. Nothing changed there. workshop/lessons/hole-for-hardware.lesson.json still
passes tests/test_lessons.py against the rewritten tools.json.

## What was not done, and what to prove live

- Nothing ran on FreeCAD. The FreeCAD tests added (tests/make/test_thread.py test_5–7,
  tests/make/test_embed.py test_5, tests/electronics/test_electronics.py test_5 and the bad-file
  case) are unrun.
- thread_cut's Body route is the one new code path of size: prove it first (workshop-make-model.json,
  the thread_cut call; then history_undo).
- The refusals for parametric bodies change what an agent sees on the commonest flow
  (part_primitive, then hw_hole): confirm on the Mac that a Part::Box really came back whole before
  (it must, by Part::Box::execute) and that part_transform { copy: true } gives a Part::Feature.
- `changes: true` on drawing_exploded and patent_figures: confirm the undo step takes the pages back.
- The "workbench" / "commands" fields need the format agent's change in Agent Link to load.
- Tools still listed as reads that write a record (no undo step): fit { calibrate },
  slicer_presets { use }, dfm_check { waive }, part_review { waive }, hw_embed_list and hw_pauses
  (dropping dead records). The format's `reads` could make fit and slicer_presets changing tools with
  their other actions as reads (it needs "default": "size" / "list" on action); waive cannot be said
  with `reads` (it is an argument present, not a value). Left for the owner.
- docs/make.md, docs/documents.md, docs/electronics.md keep their own hand-written tool tables with
  the old first sentences; README's generated table is current.
- FILES is unchanged: no file was added or removed.
- The models' refusal calls sometimes break a schema enum or leave out a required input on purpose;
  where Agent Link checks the schema first, the refusal's words are its own, not the handler's.
