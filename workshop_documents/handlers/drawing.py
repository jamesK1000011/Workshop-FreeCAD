# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Documents: the handlers of drawing_make, drawing_exploded,
# patent_figures and patent_draft (definitions in data/tools.json; moved from
# Agent Link for FreeCAD on 14 Nov 2026). No Agent Link import here.
# Drawings and documents from the bodies: a TechDraw page of standard views
# (TechDraw's template, title block, views and dimensions, editable there;
# exported as SVG, PDF and DXF by TechDraw where it can), an
# assembly manual with exploded steps and a bill of materials, and patent
# figures with reference numerals and a draft to start a patent attorney's
# work from. Where TechDraw cannot export (PDF and SVG with no window), the
# files are written by sheets.py from Open CASCADE's exact hidden-line
# removal (what TechDraw itself uses).

import datetime
import glob
import math
import os
import re

import FreeCAD
import TechDraw  # noqa: F401 — the family stands on TechDraw; left out without it

from workshop_documents import geo
from workshop_documents import iso286
from workshop_documents import sheets
from workshop_documents import records as store
from workshop_documents.td_wait import views_ready as _wait_views

from .. import fcexplode, views
from ._lent import Refusal

# Lent by the family layer when Agent Link binds these handlers (lend()); alone
# a refusal is this add-on's own and Agent Link's helpers are absent.
ToolError = Refusal
M = None  # Agent Link's measure family
picks = None  # Agent Link's picks family


def _settle(vs):
    """Every view's lines worked out before anything is placed on them or
    the page exported: {"seconds", "notReady"} as td_wait.views_ready (a
    stand-in that answers None: all ready at once)."""
    try:
        got = _wait_views(list(vs))
    except Exception as e:  # noqa: BLE001
        return {"seconds": 0.0, "notReady": [{"view": "?", "why": f"the wait failed: {type(e).__name__}: {e}"}]}
    if not isinstance(got, dict):
        return {"seconds": float(got or 0.0), "notReady": []}
    return got


def _part_views(page):
    return [v for v in (getattr(page, "Views", None) or []) if hasattr(v, "getVisibleEdges")]


V = FreeCAD.Vector
ORTHO = ("front", "back", "top", "bottom", "right", "left")


def _safe(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "drawing"


def material_shown(mid, doc=None):
    """A material id as its name (workshop.matname): never a UUID."""
    try:
        from workshop import matname

        return matname.shown(mid, doc)
    except Exception:  # noqa: BLE001
        return str(mid)


def _num(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


# TechDraw's own templates with a title block, best first. FreeCAD 1.1
# ships ISO 5457 ones (Templates/ISO/A3_Landscape_ISO5457_advanced.svg …)
# and its TD ones (A3_Landscape_TD.svg); older builds had ISO 7200 names.
# The blank one only when this build has none of them.
TITLED = {"A4": ("A4_Landscape_ISO5457_advanced.svg", "A4_Landscape_ISO5457_minimal.svg", "A4_Landscape_TD.svg",
                 "A4_Landscape_ISO7200TD.svg", "A4_LandscapeTD.svg", "A4_Landscape_ISO7200Pep.svg"),
          "A3": ("A3_Landscape_ISO5457_advanced.svg", "A3_Landscape_ISO5457_minimal.svg", "A3_Landscape_TD.svg",
                 "A3_Landscape_ISO7200TD.svg", "A3_LandscapeTD.svg", "A3_Landscape_ISO7200Pep.svg"),
          "A4P": ("A4_Portrait_ISO5457_advanced.svg", "A4_Portrait_ISO5457_minimal.svg", "A4_Portrait_TD.svg",
                  "A4_Portrait_ISO7200TD.svg", "A4_PortraitTD.svg")}
BLANK = {"A4": "A4_Landscape_blank.svg", "A3": "A3_Landscape_blank.svg", "A4P": "A4_Portrait_blank.svg"}
# Room the views leave at the foot of the sheet: TechDraw's title block,
# or the files' own smaller one.
TITLE_H = {True: 45.0, False: 18.0}
# The drawing area (left, top, right, bottom margins, mm) and the title
# block's (w, h) in its bottom right corner, by template family, measured
# on FreeCAD 1.1.3's: ISO 5457 (a 20 mm filing margin; the block with its
# material, tolerance and scale row and the projection symbol), TD.
ROOM = {"ISO5457": ((20.0, 10.0, 10.0, 10.0), (180.0, 62.0)), "TD": ((10.0, 10.0, 10.0, 10.0), (142.0, 50.0)),
        "ISO7200": ((20.0, 10.0, 10.0, 10.0), (180.0, 62.0)), None: ((10.0, 10.0, 10.0, 10.0), (130.0, 35.0))}
# Fields of TechDraw's templates that hold sample text ("A. Nemesis",
# "DN", "AAA"): emptied when nothing is given for them, never a made-up
# name. Their language, document type and status stay as the template has them.
KEEP_TEXT = ("LANGUAGE", "DOCUMENT_TYPE", "DOCUMENT_STATUS")


def template_room(path, paper):
    """(area rect (x0, y0, x1, y1), title block (w, h)) on the paper for a
    template file (None: the files' own sheet, frame 10 mm, their grid block)."""
    name = os.path.basename(path or "")
    fam = "ISO5457" if "ISO5457" in name and "notitleblock" not in name else ("ISO7200" if "ISO7200" in name else ("TD" if "TD" in name else None))
    (l, t, r, b), block = ROOM[fam]
    W, H = sheets.PAPER[paper]
    return (l, t, W - r, H - b), block


def _template(paper):
    """(TechDraw's template for the paper, whether it has a title block):
    TechDraw's own default template (its preferences) when it is this
    paper's, else its ISO 5457 one, else the other titled ones, else the
    blank one; (None, False) when this build keeps none. Localized copies
    (Templates/ISO/localized/…) are passed over for the plain ones."""
    base = os.path.join(FreeCAD.getResourceDir(), "Mod", "TechDraw", "Templates")
    try:
        pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/TechDraw/Files").GetString("TemplateFile", "")
    except Exception:  # noqa: BLE001
        pref = ""
    stem = {"A4": "A4_Landscape", "A3": "A3_Landscape", "A4P": "A4_Portrait"}[paper]
    low = os.path.basename(pref).lower()
    if pref and os.path.isfile(pref) and os.path.basename(pref).startswith(stem) and "blank" not in low and "notitleblock" not in low:
        return pref, True
    for local in (False, True):
        for want in TITLED[paper]:
            hits = sorted((h for h in glob.glob(os.path.join(base, "**", want), recursive=True) if ("localized" in h) == local), key=len)
            if hits:
                return hits[0], True
    hits = sorted(glob.glob(os.path.join(base, "**", BLANK[paper]), recursive=True), key=lambda h: ("localized" in h, len(h)))
    return (hits[0], False) if hits else (None, False)


# A title block field's name in TechDraw's templates (their EditableTexts
# keys differ between templates), matched by the words in it.
TEXT_KEYS = (
    ("title", ("DRAWING_TITLE", "FC-TITLE", "TITLE")),
    ("scale", ("SCALE", "FC-SC")),
    ("material", ("PART_MATERIAL", "MATERIAL")),
    ("partNumber", ("PART_NUMBER", "PARTNUMBER", "DRAWING_NUMBER", "PN", "DN")),
    ("revision", ("REVISION", "REV")),
    ("drawnBy", ("AUTHOR_NAME", "AUTHOR", "DRAWN", "CREATOR", "DESIGNED_BY")),
    ("checkedBy", ("CHECKED", "APPROVED", "APPROVAL")),
    ("date", ("DATE_OF_ISSUE", "FC-DATE", "DATE")),
    ("company", ("COMPANY", "LEGAL_OWNER_1", "OWNER", "ORGANISATION", "ORGANIZATION")),
    ("finish", ("FINISH", "SURFACE")),
    ("generalTolerance", ("GENERAL_TOLERANCES", "TOLERANCE", "GENERAL_TOL")),
    ("projection", ("PROJECTION",)),
    ("sheet", ("SHEET_NUMBER", "FC-SH", "SHEET")),
)


def template_texts(keys, fields):
    """{template key: text} for the title block fields given: each field to
    the first key that names it (whole name first, then a part of it), each
    key used once; keys no field names are left as the template has them."""
    keys = [str(k) for k in keys]
    out, used = {}, set()
    for field, words in TEXT_KEYS:
        v = fields.get(field)
        if v in (None, ""):
            continue
        hit = next((k for w in words for k in keys if k not in used and k.upper() == w), None)
        if hit is None:
            hit = next((k for w in words for k in keys if k not in used and len(w) > 3 and w in k.upper() and not (field == "title" and "SUB" in k.upper())), None)
        if hit is not None:
            out[hit] = str(v)
            used.add(hit)
    return out


def _bodies(s, refs):
    objs = [s.body(r) for r in refs] if refs else s.bodies()
    if not objs:
        raise ToolError("not_found", "No body in the document: make one first (gen_make, gen_part).")
    seen, out = set(), []
    for o in objs:
        if o.Label not in seen:
            seen.add(o.Label)
            out.append(o)
    return out


KINDS = ("pdf", "svg", "dxf")


def out_place(out_dir, file, name):
    """(folder, base name) the drawing's files are written as. file: an
    absolute path (~ too) is honoured — its folder made, its extension
    (.pdf, .svg, .dxf) dropped, so the other formats sit beside it with the
    same stem; a relative one with folders goes under the out folder; a bare
    name is the files' name. Without file, the drawing's name."""
    if not file:
        return out_dir, _safe(name)
    f = os.path.expanduser(str(file).strip())
    stem, ext = os.path.splitext(f)
    if ext.lower().lstrip(".") in KINDS:
        f = stem
    folder, leaf = os.path.split(f)
    if not leaf:
        raise ToolError("invalid_input", f"file: {file!r} names a folder — give the files' name too (…/Stem-drawing).")
    if not os.path.isabs(folder):
        folder = os.path.join(out_dir, folder) if folder else out_dir
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError as e:
        raise ToolError("invalid_input", f"file: the folder {folder} cannot be made here ({e.strerror or e}).")
    return folder, _safe(leaf)


def _write(s, base, sheet, kinds, folder=None):
    paths = {}
    for k in kinds:
        p = os.path.join(folder or s.out_dir, f"{base}.{k}")
        data = {"svg": sheet.svg, "pdf": sheet.pdf, "dxf": sheet.dxf}[k]()
        with open(p, "wb" if isinstance(data, bytes) else "w", **({} if isinstance(data, bytes) else {"encoding": "utf-8"})) as f:
            f.write(data)
        paths[k] = p
    return paths


def _techdraw_page(doc, objs, placed, scale, paper, label, dims, specs=(), drawn=None, section=None, fields=None, scales=None, boxes=None, projection="first", table=None,
                   extents=None):
    """The drawing: a TechDraw page on TechDraw's own template, its title
    block filled, the views, section and dimensions TechDraw's own, all
    editable in TechDraw. (page, what was made) or (None, why not)."""
    try:
        page = doc.addObject("TechDraw::DrawPage", "Page")
        page.Label = label
        tpl = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
        path, _titled = _template(paper)
        if path:
            tpl.Template = path
        page.Template = tpl
        try:
            page.ProjectionType = "Third angle" if projection == "third" else "First angle"
        except Exception:  # noqa: BLE001 — an older TechDraw
            pass
        filled, emptied = {}, []
        try:
            texts = dict(tpl.EditableTexts)
            filled = template_texts(texts, fields or {})
            texts.update(filled)
            if path and os.path.abspath(path).startswith(os.path.abspath(FreeCAD.getResourceDir())):
                # FreeCAD's own template: its sample texts ("A. Nemesis",
                # "DN", "AAA") emptied, never a name made up for them.
                for k in texts:
                    if k not in filled and not any(w in k.upper() for w in KEEP_TEXT) and texts[k]:
                        texts[k] = ""
                        emptied.append(k)
            if filled or emptied:
                tpl.EditableTexts = texts
        except Exception:  # noqa: BLE001 — a template without fields
            filled = {}
        H = sheets.PAPER[paper][1]
        made, dimmed = [], 0
        for view, (x, y) in placed:
            z, xd = views.VIEWS[view]
            v = doc.addObject("TechDraw::DrawViewPart", "View")
            page.addView(v)
            v.Label = view.capitalize()
            v.Source = objs
            v.Direction = V(*z)
            v.XDirection = V(*xd)
            v.ScaleType = "Custom"
            v.Scale = (scales or {}).get(view, scale)
            v.X = x
            v.Y = H - y
            made.append((view, v))
        doc.recompute()
        sec_note = {}
        if section and section.get("cutLineIn"):
            # The section view on the page: TechDraw's own, based on the view
            # that shows the cutting plane edge on, where the plain view was.
            try:
                base = dict(made)[section["cutLineIn"]]
                plain = dict(made)[section["view"]]
                z, xd = views.VIEWS[section["view"]]
                sv = doc.addObject("TechDraw::DrawViewSection", "Section")
                page.addView(sv)
                sv.BaseView = base
                sv.Source = objs
                sv.ScaleType = "Custom"
                sv.Scale = scale
                sv.SectionNormal = V(*z)
                sv.Direction = V(*z)
                sv.XDirection = V(*xd)
                sv.SectionOrigin = section["origin"]
                sv.SectionSymbol = section["label"].split("-")[0]
                sv.X, sv.Y = plain.X, plain.Y
                page.removeView(plain)
                doc.removeObject(plain.Name)
                made = [(n, v) for n, v in made if v is not plain] + [(section["view"], sv)]
                doc.recompute()
                sec_note = {"section": sv.Label}
            except Exception as e:
                sec_note = {"sectionNote": f"the section view could not go on the page here ({e}); the files have it"}
        # Every view's lines worked out (TechDraw's own thread) before a
        # dimension goes on them, however long it takes, and said so: the
        # wait once sat in a try that could skip it unnoticed.
        ready = _settle([v for _, v in made])
        extent_done, extent_missed = [], []
        if dims and boxes:
            # The overall sizes as TechDraw's own distance dimensions between
            # the two extreme vertices of the view's drawn geometry along
            # the axis, measured by TechDraw and checked against the part's
            # size; each outside its view: 10 mm under it or right of it
            # (7 more for a second on that side), its text off the lines.
            # (makeExtentDim with no edges read 0 on 1.1.3.)
            by = dict(made)
            for view, axis, pa, pb, off, mm in sheets.extent_dims(boxes, views.AXES, extents or {"x": 0, "y": 0, "z": 0}):
                v = by.get(view)
                if v is None:
                    continue
                horizontal = abs(pa[1] - pb[1]) < 1e-9
                bx = boxes[view]
                got = _extent_dim(doc, page, v, horizontal, mm)
                if got.get("dimension") is None:
                    extent_missed.append({"view": view, "type": "DistanceX" if horizontal else "DistanceY", "value": round(mm, 4), "why": got["why"]})
                    continue
                dim = got.pop("dim")
                try:
                    # X, Y: the text's place from the view's centre, on the page, y up.
                    if horizontal:
                        dim.X, dim.Y = 0.0, -((bx[3] - bx[1]) / 2 + off + 1.0)
                    else:
                        dim.X, dim.Y = (bx[2] - bx[0]) / 2 + off + 1.0, 0.0
                except Exception:  # noqa: BLE001
                    pass
                dimmed += 1
                extent_done.append({"view": view, "axis": axis, **got})
            doc.recompute()
        table_note = {}
        if table:
            # The holes no view sees end on, in a table on the page where
            # the files have it.
            try:
                ann = doc.addObject("TechDraw::DrawViewAnnotation", "HoleTable")
                page.addView(ann)
                ann.Text = ["  ".join(r) for r in table["rows"]]
                ann.TextSize = 3.0
                ann.X, ann.Y = table["at"][0] + 2, H - table["at"][1] - 2
                table_note = {"holeTable": ann.Label}
            except Exception as e:  # noqa: BLE001
                table_note = {"holeTableNote": f"the hole table could not go on the page here ({e}); the files have it"}
        out = {"views": len(made), "viewsReadyIn": ready["seconds"], **({"viewsNotReady": ready["notReady"]} if ready["notReady"] else {}),
               "extentDimensions": dimmed, "template": os.path.basename(path) if path else None, **sec_note, **table_note}
        if extent_done:
            out["extents"] = extent_done
        if extent_missed:
            out["notOnPage"] = list(extent_missed)
        if filled:
            out["titleBlock"] = sorted(filled)
        if emptied:
            out["titleBlockEmptied"] = sorted(emptied)
        if specs:
            # The dimensions and hole callouts on the page itself, each on
            # its own (one failing never drops the rest), added to what is
            # already listed as not on the page, never in place of it.
            again = _settle([v for _, v in made])
            if again["notReady"]:
                out["viewsNotReady"] = again["notReady"]
            try:
                done, missed = _page_dims(doc, page, made, drawn, specs, {vw: (x, y) for vw, (x, y) in placed}, H)
            except Exception as e:  # noqa: BLE001 — the page stands without them
                done, missed = [], [{**_brief(sp), "why": f"TechDraw could not take dimensions here: {type(e).__name__}: {e}"} for sp in specs]
            out["dimensions"] = done
            if missed:
                out["notOnPage"] = out.get("notOnPage", []) + missed
        return page, out
    except Exception as e:
        return None, f"the TechDraw page could not be made here ({e}); the files stand on their own"


def _export_page(page, out_dir, base, kinds=("dxf", "pdf", "svg"), report=None):
    """The page's own exports, as TechDraw's File ▸ Export does them: DXF
    always (TechDraw.writeDXFPage), PDF and SVG with the GUI up
    (TechDrawGui). ({kind: path}, {kind: why not}). Only once every view's
    lines are worked out (none exported otherwise), and the SVG checked to
    hold the views' lines, not only the template and dimensions: exported
    once more after a further wait when it does not, and neither SVG nor
    PDF kept from the page when it still does not. report (a dict) is
    filled with viewsReadyIn, viewsNotReady and viewsInExport."""
    paths, why = {}, {}
    report = {} if report is None else report
    pv = _part_views(page)
    ready = _settle(pv)
    report["viewsReadyIn"] = ready["seconds"]
    if ready["notReady"]:
        # Never a page whose views have no lines yet: its export held only
        # the frame and the dimensions floating on white.
        report["viewsNotReady"] = ready["notReady"]
        names = ", ".join(f"{x['view']} ({x['why']})" for x in ready["notReady"])
        for k in kinds:
            why[k] = f"TechDraw had not drawn every view yet ({names}); not exported from the page"
        return paths, why
    p = os.path.join(out_dir, f"{base}.dxf")
    if "dxf" in kinds:
        try:
            TechDraw.writeDXFPage(page, p)
            if os.path.isfile(p) and os.path.getsize(p) > 0:
                paths["dxf"] = p
            else:
                why["dxf"] = "TechDraw wrote nothing"
        except Exception as e:  # noqa: BLE001
            why["dxf"] = f"TechDraw could not write it ({e})"
    gui = getattr(FreeCAD, "GuiUp", False)
    if gui and any(k in kinds for k in ("pdf", "svg")):
        # TechDrawGui's exports draw the page's scene (the QGraphicsScene of
        # its tab), not the page object: shown, made the active tab, each
        # view asked to repaint and the event loop run before exporting.
        report["exportScene"] = page_scene_ready(page)
    for k, fn in (("svg", "exportPageAsSvg"), ("pdf", "exportPageAsPdf")):
        if k not in kinds:
            continue
        if not gui:
            why[k] = "TechDraw exports it with FreeCAD's window only"
            continue
        if k == "pdf" and why.get("svg", "").startswith(("TechDraw left the template out", "TechDraw's export held no view")):
            why[k] = why["svg"]
            continue
        p = os.path.join(out_dir, f"{base}.{k}")
        try:
            import TechDrawGui

            getattr(TechDrawGui, fn)(page, p)
            if k == "svg" and pv and os.path.isfile(p) and not views_in_svg(p, page, pv, report):
                # The views' lines missing from the scene the export draws:
                # wait for them again (the window redrawn) and export once more.
                again = _settle(pv)
                report["viewsReadyIn"] = round(report["viewsReadyIn"] + again["seconds"], 2)
                report["exportSceneAgain"] = page_scene_ready(page, turns=SCENE_TURNS * 2)
                getattr(TechDrawGui, fn)(page, p)
            if not (os.path.isfile(p) and os.path.getsize(p) > 0):
                why[k] = "TechDraw wrote nothing"
            elif k == "svg" and not template_in_svg(p, page):
                why[k] = "TechDraw left the template out of its export (no frame or title block in it)"
            elif k == "svg" and pv and not views_in_svg(p, page, pv, report):
                why[k] = ("TechDraw's export held no view geometry (only the template and dimensions), twice; "
                          "the page itself is fine: File ▸ Export it in FreeCAD's window")
            else:
                paths[k] = p
        except Exception as e:  # noqa: BLE001
            why[k] = f"TechDraw could not write it ({e})"
    return paths, why


SCENE_TURNS = 4


def _pump_gui():
    """One turn of FreeCAD's event loop (its window redrawn): False when
    there is none."""
    from workshop_documents import td_wait

    return td_wait._pump()


def _page_tab(page):
    """The page's tab in FreeCAD's window (its MDIViewPage), or None."""
    import FreeCADGui

    try:
        tabs = list(FreeCADGui.getDocument(page.Document.Name).mdiViewsOfType("TechDrawGui::MDIViewPage") or [])
    except Exception:  # noqa: BLE001
        tabs = []
    for m in tabs:
        try:
            got = m.getPage()
        except Exception:  # noqa: BLE001
            continue
        if got is page or getattr(got, "Name", None) == getattr(page, "Name", ""):
            return m
    return tabs[0] if len(tabs) == 1 else None


def page_scene_ready(page, turns=SCENE_TURNS):
    """Readies the scene TechDrawGui's SVG and PDF exports draw (1.1.3:
    the QGraphicsScene of the page's tab; a view's lines are put on it as
    graphics items only when its tab has been shown and the window has
    painted it, so a page whose tab was never shown, or sat behind
    another, exported the template and dimensions alone). In order: the
    page shown as a tab, that tab made the active one, every view and the
    page asked to repaint (requestPaint, no recompute: that would start
    the views' lines afresh) after one turn of the event loop has painted
    the tab, and the loop run `turns` more times. The steps done, in
    order, for the answer: [show, activate, paint, redraw, process]; a
    step that could not be done is left out."""
    done = []
    try:
        page.ViewObject.show()
        done.append("show")
    except Exception:  # noqa: BLE001
        pass
    try:
        tab = _page_tab(page)
        if tab is not None:
            import FreeCADGui

            FreeCADGui.getMainWindow().setActiveWindow(tab)
            done.append("activate")
    except Exception:  # noqa: BLE001
        pass
    if _pump_gui():
        # The tab's first paint: the views' graphics items made.
        done.append("paint")
    asked = 0
    for v in list(getattr(page, "Views", None) or []) + [page]:
        fn = getattr(v, "requestPaint", None)
        if callable(fn):
            try:
                fn()
                asked += 1
            except Exception:  # noqa: BLE001
                pass
    if asked:
        done.append("redraw")
    ran = 0
    for _ in range(max(1, int(turns))):
        if not _pump_gui():
            break
        ran += 1
    if ran:
        done.append("process")
    return done


DRAWN = re.compile(r"<(path|polyline|polygon|line|rect|circle|ellipse)\b")
_MARK = re.compile(r"<(path|polyline|polygon|line|rect|circle|ellipse)\b([^>]*)>", re.S)
_ATTR = re.compile(r"""\b(d|points)\s*=\s*("[^"]*"|'[^']*')""", re.S)
_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
# Points a shape element stands for once Qt draws it as a path: a rect's
# corners and close, a circle's or ellipse's four cubic quarters.
_SHAPE_POINTS = {"line": 2, "rect": 5, "circle": 13, "ellipse": 13}
# Points a dimension may draw: dimension line, two extension lines, two
# filled arrows, a little more for a diameter's or radius's leader.
DIM_POINTS = 40


def _svg_points(text):
    """The points an SVG draws: coordinate pairs in its paths' path data
    and its polylines' points, and a fixed count for each rect, line,
    circle and ellipse. TechDraw's SVG writes a view's lines of one style
    as a few <path> elements of many subpaths each, so the elements alone
    say little about how much is drawn; the points do, whatever the
    grouping."""
    pts = 0
    for m in _MARK.finditer(text):
        tag, attrs = m.group(1), m.group(2)
        a = _ATTR.search(attrs)
        if tag in ("path", "polyline", "polygon") and a:
            pts += len(_NUM.findall(a.group(2))) // 2
        else:
            pts += _SHAPE_POINTS.get(tag, 0)
    return pts


def _template_marks(page):
    try:
        with open(page.Template.Template, encoding="utf-8", errors="replace") as f:
            return len(DRAWN.findall(f.read()))
    except Exception:  # noqa: BLE001
        return 0


def _template_points(page):
    try:
        with open(page.Template.Template, encoding="utf-8", errors="replace") as f:
            return _svg_points(f.read())
    except Exception:  # noqa: BLE001
        return 0


def views_in_svg(path, page, part_views, report=None):
    """Whether TechDraw's SVG export holds the views' lines. TechDraw writes
    a view's visible and hidden lines as a few <path> elements of many
    subpaths each, so counting elements missed views that were there. Two
    tests, either enough: the points drawn (path data's coordinate pairs,
    polyline points, a fixed count per rect, line, circle, ellipse) beyond
    the template's own and an allowance per dimension (DIM_POINTS) number at
    least the views' visible edges (each edge draws two points or more); or
    the drawn elements beyond the template's and 8 per dimension number a
    quarter of the edges. A page exported before its views were drawn holds
    only the frame, title block and dimensions and fails both.
    report["viewsInExport"] gets the counts."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return False
    n = len(DRAWN.findall(text))
    edges = 0
    for v in part_views:
        try:
            edges += len(v.getVisibleEdges() or [])
        except Exception:  # noqa: BLE001
            pass
    if not edges:
        return True
    dims = sum(1 for v in (getattr(page, "Views", None) or []) if "Dimension" in str(getattr(v, "TypeId", "")) or "Dimension" in str(getattr(v, "Name", "")))
    tpl = _template_marks(page)
    by_elements = n - tpl - 8 * dims >= max(1, edges // 4)
    pts, tpl_pts = _svg_points(text), _template_points(page)
    by_points = pts - tpl_pts - DIM_POINTS * dims >= max(24, edges)
    ok = by_elements or by_points
    if report is not None:
        report["viewsInExport"] = {"ok": ok, "drawn": n, "template": tpl, "dimensions": dims, "viewEdges": edges,
                                   "points": pts, "templatePoints": tpl_pts, "byPoints": by_points, "byElements": by_elements}
    return ok


def template_in_svg(path, page):
    """Whether TechDraw's SVG export holds the page's template: one of its
    title block's texts (as filled), or its frame's own words, is in it."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return False
    want = []
    try:
        want = [str(v) for v in dict(page.Template.EditableTexts).values() if str(v).strip() and len(str(v)) > 2]
    except Exception:  # noqa: BLE001
        pass
    want += ["tolerances", "Title", "Scale", "SCALE", "DRAWING"]
    return any(w in text for w in want)


# ---- dimensions on the TechDraw page ---------------------------------------------------

def _view_frame(v, box):
    """How a view's own 2D geometry lies against views.project's: (scale,
    sx, sy, tx, ty) with td = (s·sx·x + tx, s·sy·y + ty), fitted on the
    visible extents and the sign of y checked against the vertices. Each
    release centres, scales and flips its geometry its own way."""
    import Part

    edges = list(v.getVisibleEdges() or [])
    if not edges:
        return None
    bb = _edges_box(edges) or Part.makeCompound(edges).BoundBox
    w, h = box[2] - box[0], box[3] - box[1]
    if max(w, h) < 1e-9:
        return None
    s = (bb.XLength / w) if w >= h else (bb.YLength / h)
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    best = None
    pts = [(p.x, p.y) for p in _vertices(v)]
    for sx in (1, -1):
        for sy in (1, -1):
            fr = (s, sx, sy, bb.Center.x - s * sx * cx, bb.Center.y - s * sy * cy)
            best = min(best or (math.inf, fr), (_fit_score(fr, pts, box), fr))
    return best[1]


def _edges_box(edges):
    """The drawn edges' extents from points on them: a B-spline's own
    BoundBox takes in its poles, which lie off the line, and threw the
    fitted frame (its scale and centre) off. None when no edge can be
    sampled."""
    xs, ys = [], []
    for e in edges:
        try:
            pts = e.discretize(Number=32)
        except Exception:  # noqa: BLE001
            continue
        xs += [p.x for p in pts]
        ys += [p.y for p in pts]
    if not xs:
        return None
    import types

    return types.SimpleNamespace(XLength=max(xs) - min(xs), YLength=max(ys) - min(ys),
                                 Center=types.SimpleNamespace(x=(max(xs) + min(xs)) / 2, y=(max(ys) + min(ys)) / 2))


def _fit_score(fr, pts, box):
    # The box's corners mapped should land on the view's vertices for a
    # part with corners; a round one ties, and any frame does.
    s, sx, sy, tx, ty = fr
    if not pts:
        return 0.0
    total = 0.0
    for x, y in ((box[0], box[1]), (box[2], box[3]), (box[0], box[3]), (box[2], box[1])):
        X, Y = s * sx * x + tx, s * sy * y + ty
        total += min(math.hypot(X - px, Y - py) for px, py in pts)
    return total


def _vertices(v):
    out, i = [], 0
    while True:
        try:
            g = v.getVertexByIndex(i)
        except Exception:
            break
        if g is None:
            break
        out.append(g.Point if hasattr(g, "Point") else g)
        i += 1
        if i > 20000:
            break
    return out


def _edges(v):
    out, i = [], 0
    while True:
        try:
            g = v.getEdgeByIndex(i)
        except Exception:
            break
        if g is None:
            break
        out.append(g)
        i += 1
        if i > 20000:
            break
    return out


def _to_view(fr, p2):
    s, sx, sy, tx, ty = fr
    return (s * sx * p2[0] + tx, s * sy * p2[1] + ty)


def _edge_ends(v, verts):
    """The indices of the view's vertices that are ends of its drawn edges.
    TechDraw's vertex list also holds the centre of every circle and arc
    it draws (a B-spline TechDraw draws as an arc too), and a flat arc's
    centre lies far outside the part: picked as an extreme it measured
    55.5 for a 47 mm high stem. All of them when the edges cannot be read."""
    ends = []
    for e in _edges(v):
        for p in getattr(e, "Vertexes", None) or ():
            q = getattr(p, "Point", p)
            ends.append((q.x, q.y))
    if not ends:
        return list(range(len(verts)))
    out = [k for k, p in enumerate(verts) if any(abs(p.x - x) < 1e-3 and abs(p.y - y) < 1e-3 for x, y in ends)]
    return out or list(range(len(verts)))


def extent_pairs(verts, ends, horizontal, mm, scale=1.0):
    """The vertex pairs to try for an overall size, best first: the
    extremes along the axis in the view's own 2D coordinates among the
    edges' ends, then among all vertices, then any pair of edge ends whose
    distance along the axis is the size (at the view's scale or 1:1; the
    lowest first). Each pair (lo, hi) of vertex indices, at most five."""
    key = (lambda k: verts[k].x) if horizontal else (lambda k: verts[k].y)
    out = []

    def add(pair):
        if pair not in out and pair[0] != pair[1] and abs(key(pair[1]) - key(pair[0])) > 1e-6:
            out.append(pair)

    for pool in (ends, range(len(verts))):
        pool = list(pool)
        if len(pool) >= 2:
            add((min(pool, key=key), max(pool, key=key)))
    srt = sorted(ends, key=key)
    for want in {mm * scale, mm}:
        for a in srt:
            for b in srt:
                d = key(b) - key(a)
                if d > 0 and abs(d - want) <= max(0.01, 0.002 * want):
                    add((a, b))
                    break
    return out[:5]


def _extent_dim(doc, page, v, horizontal, mm):
    """A DistanceX (or DistanceY) dimension of view v between its two
    extreme drawn vertices along that axis (ends of drawn edges, never a
    circle's or arc's centre), kept only when TechDraw measures the part's
    size mm; when the extremes measure otherwise, the next pairs of
    extent_pairs, each checked the same way. {dim, dimension, measured}
    or {why}."""
    verts = _vertices(v)
    if len(verts) < 2:
        return {"why": "the view has no vertices yet (TechDraw had not drawn it)"}
    try:
        sv = float(getattr(v, "Scale", 1.0) or 1.0)
    except Exception:  # noqa: BLE001
        sv = 1.0
    pairs = extent_pairs(verts, _edge_ends(v, verts), horizontal, mm, sv)
    if not pairs:
        return {"why": "its extreme vertices are one point"}
    first = None
    for lo, hi in pairs:
        try:
            dim = doc.addObject("TechDraw::DrawViewDimension", "Dimension")
            dim.Type = "DistanceX" if horizontal else "DistanceY"
            dim.MeasureType = "Projected"
            dim.References2D = [(v, f"Vertex{lo}"), (v, f"Vertex{hi}")]
            page.addView(dim)
            doc.recompute()
            raw = float(dim.getRawValue())
        except Exception as e:  # noqa: BLE001
            return {"why": f"TechDraw refused it: {e}"}
        if abs(raw - mm) <= max(0.05, 0.002 * mm):
            return {"dim": dim, "dimension": dim.Name, "measured": round(raw, 4), "value": round(mm, 4)}
        first = raw if first is None else first
        try:
            page.removeView(dim)
            doc.removeObject(dim.Name)
        except Exception:  # noqa: BLE001
            pass
    return {"why": f"TechDraw measured {first:.4g} between the view's extreme vertices, not {mm:.4g}"
                   + (f" (and no other pair of its vertices measured it, {len(pairs)} tried)" if len(pairs) > 1 else "") + ": left off"}


def match_circle(circles, centre, radius, frames):
    """The index of the circle (cx, cy, r) that is the hole: for each way
    the view may hold its geometry (frames: functions from the part's 2D
    point to the view's, with the scale they apply), the circle of that
    radius (within 10%) whose centre is nearest, within half its radius.
    None when no frame finds one. A frame may carry its own radius
    tolerance as a third item (the view's own scale is exact: 2%)."""
    for fr in frames:
        to_view, k = fr[0], fr[1]
        rtol = fr[2] if len(fr) > 2 else 0.1
        try:
            c = to_view(centre)
        except Exception:  # noqa: BLE001
            continue
        r = radius * k
        best = None
        for i, (x, y, rr) in enumerate(circles):
            if abs(rr - r) > rtol * r + 1e-6:
                continue
            d = math.hypot(x - c[0], y - c[1])
            if d <= 0.5 * r + 1e-6 and (best is None or d < best[0]):
                best = (d, i)
        if best is not None:
            return best[1]
    return None


def _page_dims(doc, page, made, drawn, specs, at=None, H=None):
    """The dimensions and hole callouts asked for, on the TechDraw page as
    its own dimensions on the views' vertices and circles — measured by
    TechDraw, so they follow the part — each read back against the value the
    files carry. Returns (dims made, what could not be). Each item stands on
    its own: one that fails (TechDraw refuses it, its view has no geometry,
    an error in the matching) is listed in what could not be, named, and the
    rest still go on the page."""
    # By the view's name: a second drawing's labels come out "Front001".
    by_view = dict(made)
    view_frames, done, missed = {}, [], []
    for sp in specs:
        try:
            got = _page_dim(doc, page, by_view, view_frames, drawn, sp, at, H)
        except Exception as e:  # noqa: BLE001 — this item only; the rest go on
            got = {"why": f"TechDraw could not take it here: {type(e).__name__}: {e}"}
        if "why" in got:
            missed.append({**_brief(sp), **got})
        else:
            done.append({**_brief(sp), **got})
    return done, missed


def _page_dim(doc, page, by_view, view_frames, drawn, sp, at=None, H=None):
    """One dimension or hole callout of _page_dims on the page:
    {dimension, measured[, warning]} or {why}. view_frames: each view's
    fitted frame, worked out once per view."""
    import Part

    view = sp["view"]
    v = by_view.get(view)
    if v is None:
        return {"why": "the view is not on the page"}
    if view not in view_frames:
        view_frames[view] = _view_frame(v, drawn[view]["box"])
    fr = view_frames[view]
    if fr is None:
        return {"why": "the view has no geometry headless"}
    bx = drawn[view]["box"]
    tol = max(0.05, 0.002 * fr[0] * max(bx[2] - bx[0], bx[3] - bx[1]))
    refs = []
    sized = None
    if sp["type"] in ("Diameter", "Radius"):
        circles, idx, turns = [], [], []
        for i, e in enumerate(_edges(v)):
            cu = getattr(e, "Curve", None)
            if isinstance(cu, (Part.Circle, Part.ArcOfCircle)) or hasattr(cu, "Radius"):
                try:
                    circles.append((cu.Center.x, cu.Center.y, cu.Radius))
                    idx.append(i)
                    turns.append(abs(e.LastParameter - e.FirstParameter))
                except Exception:
                    continue
        if sp["type"] == "Diameter":
            # A diameter is called out on a circle that goes all the way
            # round, never on an arc of that radius (the "4× ⌀6" leader
            # landed on a slot's R3 end): the arcs kept are those that
            # together close their circle (a hole TechDraw drew in two halves).
            keep = full_circles(circles, turns)
            circles, idx = [circles[k] for k in keep], [idx[k] for k in keep]
        # The view's frame fitted on its extents first; then its own
        # projection of the hole's centre (projectPoint), scaled or not,
        # y as it is or turned over: a fit thrown off by the view's
        # extents (hidden lines, a section) no longer loses the circle.
        # (Its own list: the views' frames stay by view name.)
        tries = [(lambda p, fr=fr: _to_view(fr, p), fr[0])]
        p3 = sp.get("centre3")
        sv = float(getattr(v, "Scale", 1.0) or 1.0)
        if p3 is not None and hasattr(v, "projectPoint"):
            # TechDraw draws the part centred on its bounding box's centre;
            # projectPoint projects about the origin, so the hole's centre
            # is taken from the box's centre first (the earlier try without
            # it found a hole only in a view whose part sat on the origin).
            try:
                q = v.projectPoint(V(*p3))
                o = _source_centre(v)
                qo = v.projectPoint(o) if o is not None else None
                for base in ([q.x - qo.x, q.y - qo.y] if qo is not None else None, [q.x, q.y]):
                    if base is None:
                        continue
                    for k in (sv, 1.0):
                        for fy in (1, -1):
                            tries.append((lambda _p, b=base, k=k, fy=fy: (b[0] * k, fy * b[1] * k), k, 0.02))
            except Exception:  # noqa: BLE001
                pass
        hit = match_circle(circles, sp["centre"], sp["radius"], tries)
        if hit is None:
            # Not where any frame puts the hole: a circle of its size (the
            # view's scale or 1:1, within 2%), the one nearest where the
            # fitted frame puts it, said so in a warning.
            c = _to_view(fr, sp["centre"])
            same = [i for i, (x, y, rr) in enumerate(circles)
                    if any(abs(rr - sp["radius"] * k) <= 0.02 * sp["radius"] * k + 1e-6 for k in {sv, 1.0, fr[0]})]
            if same:
                hit = min(same, key=lambda i: math.hypot(circles[i][0] - c[0], circles[i][1] - c[1]))
                sized = "placed on the view's circle of that size nearest the hole (its place did not match): check it is the hole meant"
        if hit is not None:
            refs = [(v, f"Edge{idx[hit]}")]
    else:
        verts = _vertices(v)
        for p2 in sp["points"]:
            q = _to_view(fr, p2)
            near = min(range(len(verts)), key=lambda k: math.hypot(verts[k].x - q[0], verts[k].y - q[1]), default=None)
            if near is None or math.hypot(verts[near].x - q[0], verts[near].y - q[1]) > tol:
                refs = []
                break
            refs.append((v, f"Vertex{near}"))
    if not refs:
        return {"why": "no vertex or circle of the view there (a hidden line, or a point TechDraw does not draw)"}
    try:
        dim = doc.addObject("TechDraw::DrawViewDimension", "Dimension")
        dim.Type = sp["type"]
        dim.MeasureType = "Projected"
        dim.References2D = refs
        page.addView(dim)
        if sp.get("label"):
            dim.Arbitrary = True
            dim.FormatSpec = sp["label"]
        else:
            spec = dim.FormatSpec
            if sp.get("fit"):
                spec = f"{spec} {sp['fit']}"
            if sp.get("prefix"):
                spec = sp["prefix"] + spec
            dim.FormatSpec = spec
        if sp.get("textAt") and at and view in at and H is not None:
            # The callout's text where the files have it, outside the
            # view, read horizontally on a reference line (ISO).
            cx, cy = at[view]
            dim.X, dim.Y = sp["textAt"][0] - cx, cy - sp["textAt"][1]
            try:
                dim.ViewObject.StandardAndStyle = "ISO Referencing"
            except Exception:  # noqa: BLE001 — no window: the style is the preference's
                pass
            try:
                # The size the callouts were kept apart at (place_callout).
                dim.ViewObject.Fontsize = f"{PAGE_FONT} mm"
            except Exception:  # noqa: BLE001
                pass
        if sp.get("over") is not None or sp.get("under") is not None:
            dim.EqualTolerance = False
            dim.OverTolerance = f"{sp.get('over') or 0} mm"
            dim.UnderTolerance = f"{sp.get('under') or 0} mm"
        doc.recompute()
        raw = float(dim.getRawValue())
    except Exception as e:
        return {"why": f"TechDraw refused it: {e}"}
    ok = abs(raw - sp["value"]) <= max(0.01, 0.002 * sp["value"])
    warn = None if ok else f"TechDraw measures {raw:.4g}, not {sp['value']:.4g}: check its references in the GUI"
    if sized:
        warn = f"{warn}; {sized}" if warn else sized
    return {"dimension": dim.Name, "measured": round(raw, 4), **({"warning": warn} if warn else {})}


def _source_centre(v):
    """The centre of the bounding box of what view v draws (TechDraw
    centres its geometry there), or None."""
    bb = None
    for o in list(getattr(v, "Source", None) or []):
        try:
            b = o.Shape.BoundBox
        except Exception:  # noqa: BLE001
            continue
        if bb is None:
            bb = FreeCAD.BoundBox(b)
        else:
            bb.add(b)
    return V(bb.Center.x, bb.Center.y, bb.Center.z) if bb is not None else None


def _brief(sp):
    """An item of _page_dims as the answer names it: its view, type, value
    and the text it reads ("4× ⌀8 THRU ⌴⌀13 ↧8.5", "2× ⌀6", "⌀21")."""
    out = {"view": sp.get("view"), "type": sp.get("type")}
    try:
        out["value"] = round(float(sp["value"]), 4)
    except Exception:  # noqa: BLE001
        out["value"] = sp.get("value")
    item = sp.get("label") or (f"{sp.get('prefix') or ''}{'⌀' if sp.get('type') == 'Diameter' else 'R' if sp.get('type') == 'Radius' else ''}"
                               f"{out['value']:g}{' ' + sp['fit'] if sp.get('fit') else ''}" if isinstance(out["value"], (int, float)) else None)
    if item:
        out["item"] = item
    return out


def _tolerance(nominal, d):
    """(over, under) mm from a fit or plus/minus; (None, None) for neither."""
    if d.get("fit"):
        return iso286.limits(nominal, d["fit"])
    if d.get("plus") is not None or d.get("minus") is not None:
        p = float(d.get("plus") or 0)
        m = d.get("minus")
        m = -abs(float(m)) if m is not None else -p
        return p, m
    return None, None


# ---- feature dimensions, hole callouts, the title block --------------------------------

def _to_paper(p2, box, centre, scale):
    bx, by = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return (centre[0] + (p2[0] - bx) * scale, centre[1] - (p2[1] - by) * scale)


def _ref_point(session, objs, r, what):
    """A 3D place a dimension measures from: a point [x, y, z], or a face or
    edge query on a body ({ body, kind, type, radius, near, normal … }) —
    a circle's centre, an edge's middle, a face's centre. Returns (point,
    the circle edge when it is one)."""
    import Part

    if isinstance(r, list):
        return picks.vec3(r, what), None
    if not isinstance(r, dict):
        raise ToolError("invalid_input", f"{what}: a point [x, y, z] or a query {{ body, kind: edge|face, type, radius, near }}.")
    q = dict(r)
    q.setdefault("body", objs[0].Label)
    q.setdefault("kind", "edge")
    _, _, hits = M.query(session, q)
    if not hits:
        raise ToolError("not_found", f"{what}: nothing on {q['body']} matches {r} — shape_query lists them.")
    if len(hits) > 1:
        if q.get("near") is None:
            raise ToolError("invalid_input", f"{what}: {len(hits)} match — add near: [x, y, z] to take the closest.")
        pt = picks.vec3(q["near"] if isinstance(q["near"], list) else q["near"]["point"], "near")
        hits = sorted(hits, key=lambda h: h[1].distToShape(Part.Vertex(pt))[0])
    el = hits[0][1]
    if hasattr(el, "Curve") and isinstance(el.Curve, (Part.Circle,)):
        return FreeCAD.Vector(el.Curve.Center), el
    if hasattr(el, "Curve"):
        return el.valueAt((el.FirstParameter + el.LastParameter) / 2), el
    return el.CenterOfMass, el


def _callout(nominal, d, diameter=False):
    try:
        return d.get("label") or iso286.text(nominal, d.get("fit"), d.get("plus"), d.get("minus"), diameter)
    except ValueError as e:
        raise ToolError("invalid_input", f"fit: {e}")


def _cylinder_of(f):
    """(axis, centre, radius) of a face that is a cylinder: Part's own, or
    a surface of revolution of a line parallel to its axis (what
    PartDesign's Hole and Revolution make); else None."""
    import Part

    srf = f.Surface
    if isinstance(srf, Part.Cylinder):
        return srf.Axis, srf.Center, srf.Radius
    if type(srf).__name__ != "SurfaceOfRevolution":
        return None
    try:
        ax = V(srf.Direction)
        ax.normalize()
        loc = V(srf.Location)
        bc = srf.BasisCurve
        if type(bc).__name__ not in ("Line", "LineSegment"):
            return None
        d = V(bc.Direction) if hasattr(bc, "Direction") else (bc.EndPoint - bc.StartPoint)
        d.normalize()
        if abs(abs(d.dot(ax)) - 1) > 1e-6:
            return None
        q = V(bc.Location if hasattr(bc, "Location") else bc.StartPoint) - loc
        radial = q - ax * q.dot(ax)
        if radial.Length < 1e-9:
            return None
        return ax, loc, radial.Length
    except Exception:  # noqa: BLE001
        return None


def _pd_holes(objs, view):
    """PartDesign Hole features of the bodies drawn, seen end on in the
    view: [{diameter, centres, suffix, cut}] — what FreeCAD's own Hole
    says it is (its size, thread, depth, counterbore or countersink), at
    the centres of its profile's circles."""
    Z, X, Y = views.frame(view)
    out = {}
    for o in objs:
        if o.TypeId != "PartDesign::Body":
            continue
        for f in getattr(o, "Group", []) or []:
            if f.TypeId != "PartDesign::Hole" or getattr(f, "Suppressed", False):
                continue
            try:
                prof = f.Profile[0] if isinstance(f.Profile, tuple) else f.Profile
                pl = o.Placement.multiply(prof.Placement)
                normal = pl.Rotation.multVec(V(0, 0, 1))
                if abs(abs(normal.dot(Z)) - 1) > 1e-6:
                    continue
                pts = []
                for i, g in enumerate(prof.Geometry):
                    if prof.getConstruction(i):
                        continue
                    if type(g).__name__ == "Circle":
                        pts.append(pl.multVec(g.Center))
                    elif type(g).__name__ == "Point":
                        pts.append(pl.multVec(V(g.X, g.Y, g.Z)))
                if not pts:
                    continue
                dia = round(float(f.Diameter), 3)
                bits = []
                thread = str(getattr(f, "ThreadType", "None")) not in ("None", "") and bool(getattr(f, "Threaded", False))
                head = str(f.ThreadSize) if thread else None
                if str(getattr(f, "DepthType", "")) == "ThroughAll":
                    bits.append("THRU")
                else:
                    bits.append(f"↧{_num(float(f.Depth))}")
                cut = str(getattr(f, "HoleCutType", "None"))
                cutd = float(getattr(f, "HoleCutDiameter", 0) or 0)
                kind = None
                # FreeCAD names a cut by its kind or by the screw it takes
                # (ISO 4762 a counterbore; ISO 10642, 2009, 7046 a countersink).
                if cut not in ("None", "") and any(w in cut for w in ("ountersink", "10642", "2009", "7046", "14582")):
                    kind = "countersink"
                    bits.append(f"⌵⌀{_num(cutd)} × {_num(float(getattr(f, 'HoleCutCountersinkAngle', 90)))}°")
                elif cut not in ("None", ""):
                    kind = "counterbore"
                    bits.append(f"⌴⌀{_num(cutd)} ↧{_num(float(f.HoleCutDepth))}")
                key = (dia, head, " ".join(bits))
                g = out.setdefault(key, {"diameter": dia, "thread": head, "suffix": " ".join(bits), "cut": kind, "cutDiameter": round(cutd, 3) if kind else None,
                                         "centres": [], "features": []})
                g["centres"] += pts
                g["features"].append(f.Label)
            except Exception:  # noqa: BLE001 — a Hole that cannot be read is found by its faces below
                continue
    return list(out.values())


DEPTHS = {}  # (diameter, x, y in the view) -> length along the axis, from the last _holes()


def _holes(objs, view, skip=()):
    """The round holes seen end on in a view, grouped by diameter: [(d,
    [centres])]. A hole is a cylindrical face (Part's, or the surface of
    revolution PartDesign's Hole makes) that goes all the way round into
    the part, its axis along the view. skip: (diameter, centre) already
    called out (a PartDesign Hole's bore and counterbore)."""
    Z, _, _ = views.frame(view)
    seen = {}
    for o in objs:
        sh = o.Shape
        for f in sh.Faces:
            cyl = _cylinder_of(f)
            if cyl is None:
                continue
            ax, c, rad = cyl
            if abs(abs(ax.dot(Z)) - 1) > 1e-6:
                continue
            # A hole's material is outside its cylinder: the face's normal points to the axis.
            u0, u1, v0, v1 = f.ParameterRange
            p = f.valueAt((u0 + u1) / 2, (v0 + v1) / 2)
            n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
            radial = p - c - ax * (p - c).dot(ax)
            if radial.Length < 1e-9 or n.dot(radial) > 0:
                continue
            dia = round(2 * rad, 3)
            key = (round(c.dot(views.frame(view)[1]), 2), round(c.dot(views.frame(view)[2]), 2))
            got = seen.setdefault(dia, {}).setdefault(key, [c, 0.0, [], ax])
            # The turn the face covers about its axis (u for Part's cylinder
            # and for a surface of revolution alike).
            got[1] += abs(u1 - u0)
            # Its length along the axis (a counterbore's depth).
            try:
                got[2] += [vx.Point.dot(ax) for vx in f.Vertexes]
            except Exception:  # noqa: BLE001
                pass
    # A hole goes all the way round (in one face or two); a cavity's rounded
    # inside corner is a quarter turn and is no hole.
    X, Y = views.frame(view)[1], views.frame(view)[2]
    out = []
    DEPTHS.clear()
    for d, v in seen.items():
        for c, span, along, _ax in v.values():
            if along:
                DEPTHS[(d, round(c.dot(X), 2), round(c.dot(Y), 2))] = round(max(along) - min(along), 3)
        centres = [c for c, span, _a, _x in v.values() if span >= 0.95 * 2 * math.pi]
        centres = [c for c in centres if not any(abs(d - sd) < 0.02 and abs(c.dot(X) - sc.dot(X)) < 0.05 and abs(c.dot(Y) - sc.dot(Y)) < 0.05 for sd, sc in skip)]
        if centres:
            out.append((d, centres))
    return sorted(out, key=lambda x: -x[0])


def title_block_grid(sheet, fields, margin=10.0, width=130.0):
    """A title block of labelled cells in the bottom-right corner: the
    title across the top, then pairs of fields."""
    rows = [("TITLE", fields.get("title", ""))]
    pairs = [k for k in ("partNumber", "revision", "material", "finish", "drawnBy", "date", "checkedBy", "company", "scale", "projection", "sheet", "generalTolerance") if fields.get(k)]
    names = {"partNumber": "PART No.", "revision": "REV", "material": "MATERIAL", "finish": "FINISH", "drawnBy": "DRAWN", "date": "DATE", "checkedBy": "CHECKED",
             "company": "COMPANY", "scale": "SCALE", "projection": "PROJECTION", "sheet": "SHEET", "generalTolerance": "GENERAL TOL."}
    cell_h = 7.0
    n_rows = 1 + (len(pairs) + 1) // 2
    x1, y1 = sheet.w - margin, sheet.h - margin
    x0, y0 = x1 - width, y1 - cell_h * n_rows
    sheet.line([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], "visible", closed=True)
    half = width / 2
    for r in range(1, n_rows):
        y = y0 + r * cell_h
        sheet.line([(x0, y), (x1, y)], "thin")
    if n_rows > 1:
        sheet.line([(x0 + half, y0 + cell_h), (x0 + half, y1)], "thin")
    sheet.text(x0 + 1.5, y0 + 2.4, 1.6, "TITLE")
    sheet.text(x0 + 1.5, y0 + cell_h - 1.4, 3.2, str(rows[0][1])[:44])
    for i, k in enumerate(pairs):
        r, c = 1 + i // 2, i % 2
        cx, cy = x0 + c * half, y0 + r * cell_h
        sheet.text(cx + 1.5, cy + 2.4, 1.6, names[k])
        sheet.text(cx + 1.5, cy + cell_h - 1.4, 2.6, str(fields[k])[:30])
    return (x0, y0, x1, y1)


# ---- TechDraw pieces the manual and patent pages share --------------------------------

def _page(doc, label, paper, blank=False):
    """An ordinary TechDraw page on TechDraw's own template (blank: the
    blank one, as patent sheets carry no title block)."""
    page = doc.addObject("TechDraw::DrawPage", "Page")
    page.Label = label
    tpl = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
    if blank:
        base = os.path.join(FreeCAD.getResourceDir(), "Mod", "TechDraw", "Templates")
        hits = glob.glob(os.path.join(base, "**", BLANK[paper]), recursive=True)
        path = hits[0] if hits else None
    else:
        path, _t = _template(paper)
    if path:
        tpl.Template = path
    page.Template = tpl
    return page


def _view(doc, page, source, view, scale, x, y, label, line_art=False):
    """A TechDraw view of source looking as views.VIEWS[view] does, at the
    page point (x, y) from the top left (mm). line_art: visible edges only
    (no hidden, smooth or seam lines), as patent figures are drawn."""
    z, xd = views.VIEWS[view]
    v = doc.addObject("TechDraw::DrawViewPart", "View")
    page.addView(v)
    v.Label = label
    v.Source = source
    v.Direction = V(*z)
    v.XDirection = V(*xd)
    v.ScaleType = "Custom"
    v.Scale = scale
    v.X = x
    v.Y = page_height(page) - y
    if line_art:
        for prop in ("HardHidden", "SmoothHidden", "SeamHidden", "IsoHidden", "SmoothVisible", "SeamVisible", "IsoVisible"):
            try:
                setattr(v, prop, False)
            except Exception:  # noqa: BLE001 — a property this release lacks
                pass
    return v


def page_height(page):
    try:
        return float(page.Template.Height)
    except Exception:  # noqa: BLE001
        return 297.0


def balloon_at(p3, centre3, view, scale, lift):
    """(origin, label) for a TechDraw balloon: the point p3 on the part and
    the label lift (dx, dy) mm on the paper from it, both in the view's own
    coordinates (from its centre, the shape's box centre TechDraw centres
    the view on, model mm, y up)."""
    px, py = views.point(p3, view)
    cx, cy = views.point(centre3, view)
    ox, oy = px - cx, py - cy
    return (ox, oy), (ox + lift[0] / scale, oy + lift[1] / scale)


def _balloon(doc, page, view, origin, at, text, plain=False):
    """A TechDraw balloon on view: text at `at`, its lead line to origin.
    plain: no bubble and no arrowhead (a patent's reference numeral)."""
    b = doc.addObject("TechDraw::DrawViewBalloon", "Balloon")
    b.SourceView = view
    b.OriginX, b.OriginY = origin
    b.X, b.Y = at
    b.Text = str(text)
    if plain:
        for prop, val in (("BubbleShape", "None"), ("EndType", "None")):
            try:
                setattr(b, prop, val)
            except Exception:  # noqa: BLE001 — a value this release names otherwise
                pass
    page.addView(b)
    return b


def _note(doc, page, lines, x, y, size=None):
    """A TechDraw annotation: lines of text at the page point (x, y) from
    the top left, mm."""
    t = doc.addObject("TechDraw::DrawViewAnnotation", "Annotation")
    page.addView(t)
    t.Text = [str(x_) for x_ in lines]
    if size:
        try:
            t.TextSize = size
        except Exception:  # noqa: BLE001
            pass
    t.X = x
    t.Y = page_height(page) - y
    return t


def _shapes_box(shapes):
    bb = shapes[0].BoundBox
    for sh in shapes[1:]:
        bb.add(sh.BoundBox)
    return bb



# ---- drawing_make ----------------------------------------------------------------------

# The views a hole is called out in, best first: where its circle is seen true.
HOLE_VIEWS = ("front", "right", "top", "left", "back", "bottom")
AXIS_NAME = {"front": "Y", "back": "Y", "right": "X", "left": "X", "top": "Z", "bottom": "Z"}


def _boxes_hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def hole_label(count, size, suffix=None):
    """"4× ⌀8 THRU ⌴⌀13 ↧8.5": count (when more than one), size, how made."""
    return (f"{count}× " if count > 1 else "") + str(size) + (f" {suffix}" if suffix else "")


def hole_groups(objs, order, drawn_views):
    """Every round hole of the bodies, grouped by how it is made, each
    with the view it is called out in: the first of order drawn whose
    direction is its axis (front before back), else view None and its
    axis named, for the hole table. [{diameter, centres, view, axis,
    thread, suffix, cut, cutDiameter, features}]."""
    out, seen_axes = [], []
    for v in order:
        Z = views.frame(v)[0]
        key = (round(abs(Z.x), 3), round(abs(Z.y), 3), round(abs(Z.z), 3))
        if key in seen_axes:
            continue
        seen_axes.append(key)
        pdh = _pd_holes(objs, v)
        skip = []
        for g in pdh:
            for c in g["centres"]:
                skip.append((g["diameter"], c))
                if g["cutDiameter"]:
                    skip.append((g["cutDiameter"], c))
        found = [dict(g) for g in pdh] + [{"diameter": d, "centres": cs, "thread": None, "suffix": None, "cut": None, "cutDiameter": None, "features": []}
                                          for d, cs in _holes(objs, v, skip)]
        X, Y = views.frame(v)[1], views.frame(v)[2]
        for g in found:
            g["depths"] = [DEPTHS.get((g["diameter"], round(c.dot(X), 2), round(c.dot(Y), 2))) for c in g["centres"]]
        found = merge_counterbores(found, lambda c: (c.dot(X), c.dot(Y)))
        shown = v if v in drawn_views else next((w for w in drawn_views if w in AXIS_NAME and AXIS_NAME[w] == AXIS_NAME.get(v)), None)
        for g in found:
            g["view"] = shown
            g["axis"] = AXIS_NAME.get(v, "?")
            out.append(g)
    return out


def merge_counterbores(groups, flat):
    """A wider plain hole on the same centres as a narrower hole (a pocket
    round a bolt hole) is its counterbore: one callout, "4× ⌀8 THRU
    ⌴⌀13 ↧8.5", not two. groups as hole_groups makes them; flat: a centre
    to its 2D place in the view."""
    out = list(groups)
    for big in sorted([g for g in out if not g.get("features") and not g.get("cut")], key=lambda g: -g["diameter"]):
        pb = sorted((round(flat(c)[0], 2), round(flat(c)[1], 2)) for c in big["centres"])
        for small in out:
            if small is big or small["diameter"] >= big["diameter"] or small.get("cut"):
                continue
            ps = [(round(flat(c)[0], 2), round(flat(c)[1], 2)) for c in small["centres"]]
            if pb and all(any(abs(a[0] - b[0]) < 0.05 and abs(a[1] - b[1]) < 0.05 for b in ps) for a in pb) and len(ps) == len(pb):
                depth = next((d for d in big.get("depths") or [] if d), None)
                bit = f"⌴⌀{_num(big['diameter'])}" + (f" ↧{_num(depth)}" if depth else "")
                small["suffix"] = f"{small['suffix']} {bit}" if small.get("suffix") else bit
                small["cut"], small["cutDiameter"] = "counterbore", big["diameter"]
                out.remove(big)
                break
    return out


def full_circles(circles, turns, share=0.95):
    """Which of a view's round edges belong to a circle drawn all the way
    round: circles [(cx, cy, r)], turns the angle each edge covers
    (radians). Edges on one centre and radius are taken together, so a
    circle drawn as two half arcs counts and a slot's end (half a turn) or a
    fillet (a quarter) does not. The indices kept."""
    groups = {}
    for i, (c, t) in enumerate(zip(circles, turns)):
        groups.setdefault((round(c[0], 2), round(c[1], 2), round(c[2], 3)), []).append((i, t))
    keep = []
    for members in groups.values():
        if sum(t for _i, t in members) >= share * 2 * math.pi:
            keep += [i for i, _t in members]
    return sorted(keep)


def hole_circle(circles, points, radius, rtol=0.02, thread=False):
    """Where a hole callout's leader may land in a drawn view: the first of
    points (the hole's centres in the view, in the order tried) with a
    drawn circle of the hole's radius (within rtol, 2%) centred on it
    (within 0.1 mm plus 5% of the radius). (index of the point, (cx, cy,
    r)) or None: then the callout is left off, never put on the nearest
    other round edge (a slot's end, a bore of another size; a hole hidden
    in this view has no circle drawn). circles: views.project's. A
    threaded hole (thread) is drawn at its tap drill when its thread is
    not modelled: a circle from 75% of its nominal radius up to it too."""
    lo = 0.75 * radius if thread else radius * (1 - rtol)
    for i, p in enumerate(points):
        best = None
        for c in circles or ():
            if not (lo - 1e-6 <= c[2] <= radius * (1 + rtol) + 1e-6):
                continue
            d = math.hypot(c[0] - p[0], c[1] - p[1])
            if d <= 0.1 + 0.05 * radius and (best is None or d < best[0]):
                best = (d, c)
        if best is not None:
            return i, best[1]
    return None


def callout_leader(at, r, outline, k, left=None, slope=45):
    """A hole callout's leader from the circle (centre at, radius r on the
    paper) out past the view's outline, the k-th in that view turned a
    little more: (tip, elbow, tail end, text anchor). Up and to the left
    or right, whichever side of the view the hole is nearer (or as left
    says), at slope degrees over the horizontal (45 unless asked)."""
    if left is None:
        left = at[0] <= (outline[0] + outline[2]) / 2
    ang = math.radians(180 - slope if left else slope)
    tip = (at[0] + r * math.cos(ang), at[1] - r * math.sin(ang))
    # Out at the slope until clear of the view's outline above it: 6 mm over
    # its top, each further callout of the view 6 mm higher.
    rise = max(6.0, tip[1] - outline[1] + 6.0 + 6.0 * k)
    run_ = rise / math.tan(math.radians(slope))
    elbow = (tip[0] + (-run_ if left else run_), tip[1] - rise)
    tail = (elbow[0] + (-12 if left else 12), elbow[1])
    return tip, elbow, tail, ("end" if left else "start")


# TechDraw's dimension text on the page (its Fontsize set to this), and the
# clear margin kept round each callout's text.
PAGE_FONT = 3.5
CALLOUT_PAD = 1.5


def _segs_cross(a, b, c, d):
    """Whether segments ab and cd cross (touching ends do not count)."""
    def o(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)
    o1, o2, o3, o4 = o(a, b, c), o(a, b, d), o(c, d, a), o(c, d, b)
    return o1 * o2 < 0 and o3 * o4 < 0


def _seg_in_box(a, b, box):
    """Whether segment ab passes through box (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    for t in (i / 16 for i in range(17)):
        x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        if x0 < x < x1 and y0 < y < y1:
            return True
    return False


def _pad(box, m):
    return (box[0] - m, box[1] - m, box[2] + m, box[3] + m)


def page_text_box(centre, text, size=PAGE_FONT):
    """The box TechDraw's text takes on the page, centred where the
    callout's text is put (dim.X, dim.Y), at the page's font size."""
    w, h = 0.6 * size * len(text), 1.25 * size
    return (centre[0] - w / 2, centre[1] - h / 2, centre[0] + w / 2, centre[1] + h / 2)


def place_callout(pa, r, outline, k, label, busy, placed, size=3.0, tries=12):
    """A hole callout clear of what is on the sheet and of every callout
    placed before it: its text (as the sheet draws it and as the TechDraw
    page does, larger, with a margin) off the views, the texts and every
    earlier callout's text, and its leaders (the sheet's tip, elbow, tail;
    the page's straight line from the hole to its text) crossing no earlier
    leader nor running through an earlier text. Each try goes 6 mm further
    up, on the hole's own side first, then the other, its leader at 45°,
    then 30° and 60° (a leader parallel to an earlier one can pass under
    that one's text only at another slope). The first clear
    place, else the one with fewest clashes.
    placed: earlier callouts as returned here (their "boxes" and "segs");
    returns {tip, elbow, tail, anchor, text, textAt, boxes, segs, clashes}."""
    best = None
    near_left = pa[0] <= (outline[0] + outline[2]) / 2
    for extra in range(tries):
        for left, slope in ((sd, sl) for sd in (near_left, not near_left) for sl in (45, 30, 60)):
            tip, elbow, tail, anchor = callout_leader(pa, r, outline, k + extra, left, slope)
            t = (tail[0] + (1 if anchor == "start" else -1), tail[1] - 1, size, label, anchor)
            tb = sheets.text_box(t)
            at = ((tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2)
            pb = page_text_box(at, label)
            boxes = [_pad(tb, CALLOUT_PAD / 2), _pad(pb, CALLOUT_PAD)]
            # The page's leader: from the hole to the near lower corner of its text.
            corner = (pb[2], pb[3]) if anchor == "end" else (pb[0], pb[3])
            segs = [(tip, elbow), (elbow, tail), (pa, corner)]
            clashes = sum(1 for b in boxes for o in busy if _boxes_hit(b, o))
            for q in placed:
                clashes += sum(1 for b in boxes for o in q["boxes"] if _boxes_hit(b, o))
                clashes += sum(1 for s1 in segs for s2 in q["segs"] if _segs_cross(s1[0], s1[1], s2[0], s2[1]))
                clashes += sum(1 for s1 in segs for o in q["boxes"] if _seg_in_box(s1[0], s1[1], o))
                clashes += sum(1 for s2 in q["segs"] for o in boxes if _seg_in_box(s2[0], s2[1], o))
            got = {"tip": tip, "elbow": elbow, "tail": tail, "anchor": anchor, "text": t, "textAt": at, "boxes": boxes, "segs": segs, "clashes": clashes}
            if clashes == 0:
                return got
            if best is None or clashes < best["clashes"]:
                best = got
    return best


def default_projection(asked):
    """(projection, where it came from): as asked; else TechDraw's own
    preference (General ▸ ProjectionAngle: first, third); else third angle
    when FreeCAD shows inch units (ASME), first angle (ISO) otherwise."""
    if asked:
        return asked, "asked"
    try:
        g = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/TechDraw/General")
        pa = g.GetInt("ProjectionAngle", -1)
        if pa in (0, 1):
            return ("first", "third")[pa], "TechDraw's preference"
    except Exception:  # noqa: BLE001
        pass
    try:
        schema = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Units").GetInt("UserSchema", 0)
        if schema in (2, 3, 5, 7):
            return "third", "inch units (ASME)"
    except Exception:  # noqa: BLE001
        pass
    return "first", "ISO default"


def drawing_make(s, a):
    objs = _bodies(s, a.get("bodies"))
    want = a.get("views") or ["front", "top", "right", "iso"]
    bad = [v for v in want if v not in views.VIEWS]
    if bad:
        raise ToolError("invalid_input", f"views: {bad[0]} is not one — they are: {', '.join(views.VIEWS)}.")
    want = list(dict.fromkeys(want))
    projection, proj_from = default_projection(a.get("projection"))
    if projection not in sheets.GRID:
        raise ToolError("invalid_input", "projection: first (ISO) or third (ASME).")
    paper = a.get("paper", "auto")
    if paper not in ("A4", "A3", "auto"):
        raise ToolError("invalid_input", "paper: A4, A3 or auto.")
    shapes = [o.Shape for o in objs]
    sec_view = a.get("section")
    if sec_view is not None and sec_view not in want:
        raise ToolError("invalid_input", f"section: one of the views drawn ({', '.join(want)}) to show cut through.")
    if sec_view == "iso":
        raise ToolError("invalid_input", "section: a straight view (front, top, right …), not iso.")
    sec_label = str(a.get("sectionLabel") or "A")[:2].upper()
    drawn = {}
    for v in want:
        if v == sec_view:
            try:
                drawn[v] = views.section(shapes, v, float(a.get("sectionAt", 0)), hidden=bool(a.get("hidden")))
            except ValueError as e:
                raise ToolError("invalid_input", f"sectionAt: {e} — a smaller offset from the middle.")
        else:
            drawn[v] = views.project(shapes, v, hidden=bool(a.get("hidden")))
    sizes = {v: (d["box"][2] - d["box"][0], d["box"][3] - d["box"][1]) for v, d in drawn.items()}
    sc = a.get("scale")
    if sc is not None and (not isinstance(sc, (int, float)) or sc <= 0):
        raise ToolError("invalid_input", "scale: a number over 0 — 0.5 for 1:2, 2 for 2:1. Left out, the largest standard scale that fits.")
    papers = []
    for pp in (["A4", "A3"] if paper == "auto" else [paper]):
        # The views keep clear of the title block the page's template has
        # (the files' own smaller one without a page).
        tpath = _template(pp)[0] if a.get("page", True) else None
        area, block = template_room(tpath, pp)
        papers.append((pp, sheets.PAPER[pp], area, block))
    try:
        paper, L = sheets.choose(sizes, papers, projection, sc)
    except ValueError as e:
        raise ToolError("invalid_input", str(e))
    scale = L["scale"]
    scales = L["scales"]
    name = a.get("name") or (objs[0].Label if len(objs) == 1 else "Assembly")
    sheet = sheets.Sheet(*sheets.PAPER[paper], title=name)
    sheet.frame()
    bb = shapes[0].BoundBox
    for sh in shapes[1:]:
        bb.add(sh.BoundBox)
    extent = {"x": bb.XLength, "y": bb.YLength, "z": bb.ZLength}
    dims = []
    for v in want:
        d = drawn[v]
        cx, cy = L["centres"][v]
        sv = scales[v]
        lines = d["lines"]
        if v == sec_view:
            # The cut faces hatched 2.5 mm apart on the paper.
            lines = lines + [("thin", [p, q]) for p, q in views.hatch(d["cut"], 2.5 / sv)]
        sheet.place(lines, d["box"], (cx, cy), sv)
        h = sizes[v][1] * sv
        name_v = f"SECTION {sec_label}-{sec_label}" if v == sec_view else v.upper()
        if v == "iso" and sv != scale:
            name_v += f" ({sheets.scale_text(sv)})"
        # The view's name over it: under it is where its dimension goes.
        sheet.text(cx, cy - h / 2 - 3, 3.0, name_v, "middle")
    if a.get("dimensions", True):
        # Overall sizes once each, outside the outlines: 10 mm off, stacked 7.
        boxes = {v: L["boxes"][v] for v in want if v in views.AXES}
        for v, axis, pa, pb, off, mm in sheets.extent_dims(boxes, views.AXES, extent):
            sheet.dimension(pa, pb, off, _num(mm))
            dims.append({"view": v, "axis": axis, "mm": round(mm, 3)})
    section_out = None
    if sec_view:
        # The cutting plane seen edge on in another view: a chain line
        # across it, past its ends, lettered at both.
        Zs, _, _ = views.frame(sec_view)
        d_plane = drawn[sec_view]["plane"]
        shown = None
        for v in want:
            if v in (sec_view, "iso") or v not in views.VIEWS:
                continue
            Zv, Xv, Yv = views.frame(v)
            if abs(Zv.dot(Zs)) < 1e-6:
                shown = v
                break
        section_out = {"view": sec_view, "label": f"{sec_label}-{sec_label}", "plane": round(d_plane, 3), "cutFaces": len(drawn[sec_view]["cut"])}
        bbs = shapes[0].BoundBox
        for sh in shapes[1:]:
            bbs.add(sh.BoundBox)
        sec_origin = bbs.Center + Zs * (d_plane - bbs.Center.dot(Zs))
        if shown:
            Zv, Xv, Yv = views.frame(shown)
            box, centre = drawn[shown]["box"], L["centres"][shown]
            along_x = abs(Zs.dot(Xv)) > 0.5
            c = Zs * d_plane
            q = views.point(c, shown)
            if along_x:
                pa, pb = (q[0], box[1] - 4 / scale), (q[0], box[3] + 4 / scale)
            else:
                pa, pb = (box[0] - 4 / scale, q[1]), (box[2] + 4 / scale, q[1])
            ppa, ppb = _to_paper(pa, box, centre, scale), _to_paper(pb, box, centre, scale)
            sheet.line([ppa, ppb], "trail")
            for pp in (ppa, ppb):
                sheet.text(pp[0] + 1.5, pp[1] - 1.5, 3.5, sec_label)
            section_out["cutLineIn"] = shown
    # Feature dimensions asked for, each in its view: lengths between two
    # places, diameters and radii of round edges, with a tolerance or fit.
    placed, specs = [], []
    for i, d in enumerate(a.get("dims") or []):
        if not isinstance(d, dict) or d.get("view") not in drawn:
            raise ToolError("invalid_input", f"dims.{i}: {{ view (one drawn: {', '.join(want)}), kind: length|diameter|radius, a, b, offset, fit | plus/minus }}.")
        v = d["view"]
        kind = d.get("kind", "length")
        box, centre = drawn[v]["box"], L["centres"][v]
        pa3, ea = _ref_point(s, objs, d.get("a"), f"dims.{i}.a")
        pa = _to_paper(views.point(pa3, v), box, centre, scale)
        if kind == "length":
            pb3, _ = _ref_point(s, objs, d.get("b"), f"dims.{i}.b")
            pb = _to_paper(views.point(pb3, v), box, centre, scale)
            axis = d.get("along")
            a2, b2 = views.point(pa3, v), views.point(pb3, v)
            if axis == "h":
                value, pb = abs(b2[0] - a2[0]), (pb[0], pa[1])
            elif axis == "v":
                value, pb = abs(b2[1] - a2[1]), (pa[0], pb[1])
            else:
                value = math.hypot(b2[0] - a2[0], b2[1] - a2[1])
            label = _callout(value, d)
            sheet.dimension(pa, pb, float(d.get("offset", 8)), label)
            over, under = _tolerance(value, d)
            specs.append({"view": v, "type": {"h": "DistanceX", "v": "DistanceY"}.get(axis, "Distance"), "points": [a2, b2], "value": value,
                          "fit": d.get("fit"), "over": over, "under": under, "label": d.get("label")})
        elif kind in ("diameter", "radius"):
            import Part

            if ea is None or not isinstance(getattr(ea, "Curve", None), Part.Circle):
                raise ToolError("invalid_input", f"dims.{i}.a: a round edge ({{ kind: \"edge\", type: \"circle\", radius, near }}) for a {kind}.")
            rr = ea.Curve.Radius
            value = 2 * rr if kind == "diameter" else rr
            label = _callout(value, d, diameter=kind == "diameter")
            if kind == "radius":
                label = "R" + label
            over, under = _tolerance(value, d)
            specs.append({"view": v, "type": kind.capitalize(), "centre": views.point(pa3, v), "radius": rr, "value": value,
                          "fit": d.get("fit"), "over": over, "under": under, "label": d.get("label")})
            ang = math.radians(float(d.get("angle", 45)))
            rp = rr * scale
            tip = (pa[0] + rp * math.cos(ang), pa[1] - rp * math.sin(ang))
            elbow = (tip[0] + 8 * math.cos(ang), tip[1] - 8 * math.sin(ang))
            tail = (elbow[0] + (10 if math.cos(ang) >= 0 else -10), elbow[1])
            sheet.line([tip, elbow, tail], "dim")
            sheet.arrow(tip, elbow)
            sheet.text(tail[0] + (1 if math.cos(ang) >= 0 else -1), tail[1] - 1, 3.0, label, "start" if math.cos(ang) >= 0 else "end")
        else:
            raise ToolError("invalid_input", f"dims.{i}.kind: length, diameter or radius.")
        placed.append({"view": v, "kind": kind, "value": round(value, 4), "label": label})
    # Every round hole called out once per size, in a view that sees it end
    # on (its circle true): "4× ⌀8 THRU ⌴⌀13 ↧8.5". Holes no view drawn sees
    # end on go in a hole table on the sheet.
    holes_out, hole_table = [], []
    if a.get("holes"):
        if isinstance(a["holes"], str) and a["holes"] not in drawn:
            raise ToolError("invalid_input", f"holes: a view drawn ({', '.join(want)}), or true for every view that sees them.")
        order = [a["holes"]] if isinstance(a["holes"], str) else HOLE_VIEWS
        groups = hole_groups(objs, order, [v for v in want if v not in ("iso", sec_view)] if not isinstance(a["holes"], str) else [a["holes"]])
        fits = a.get("holeFits") or {}
        per_view, callouts, off = {}, [], []
        for g in groups:
            dia = g["diameter"]
            fit = fits.get(str(dia)) or fits.get(f"{dia:g}")
            size = g["thread"] if g.get("thread") else _callout(dia, {"fit": fit}, diameter=True)
            label = hole_label(len(g["centres"]), size, g.get("suffix"))
            row = {"view": g["view"], "diameter": dia, "count": len(g["centres"]), "label": label,
                   **({"from": "PartDesign Hole", "features": g["features"], **({"cut": g["cut"], "cutDiameter": g["cutDiameter"]} if g.get("cut") else {})}
                      if g.get("features") else {"from": "its faces"})}
            if g["view"] is None:
                row["axis"] = g["axis"]
                row["inTable"] = True
                hole_table.append(row)
                holes_out.append(row)
                continue
            hv = g["view"]
            k = per_view.get(hv, 0)
            per_view[hv] = k + 1
            box, centre = drawn[hv]["box"], L["centres"][hv]
            sv = scales[hv]
            cs = sorted(g["centres"], key=lambda c: (views.point(c, hv)[0], -views.point(c, hv)[1]))
            c0 = cs[0]
            # The leader lands on a drawn circle of the hole's size where the
            # hole projects, else the callout is left off and listed (it once
            # landed on a slot's end and on a bore of another size).
            on = hole_circle(drawn[hv].get("circles"), [views.point(c, hv) for c in cs], dia / 2, thread=bool(g.get("thread")))
            spec_at = {}
            if on is None:
                row["calloutOff"] = (f"no circle of ⌀{_num(dia)} drawn where the hole is in the {hv} view "
                                     "(hidden there, or drawn otherwise): left off the sheet rather than on another round edge")
                off.append({"view": hv, "label": label, "why": row["calloutOff"]})
            else:
                c0 = cs[on[0]]
                pa = _to_paper(on[1][:2], box, centre, sv)
            # Clear of every view and every text already on the sheet: the
            # callout goes up 6 mm more until it is.
            # and of every callout before it (text boxes tested against each
            # other at the page's font, leaders never crossing).
                busy = list(L["boxes"].values()) + [sheets.text_box(t) for t in sheet.texts]
                co = place_callout(pa, dia / 2 * sv, L["boxes"][hv], k, label, busy, callouts)
                callouts.append(co)
                tip, elbow, tail, t = co["tip"], co["elbow"], co["tail"], co["text"]
                sheet.line([tip, elbow, tail], "dim")
                sheet.arrow(tip, elbow)
                sheet.text(*t)
                spec_at = {"textAt": co["textAt"]}
            holes_out.append(row)
            over, under = _tolerance(dia, {"fit": fit}) if fit else (None, None)
            specs.append({"view": hv, "type": "Diameter", "centre": views.point(c0, hv), "centre3": [c0.x, c0.y, c0.z], "radius": dia / 2, "value": dia,
                          "fit": fit, "over": over, "under": under, "prefix": f"{len(g['centres'])}× " if len(g["centres"]) > 1 else "",
                          **spec_at,
                          **({"label": label} if g.get("features") or g.get("cut") else {})})
        if hole_table:
            rows = [("HOLE", "QTY", "AXIS")] + [(r["label"].split("× ", 1)[-1], str(r["count"]), r["axis"]) for r in hole_table]
            tw, th = 6 + 3.0 * 0.6 * max(len(r[0]) for r in rows) + 30, 6.0 * len(rows) + 2
            at = sheets.free_spot(L, tw, th) or (L["area"][0] + 2, L["area"][1] + 2)
            for i, (h_, q_, ax_) in enumerate(rows):
                y = at[1] + 6.0 * (i + 1)
                sheet.text(at[0] + 2, y, 3.0, h_)
                sheet.text(at[0] + tw - 16, y, 3.0, q_)
                sheet.text(at[0] + tw - 8, y, 3.0, ax_)
            sheet.line([(at[0], at[1]), (at[0] + tw, at[1]), (at[0] + tw, at[1] + th), (at[0], at[1] + th)], "thin", closed=True)
            sheet.line([(at[0], at[1] + 7.5), (at[0] + tw, at[1] + 7.5)], "thin")
            hole_table = {"at": [round(at[0], 1), round(at[1], 1)], "rows": rows}
    tb = dict(a.get("titleBlock") or {})
    tb.setdefault("title", name)
    tb.setdefault("scale", sheets.scale_text(scale))
    tb.setdefault("projection", f"{projection} angle")
    tb.setdefault("generalTolerance", "ISO 2768-m")
    if not tb.get("material"):
        mat = store.materials(s.doc).get(objs[0].Label) if len(objs) == 1 else None
        if mat:
            # Its name (a FreeCAD library card's, not its UUID); the id kept apart.
            tb["material"] = material_shown(mat, s.doc).upper()
            tb["materialId"] = str(mat)
    tb.setdefault("sheet", "1 / 1")
    tb.setdefault("date", datetime.date.today().isoformat())
    title_block_grid(sheet, tb)
    folder, base = out_place(s.out_dir, a.get("file"), name)
    page, made = (None, "not asked for")
    if a.get("page", True):
        page, made = _techdraw_page(s.doc, objs, [(v, L["centres"][v]) for v in want], scale, paper, f"{name} drawing", a.get("dimensions", True), specs, drawn,
                                     {**section_out, "origin": sec_origin} if section_out else None, tb, scales,
                                     {v: L["boxes"][v] for v in want if v in views.AXES}, projection, hole_table or None, extent)
    # The files are the page's own exports where TechDraw can write them;
    # Workshop's sheet writer (the same views by Open CASCADE's hidden-line
    # removal) writes the rest, and the answer says which is which.
    paths, frm = {}, {}
    if page is not None:
        exported = {}
        paths, why = _export_page(page, folder, base, report=exported)
        if isinstance(made, dict):
            # The wait just before the export, and whether the export holds the views.
            made["exportViewsReadyIn"] = exported.get("viewsReadyIn")
            for k in ("viewsNotReady", "viewsInExport", "exportScene", "exportSceneAgain"):
                if k in exported:
                    made[k if k != "viewsNotReady" else "exportViewsNotReady"] = exported[k]
        frm = {k: "TechDraw page" for k in paths}
        frm.update({k: f"Workshop's sheet writer: {w}" for k, w in why.items()})
    rest = [k for k in ("svg", "pdf", "dxf") if k not in paths]
    if rest:
        paths.update(_write(s, base, sheet, rest, folder))
        for k in rest:
            frm.setdefault(k, "Workshop's sheet writer: no TechDraw page")
    paths = {k: paths[k] for k in ("svg", "pdf", "dxf")}
    page_label = page.Label if page is not None else None
    s.snapshot("drawing_make")
    out = {
        "files": paths,
        "paper": paper,
        "scale": sheets.scale_text(scale),
        "projection": projection,
        "projectionFrom": proj_from,
        "fill": L["fill"],
        "views": [{"view": v, "at": [round(c, 1) for c in L["centres"][v]], "size": [round(sizes[v][0] * scales[v], 1), round(sizes[v][1] * scales[v], 1)],
                   **({"scale": sheets.scale_text(scales[v])} if scales[v] != scale else {})} for v in want],
        "dimensions": dims + placed,
        **({"section": section_out} if section_out else {}),
        **({"holes": holes_out} if a.get("holes") else {}),
        **({"holeTable": hole_table} if hole_table else {}),
        **({"calloutsOff": off} if a.get("holes") and off else {}),
        "titleBlock": tb,
        "techdrawPage": page_label,
        "filesFrom": frm,
        "step": len(s.steps),
    }
    out["page" if page is not None else "pageNote"] = made
    if a.get("dimensions", True):
        out["note"] = ("The drawing is the TechDraw page (edit it in TechDraw: its views, section, dimensions and title block are TechDraw's own; "
                       "page.dimensions, and any it could not place under page.notOnPage). The files are the page's exports where TechDraw can write them "
                       "(filesFrom); the rest come from Workshop's sheet writer, which also draws the hole callouts and overall sizes the page has as TechDraw dimensions.")
    return out


def _hardware(o):
    """A Fasteners Workbench part's BOM line ("ISO4762 Screw M3x12"), or
    None for a part that is made (workshop_fasteners: no Fasteners code
    needed to tell)."""
    try:
        from workshop_fasteners import api as fasteners
        from workshop_fasteners import detect

        return fasteners.bom_text(o) if detect.is_fastener(o) else None
    except Exception:  # noqa: BLE001
        return None


# ---- drawing_exploded ------------------------------------------------------------------

def drawing_exploded(s, a):
    from workshop_documents.materials import DENSITY

    steps = a.get("steps")
    if not isinstance(steps, list) or not steps or not all(isinstance(x, dict) and x.get("add") for x in steps):
        raise ToolError("invalid_input", "steps: [{ title, add: [bodies], note }], one or more, in the order they go together.")
    order, seen = [], {}
    for i, st in enumerate(steps):
        for b in st["add"]:
            o = s.body(b)
            if o.Label in seen:
                raise ToolError("invalid_input", f"steps.{i}: {o.Label} goes in at step {seen[o.Label] + 1} already — a body is added once.")
            seen[o.Label] = i
            order.append(o)
    missing = [o.Label for o in s.bodies() if o.Label not in seen]
    direction = a.get("direction", "up")
    if direction not in ("up", "out"):
        raise ToolError("invalid_input", "direction: up (each new part lifted over its place) or out (moved away from the middle).")
    bb = order[0].Shape.BoundBox
    for o in order[1:]:
        bb.add(o.Shape.BoundBox)
    explode = float(a.get("explode") or max(10.0, 0.6 * max(bb.XLength, bb.YLength, bb.ZLength)))
    mid = bb.Center

    # The bill of materials: bodies the same shape are one item.
    items, item_of = [], {}
    mats = store.materials(s.doc)
    for o in order:
        st = geo.stats(o.Shape)
        key = (st["volume"], tuple(sorted(st["box"])), st["faces"])
        hw = _hardware(o)
        if hw:  # a Fasteners Workbench part: bought hardware, one item per kind and size
            key = ("hardware", hw)
        hit = next((it for it in items if it["key"] == key), None)
        if hit is None and hw:
            hit = {"key": key, "item": len(items) + 1, "part": hw, "bodies": [], "size": [round(v, 1) for v in st["box"]],
                   "material": "", "massG": None, "madeBy": "bought", "hardware": True, "source": "Fasteners Workbench"}
            items.append(hit)
        if hit is None:
            m = mats.get(o.Label)
            setup = store.setup_of(s.doc, o.Label)
            hit = {
                "key": key,
                "item": len(items) + 1,
                "part": o.Label,
                "bodies": [],
                "size": [round(v, 1) for v in st["box"]],
                "material": material_shown(m, s.doc) if m else "",
                **({"materialId": m} if m else {}),
                "massG": round(o.Shape.Volume * DENSITY[m] / 1000.0, 1) if m in DENSITY else None,
                "madeBy": setup["type"] if setup else "",
            }
            items.append(hit)
        hit["bodies"].append(o.Label)
        item_of[o.Label] = hit["item"]

    base = _safe(a.get("name") or "assembly")
    sheet_w, sheet_h = 210.0, 148.0
    files, made_steps = [], []
    for i, st in enumerate(steps):
        new = [s.body(b) for b in st["add"]]
        before = [o for o in order if seen[o.Label] < i]
        moved = []
        for o in new:
            if direction == "up":
                off = V(0, 0, explode)
            else:
                c = o.Shape.BoundBox.Center
                d = V(c.x - mid.x, c.y - mid.y, 0)
                off = d.normalize() * explode if d.Length > 1e-6 else V(0, 0, explode)
            sh = o.Shape.copy()
            sh.translate(off)
            moved.append((o, sh, off))
        shapes = [o.Shape for o in before] + [m[1] for m in moved]
        d = views.project(shapes, "iso")
        bw, bh = d["box"][2] - d["box"][0], d["box"][3] - d["box"][1]
        scale = 0.85 * min((sheet_w - 30) / max(bw, 1e-6), (sheet_h - 36) / max(bh, 1e-6))
        sheet = sheets.Sheet(sheet_w, sheet_h, title=f"Step {i + 1}")
        centre = (sheet_w / 2, sheet_h / 2 + 4)
        sheet.place(d["lines"], d["box"], centre, scale)
        bx, by = (d["box"][0] + d["box"][2]) / 2, (d["box"][1] + d["box"][3]) / 2

        def paper(p):
            x, y = views.point(p, "iso")
            return (centre[0] + (x - bx) * scale, centre[1] - (y - by) * scale)

        for o, sh, off in moved:
            home = o.Shape.BoundBox.Center
            a0, a1 = paper(home + off), paper(home)
            sheet.line([a0, a1], "trail")
            sheet.arrow(a1, a0, 2.0)
            # A balloon with the item number, off to the upper right.
            bxy = (a0[0] + 12, a0[1] - 10)
            sheet.circle(bxy[0], bxy[1], 3.5)
            sheet.line([a0, (bxy[0] - 2.5, bxy[1] + 2.5)], "thin")
            sheet.text(bxy[0], bxy[1] + 1.2, 3.2, str(item_of[o.Label]), "middle")
        sheet.text(10, 12, 5, f"Step {i + 1}" + (f" — {st['title']}" if st.get("title") else ""))
        p = os.path.join(s.out_dir, f"{base}_step{i + 1:02d}.svg")
        with open(p, "w", encoding="utf-8") as f:
            f.write(sheet.svg())
        files.append(p)
        counts = {}
        for o in new:
            counts[item_of[o.Label]] = counts.get(item_of[o.Label], 0) + 1
        made_steps.append({"step": i + 1, "title": st.get("title", ""), "adds": [{"item": k, "part": items[k - 1]["part"], "qty": n} for k, n in counts.items()], "svg": p})

    md = [f"# {a.get('title') or a.get('name') or 'Assembly'}", ""]
    md += ["## Bill of materials", "", "| Item | Part | Qty | Size (mm) | Material | Mass (g) | Made by |", "|---|---|---|---|---|---|---|"]
    for it in items:
        md.append(f"| {it['item']} | {it['part']} | {len(it['bodies'])} | {' x '.join(_num(v) for v in it['size'])} | {it['material'] or '—'} | {it['massG'] if it['massG'] is not None else '—'} | {it['madeBy'] or '—'} |")
    md.append("")
    for ms, st in zip(made_steps, steps):
        md += [f"## Step {ms['step']}" + (f" — {ms['title']}" if ms["title"] else ""), "", f"![Step {ms['step']}]({os.path.basename(ms['svg'])})", ""]
        md.append("Add " + ", ".join(f"{x['qty']} x {x['part']} (item {x['item']})" for x in ms["adds"]) + ".")
        if st.get("note"):
            md += ["", st["note"]]
        md.append("")
    mp = os.path.join(s.out_dir, f"{base}_assembly.md")
    with open(mp, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    out = {
        "manual": mp,
        "steps": made_steps,
        "bom": [{k: v for k, v in it.items() if k != "key"} for it in items],
        "explode": round(explode, 1),
    }
    if missing:
        out["notInAnyStep"] = missing
    # Each part is lifted over where it is in the document: one lying
    # apart from everything before it (printed beside the box, say) is
    # lifted over the wrong place, and the arrow points at nothing.
    apart = []
    for o in order:
        prior = [p for p in order if seen[p.Label] < seen[o.Label]]
        if not prior:
            continue
        b = o.Shape.BoundBox
        if not any(b.XMin < p.Shape.BoundBox.XMax and p.Shape.BoundBox.XMin < b.XMax and b.YMin < p.Shape.BoundBox.YMax and p.Shape.BoundBox.YMin < b.YMax for p in prior):
            apart.append(o.Label)
    if apart:
        out["warnings"] = [f"{', '.join(apart)} lie apart from the parts before them, not where they go: each part is lifted over its place in the document, so put them there first (object_set Placement — a lid printed top down turns over about X), then again. view_render shows where they are."]
    out.update(_exploded_in_assembly(s, a, steps, order, seen, explode, direction, mid, item_of, items))
    return out


OWN_ROUTE = "Workshop's own exploded shapes"


def _exploded_in_assembly(s, a, steps, order, seen, explode, direction, mid, item_of, items):
    """Where the parts are in a FreeCAD Assembly: the whole manual as its own
    Exploded View (step k's parts moved k − 1 explode lengths up, or out
    from the middle from step 2 on), editable in the Assembly, and an
    ordinary TechDraw page of it with a balloon an item and the bill of
    materials. Else the step pictures stand alone, and the answer says so."""
    asm = fcexplode.assembly_of(s.doc, order)
    if asm is None:
        return {"route": OWN_ROUTE, "routeNote": "The parts are in no FreeCAD Assembly, so the steps are drawn from Workshop's own exploded shapes; put them in an Assembly for its own Exploded View, editable there."}
    offsets, by_label, labels = {}, {}, []
    for o in order:
        k = seen[o.Label]
        by_label[o.Label] = o
        if direction == "up":
            off = (0.0, 0.0, explode * k)
        else:
            c = o.Shape.BoundBox.Center
            d = V(c.x - mid.x, c.y - mid.y, 0)
            u = d.normalize() * explode if d.Length > 1e-6 else V(0, 0, explode)
            off = (u.x, u.y, u.z) if k else (0.0, 0.0, 0.0)
        offsets[o.Label] = off
    labels = [[s.body(b).Label for b in st["add"]] for st in steps]
    moves = [m for m in fcexplode.plan(labels, offsets) if any(abs(x) > 1e-9 for x in m[2])]
    title = a.get("title") or a.get("name") or "Assembly"
    view, why = fcexplode.make_view(s.doc, asm, moves, by_label, f"{title} exploded")
    if view is None:
        return {"route": OWN_ROUTE, "routeNote": why}
    out = {"route": "FreeCAD Assembly Exploded View", "explodedView": view.Label, "assembly": asm.Label, "moves": len(moves)}
    if not a.get("page", True):
        return out
    try:
        moved = []
        for o in order:
            sh = o.Shape.copy()
            sh.translate(V(*offsets[o.Label]))
            moved.append(sh)
        bb = _shapes_box(moved)
        W, H = sheets.PAPER["A4"]
        d = views.project(moved, "iso")
        bw, bh = d["box"][2] - d["box"][0], d["box"][3] - d["box"][1]
        fit = min((W - 120) / max(bw, 1e-6), (H - 90) / max(bh, 1e-6))
        scale = next((x for x in sheets.SCALES if x <= fit), sheets.SCALES[-1])
        page = _page(s.doc, f"{title} exploded", "A4")
        v = _view(s.doc, page, [view], "iso", scale, (W - 90) / 2, (H - 45) / 2, "Exploded")
        _wait_views([v])
        done = set()
        for o in order:
            it = item_of[o.Label]
            if it in done:
                continue
            done.add(it)
            p3 = o.Shape.BoundBox.Center + V(*offsets[o.Label])
            origin, at = balloon_at(p3, bb.Center, "iso", scale, (14, 12))
            _balloon(s.doc, page, v, origin, at, it)
        rows = ["ITEM   PART   QTY"] + [f"{it['item']}   {it['part']}   {len(it['bodies'])}" for it in items]
        _note(s.doc, page, rows, W - 80, 20)
        s.doc.recompute()
        out["page"] = page.Label
    except Exception as e:  # noqa: BLE001 — the Exploded View stands without it
        out["pageNote"] = f"the TechDraw page could not be made here ({e})"
    return out


# ---- patent_figures --------------------------------------------------------------------

def patent_figures(s, a):
    objs = _bodies(s, a.get("bodies"))
    want = a.get("views") or ["iso", "front", "top", "right"]
    bad = [v for v in want if v not in views.VIEWS]
    if bad:
        raise ToolError("invalid_input", f"views: {bad[0]} is not one — they are: {', '.join(views.VIEWS)}.")
    given = a.get("numerals") or {}
    numerals = {}
    step = 10 if len(objs) <= 9 else 2
    n = 10
    for o in objs:
        g = given.get(o.Label)
        if g is not None:
            if not isinstance(g, int) or g <= 0:
                raise ToolError("invalid_input", f"numerals.{o.Label}: a whole number over 0.")
            numerals[o.Label] = g
    used = set(numerals.values())
    if len(used) != len(numerals):
        raise ToolError("invalid_input", "numerals: each part its own number.")
    for o in objs:
        if o.Label not in numerals:
            while n in used:
                n += step
            numerals[o.Label] = n
            used.add(n)
    unknown = [k for k in given if k not in numerals]
    if unknown:
        raise ToolError("not_found", f"numerals: {unknown[0]} is not among the bodies drawn — {', '.join(numerals)}.")
    base = _safe(a.get("name") or "patent")
    # 37 CFR 1.84 margins on A4: top 2.5 cm, left 2.5, right 1.5, bottom 1.0.
    W, H = sheets.PAPER["A4P"]
    left, top, right, bottom = 25.0, 25.0, 15.0, 10.0
    aw, ah = W - left - right, H - top - bottom - 20
    figs, unseen = [], {}
    shapes = [o.Shape for o in objs]
    for k, v in enumerate(want, 1):
        d = views.project(shapes, v)
        bw, bh = d["box"][2] - d["box"][0], d["box"][3] - d["box"][1]
        scale = min((aw - 60) / max(bw, 1e-6), (ah - 60) / max(bh, 1e-6))
        centre = (left + aw / 2, top + ah / 2)
        sheet = sheets.Sheet(W, H, title=f"FIG. {k}")
        sheet.place([(kk, pts) for (kk, pts) in d["lines"] if kk == "visible"], d["box"], centre, scale)
        bx, by = (d["box"][0] + d["box"][2]) / 2, (d["box"][1] + d["box"][3]) / 2
        half_w, half_h = bw * scale / 2, bh * scale / 2
        labels = []
        for o in objs:
            others = [x.Shape for x in objs if x is not o]
            p = views.visible_point(o.Shape, others, v)
            if p is None:
                unseen.setdefault(o.Label, []).append(k)
                continue
            x, y = views.point(p, v)
            px, py = centre[0] + (x - bx) * scale, centre[1] - (y - by) * scale
            ang = math.atan2(py - centre[1], px - centre[0])
            for _ in range(24):
                # Out along the line from the middle through the point, past the view's box.
                ux, uy = math.cos(ang), math.sin(ang)
                t = min(((half_w + 14) / abs(ux)) if abs(ux) > 1e-9 else 1e9, ((half_h + 14) / abs(uy)) if abs(uy) > 1e-9 else 1e9)
                lx, ly = centre[0] + ux * t, centre[1] + uy * t
                if all(math.hypot(lx - qx, ly - qy) > 9 for (qx, qy) in labels):
                    break
                ang += math.radians(9)
            labels.append((lx, ly))
            sheet.text(lx, ly + 1.75, 3.5, str(numerals[o.Label]), "middle")
            dx, dy = px - lx, py - ly
            dl = math.hypot(dx, dy) or 1.0
            sheet.line([(lx + dx / dl * 3.5, ly + dy / dl * 3.5), (px, py)], "thin")
        sheet.text(centre[0], H - bottom - 8, 6, f"FIG. {k}", "middle")
        fp = os.path.join(s.out_dir, f"{base}_fig{k}")
        fig = {"fig": k, "view": v}
        got, frm = {}, {}
        if a.get("page", True):
            pg, note = _patent_page(s, objs, shapes, v, k, scale, centre, numerals, f"{a.get('name') or 'Patent'} FIG. {k}")
            if pg is not None:
                fig["page"] = pg.Label
                got, why = _export_page(pg, s.out_dir, os.path.basename(fp), ("pdf", "svg"))
                frm = {kk: "TechDraw page" for kk in got}
                frm.update({kk: f"Workshop's sheet writer: {w}" for kk, w in why.items()})
            else:
                fig["pageNote"] = note
        if "svg" not in got:
            with open(fp + ".svg", "w", encoding="utf-8") as f:
                f.write(sheet.svg())
            frm.setdefault("svg", "Workshop's sheet writer: no TechDraw page")
        if "pdf" not in got:
            with open(fp + ".pdf", "wb") as f:
                f.write(sheet.pdf())
            frm.setdefault("pdf", "Workshop's sheet writer: no TechDraw page")
        fig.update({"svg": fp + ".svg", "pdf": fp + ".pdf", "filesFrom": frm})
        figs.append(fig)
    lines = [f"# Reference numerals — {a.get('name') or 'figures'}", ""]
    lines += [f"- FIG. {f['fig']} is {views.WORDS[f['view']]}." for f in figs]
    lines += [""] + [f"- {num} — {lbl}" for lbl, num in sorted(numerals.items(), key=lambda t: t[1])]
    np_ = os.path.join(s.out_dir, f"{base}_numerals.md")
    with open(np_, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    s._patent = {"name": a.get("name"), "numerals": numerals, "figures": [{"fig": f["fig"], "view": f["view"]} for f in figs]}
    out = {"figures": figs, "numerals": numerals, "list": np_, "note": "Black line art, no shading or hidden lines, on A4 within the USPTO's margins; numerals 3.5 mm high with lead lines to a face of each part. "
           "Each figure is an ordinary TechDraw page (page), its numerals TechDraw balloons with no bubble, editable in TechDraw; the files are its exports where TechDraw can write them (filesFrom)."}
    if unseen:
        out["notSeenIn"] = unseen
    return out


def _patent_page(s, objs, shapes, view, k, scale, centre, numerals, label):
    """FIG. k as an ordinary TechDraw page in patent style: A4 portrait,
    TechDraw's blank template (no title block), visible lines only, each
    part's numeral a TechDraw balloon with no bubble and no arrowhead, the
    figure's label a TechDraw annotation, inside the 37 CFR 1.84 margins the
    files keep. (page, None) or (None, why not)."""
    try:
        W, H = sheets.PAPER["A4P"]
        page = _page(s.doc, label, "A4P", blank=True)
        v = _view(s.doc, page, objs, view, scale, centre[0], centre[1], f"FIG. {k}", line_art=True)
        _wait_views([v])
        c3 = _shapes_box(shapes).Center
        for o in objs:
            others = [x.Shape for x in objs if x is not o]
            p = views.visible_point(o.Shape, others, view)
            if p is None:
                continue
            px, py = views.point(p, view)
            cx, cy = views.point(c3, view)
            ang = math.atan2(py - cy, px - cx)
            origin, at = balloon_at(p, c3, view, scale, (14 * math.cos(ang), 14 * math.sin(ang)))
            _balloon(s.doc, page, v, origin, at, numerals[o.Label], plain=True)
        _note(s.doc, page, [f"FIG. {k}"], centre[0], H - 10.0 - 8, size=6)
        s.doc.recompute()
        return page, None
    except Exception as e:  # noqa: BLE001 — the files stand without it
        return None, f"the TechDraw page could not be made here ({e})"


# ---- patent_draft ----------------------------------------------------------------------

def patent_draft(s, a):
    title = a.get("title")
    if not title:
        raise ToolError("invalid_input", "title: what the invention is, a few words.")
    pat = getattr(s, "_patent", None)
    objs = _bodies(s, a.get("bodies") or (list(pat["numerals"]) if pat else None))
    numerals = dict(pat["numerals"]) if pat else {}
    n = max(numerals.values(), default=0)
    for o in objs:
        if o.Label not in numerals:
            n += 10
            numerals[o.Label] = n
    figs = pat["figures"] if pat else []
    name = lambda o: o.Label.lower()  # noqa: E731
    touch = []
    for i, o1 in enumerate(objs):
        for o2 in objs[i + 1:]:
            try:
                if o1.Shape.distToShape(o2.Shape)[0] < 0.05:
                    touch.append((o1, o2))
            except Exception:  # a pair the distance cannot be read for: not claimed to touch
                pass
    bb = objs[0].Shape.BoundBox
    for o in objs[1:]:
        bb.add(o.Shape.BoundBox)
    md = [
        "> **DRAFT — NOT FOR FILING.** A starting point for review by a registered patent attorney or agent. "
        "It has not been filed, sent or searched against prior art, and nothing in it is legal advice. "
        "Every bracketed passage is to be written or checked with counsel.",
        "",
        f"# {title}",
        "",
        "## Cross-reference to related applications",
        "",
        "[None, or the provisional application this claims the benefit of.]",
        "",
        "## Field",
        "",
        a.get("field") or "[The technical field, one sentence.]",
        "",
        "## Background",
        "",
        a.get("background") or "[The problem, and how it is met today — without admitting anything is prior art.]",
        "",
        "## Summary",
        "",
        "[A short statement of the invention, following claim 1 once the claims are settled.]",
        "",
        "## Brief description of the drawings",
        "",
    ]
    if figs:
        md += [f"FIG. {f['fig']} is {views.WORDS[f['view']]} of the {title.lower()}." for f in figs]
    else:
        md.append("[No figures yet: patent_figures makes them, with the numerals used here.]")
    md += ["", "## Detailed description", ""]
    md.append(f"Referring to the figures, the {title.lower()} comprises " + ", ".join(f"a {name(o)} {numerals[o.Label]}" for o in objs) + ".")
    md.append("")
    for o in objs:
        b = o.Shape.BoundBox
        mat = store.materials(s.doc).get(o.Label)
        md.append(
            f"The {name(o)} {numerals[o.Label]} measures about {_num(b.XLength)} mm by {_num(b.YLength)} mm by {_num(b.ZLength)} mm"
            + (f" and may be made of {material_shown(mat, s.doc)}" if mat else "")
            + ". [What it does, and how.]"
        )
    for o1, o2 in touch:
        md.append(f"The {name(o1)} {numerals[o1.Label]} adjoins the {name(o2)} {numerals[o2.Label]}. [How they are joined or how one moves against the other.]")
    md += [
        "",
        f"Overall the {title.lower()} measures about {_num(bb.XLength)} mm by {_num(bb.YLength)} mm by {_num(bb.ZLength)} mm. "
        "The sizes are of the embodiment drawn; [say which are not limiting].",
        "",
        "## Claims (skeleton)",
        "",
        f"1. A {title.lower()}, comprising:",
    ]
    for i, o in enumerate(objs):
        rel = next((f" adjoining the {name(p)}" for (q, p) in touch if q is o), "")
        md.append(f"   a {name(o)}{rel};" if i < len(objs) - 1 else f"   a {name(o)}{rel}; and")
    md.append("   [wherein — the feature that sets it apart, to be written with counsel].")
    md.append("")
    for i, o in enumerate(objs[:3], 2):
        md.append(f"{i}. The {title.lower()} of claim 1, wherein the {name(o)} [a narrower feature: a size, a material, a shape].")
        md.append("")
    md += ["## Abstract", "", "[At most 150 words, written last.]", ""]
    md.append("Reference numerals: " + "; ".join(f"{numerals[o.Label]} {name(o)}" for o in objs) + ".")
    p = os.path.join(s.out_dir, f"{_safe(a.get('name') or title)}_patent_draft.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    return {"draft": p, "numerals": numerals, "figures": len(figs), "adjoining": [[o1.Label, o2.Label] for o1, o2 in touch], "note": "A draft for an attorney's review, written to the output folder only — nothing is filed or sent."}


HANDLERS = {
    "drawing_make": drawing_make,
    "drawing_exploded": drawing_exploded,
    "patent_figures": patent_figures,
    "patent_draft": patent_draft,
}
