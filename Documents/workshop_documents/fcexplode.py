# SPDX-License-Identifier: LGPL-2.1-or-later
"""Exploded Drawing on FreeCAD 1.x Assembly's own Exploded View: where the
parts are in an Assembly, the manual's moves become an Exploded View in it
(Assembly_CreateView's objects: an "Exploded View" in the assembly's view
group, a "Move" step each, MoveType Normal with its MovementTransform),
editable there; its exploded shape is what the TechDraw page shows.
Outside an Assembly drawing_exploded keeps its own exploded shapes and
says so.

The planning is pure Python (tested without FreeCAD); the FreeCAD side is
guarded and gives (None, why) instead of failing the manual."""

ASSEMBLY = "Assembly::AssemblyObject"


def linked(o):
    """What o stands for: a Link's linked object, else o."""
    try:
        if getattr(o, "TypeId", "") == "App::Link" or hasattr(o, "LinkedObject"):
            t = o.LinkedObject
            if t is not None:
                return t
    except Exception:  # noqa: BLE001
        pass
    return o


def children(asm):
    """The objects directly in an assembly (parts, links, joint groups)."""
    try:
        return list(asm.Group)
    except Exception:  # noqa: BLE001
        return []


def child_for(asm, body):
    """The assembly's own child that is body or links to it, else None."""
    for c in children(asm):
        if c is body or linked(c) is body:
            return c
    return None


def assembly_of(doc, bodies):
    """The one Assembly holding every body (as itself or a link), else None."""
    try:
        asms = [o for o in doc.Objects if getattr(o, "TypeId", "") == ASSEMBLY]
    except Exception:  # noqa: BLE001
        return None
    for a in asms:
        if all(child_for(a, b) is not None for b in bodies):
            return a
    return None


def plan(steps, offsets):
    """The Exploded View's moves: [(step number, [labels], (dx, dy, dz))],
    one a step when its parts move alike (up), else one a part (out).
    steps: [[labels]]; offsets: {label: (dx, dy, dz)}."""
    out = []
    for i, labels in enumerate(steps, 1):
        by = {}
        for lb in labels:
            off = tuple(round(float(x), 6) for x in offsets[lb])
            by.setdefault(off, []).append(lb)
        for off, lbs in by.items():
            out.append((i, lbs, off))
    return out


def make_view(doc, asm, moves, by_label, name="Exploded View"):
    """FreeCAD's own Exploded View in asm with the moves (plan()'s; by_label:
    {label: body}). (the view object, None) or (None, why not); nothing is
    left behind when it fails."""
    made = []
    try:
        import FreeCAD
        import CommandCreateView as CCV
        import UtilsAssembly as UA

        group = UA.getViewGroup(asm)
        view = group.newObject("App::FeaturePython", name)
        made.append(view)
        CCV.ExplodedView(view)
        if getattr(FreeCAD, "GuiUp", False):
            try:
                CCV.ViewProviderExplodedView(view.ViewObject)
            except Exception:  # noqa: BLE001
                pass
        steps = []
        for _i, labels, off in moves:
            mv = asm.newObject("App::FeaturePython", "Move")
            made.append(mv)
            CCV.ExplodedViewStep(mv, 0)
            if getattr(FreeCAD, "GuiUp", False):
                try:
                    CCV.ViewProviderExplodedViewStep(mv.ViewObject)
                except Exception:  # noqa: BLE001
                    pass
            mv.References = [asm, [child_for(asm, by_label[lb]).Name + "." for lb in labels]]
            mv.MovementTransform = FreeCAD.Placement(FreeCAD.Vector(*off), FreeCAD.Rotation())
            steps.append(mv)
        view.Group = steps
        doc.recompute()
        return view, None
    except Exception as e:  # noqa: BLE001
        for o in reversed(made):
            try:
                doc.removeObject(o.Name)
            except Exception:  # noqa: BLE001
                pass
        return None, f"FreeCAD's Exploded View could not be made here ({e})"


def exploded_shape(view):
    """The view's exploded shape (FreeCAD's getExplodedShape), or None."""
    try:
        return view.Proxy.getExplodedShape(view)
    except Exception:  # noqa: BLE001
        return None
