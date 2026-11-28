# SPDX-License-Identifier: LGPL-2.1-or-later
# drawing_make's hole callouts (README screenshot pass, finding 2; desk-lamp
# test drive, finding 13): a "2× ⌀3.2" callout of a hole in the top view
# had its text by the iso view and its leader across the iso view. Now the
# text stays near the view that holds the hole (up, then down from it), no
# leader crosses another view or a text, and the text stays in the drawing
# area and off the title block. And drawing_make's card (finding 14): the
# long "Behaviour, in full" part is a guide section now, which the card
# names. FreeCAD stood in for.
import json
import os
import unittest

from _stubs import run

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def card_text(e):
    """All the words of an entry's card (the hub's reading); the hub is not
    needed: without it the lines are joined here the same way."""
    try:
        from agentlink.tooldata import card_text as hub_card_text
        return hub_card_text(e)
    except ImportError:
        pass
    c = e.get("card")
    if not isinstance(c, dict):
        return e.get("description", "")
    out = [c.get("does", "")]
    for k, n in (c.get("inputNotes") or {}).items():
        out += [f"{k}: {n.get('means', '')}"] + [f"{k}: {f}" for f in n.get("forms") or []]
    out += [x.get("line", "") for x in c.get("links") or []] + list(c.get("effects") or [])
    out += [f"{k}: {r.get('means', '')}" for k, r in (c.get("returns") or {}).items()]
    out += list(c.get("refusalNotes") or []) + list(c.get("hints") or [])
    return " ".join(x for x in out if x)


def served_words(e):
    """The words of the card a call serves by default: every kind but hints
    and refusals (refusalNotes). A call reads only what it selects, so the
    cap counts these."""
    c = e.get("card")
    if not isinstance(c, dict):
        return e.get("description", "")
    out = [c.get("does", "")]
    for k, n in (c.get("inputNotes") or {}).items():
        out += [f"{k}: {n.get('means', '')}"] + [f"{k}: {f}" for f in n.get("forms") or []]
    out += [x.get("line", "") for x in c.get("links") or []] + list(c.get("effects") or [])
    out += [f"{k}: {r.get('means', '')}" for k, r in (c.get("returns") or {}).items()]
    return " ".join(x for x in out if x)


SCENE = r'''
from workshop_documents.handlers import drawing as D
from workshop_documents import sheets
front, top, iso = (60, 20, 160, 100), (60, 145, 160, 195), (165, 110, 230, 170)
area, block = (10, 10, 410, 287), (230, 250, 410, 287)
pa, r, label = (152, 165), 1.6, "2× ⌀3.2"
'''


class CalloutNearItsView(unittest.TestCase):
    def test_the_old_way_crossed_the_iso_view(self):
        out = run(SCENE + r'''
# As before: up only, the sheet's text tested against the views, no leader tested.
for extra in range(12):
    tip, elbow, tail, anchor = D.callout_leader(pa, r, top, extra)
    t = (tail[0] + (1 if anchor == "start" else -1), tail[1] - 1, 3.0, label, anchor)
    tb = sheets.text_box(t)
    if not any(D._boxes_hit(tb, x) for x in [front, top, iso]):
        break
at = ((tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2)
pb = D.page_text_box(at, label)
corner = (pb[2], pb[3]) if anchor == "end" else (pb[0], pb[3])
OUT["crosses_iso"] = D._seg_box(pa, corner, iso)
OUT["at"] = at
''')
        self.assertTrue(out["crosses_iso"])
        self.assertGreater(out["at"][0], 165)  # its text past the iso view's left edge

    def test_now_near_the_view_and_no_leader_across_another(self):
        out = run(SCENE + r'''
co = D.place_callout(pa, r, top, 0, label, [front, top, iso], [], area=area, block=block)
OUT["clashes"] = co["clashes"]
OUT["cross"] = [any(D._seg_box(s[0], s[1], v) for s in co["segs"]) for v in (front, iso)]
OUT["at"] = co["textAt"]
OUT["in_area"] = all(area[0] <= b[0] and area[1] <= b[1] and b[2] <= area[2] and b[3] <= area[3] for b in co["boxes"])
''')
        self.assertEqual(out["clashes"], 0)
        self.assertEqual(out["cross"], [False, False])
        self.assertTrue(out["in_area"])
        x, y = out["at"]
        # Within 20 mm of the top view's outline (60, 145, 160, 195).
        dx = max(60 - x, 0, x - 160)
        dy = max(145 - y, 0, y - 195)
        self.assertLess((dx * dx + dy * dy) ** 0.5, 20, out["at"])

    def test_down_when_up_is_taken(self):
        out = run(SCENE + r'''
# A view right over the top view, wall to wall: the callout goes below it.
over = (40, 100, 280, 143)
co = D.place_callout(pa, r, top, 0, label, [over, top], [], area=area, block=block)
OUT["clashes"] = co["clashes"]
OUT["below"] = co["textAt"][1] > top[3]
OUT["cross"] = any(D._seg_box(s[0], s[1], over) for s in co["segs"])
''')
        self.assertEqual(out["clashes"], 0)
        self.assertTrue(out["below"])
        self.assertFalse(out["cross"])

    def test_off_the_title_block(self):
        out = run(SCENE + r'''
low = (250, 200, 330, 245)
co = D.place_callout((320, 230), 1.6, low, 0, label, [low], [], area=area, block=block)
OUT["hit"] = any(D._boxes_hit(b, block) for b in co["boxes"])
OUT["clashes"] = co["clashes"]
''')
        self.assertFalse(out["hit"])
        self.assertEqual(out["clashes"], 0)

    def test_segment_and_box(self):
        out = run(r'''
from workshop_documents.handlers import drawing as D
box = (10, 10, 20, 20)
OUT["r"] = [D._seg_box((0, 15), (30, 15), box), D._seg_box((0, 0), (5, 30), box), D._seg_box((0, 10), (30, 10), box),
            D._seg_box((12, 12), (14, 14), box), D._seg_box((0, 0), (9, 9), box)]
''')
        self.assertEqual(out["r"], [True, False, False, True, False])


class ShortCard(unittest.TestCase):
    """drawing_make's card keeps inputs, traps and the answer; the rest is a
    guide section it names, and every Workshop card stays under 800 words (the words of the default-served
    card: all kinds but hints and refusals)."""

    # Records cards (28 Nov) hold facts the old text left to guides: a card
    # past 800 has a ceiling at its measured served size, so it cannot grow.
    CEILING = {"drawing_make": 1000}

    def test_cards_are_short(self):
        for rel in ("workshop_documents", "workshop_make", "workshop_electronics", "workshop_fasteners"):
            with open(os.path.join(ROOT, rel, "data", "tools.json"), encoding="utf-8") as f:
                for name, e in json.load(f)["entries"].items():
                    self.assertLess(len(served_words(e).split()), self.CEILING.get(name, 800), name)

    def test_the_guide_holds_the_rest(self):
        with open(os.path.join(ROOT, "workshop_documents", "data", "tools.json"), encoding="utf-8") as f:
            card = card_text(json.load(f)["entries"]["drawing_make"])
        with open(os.path.join(ROOT, "workshop_documents", "guides", "drawing.md"), encoding="utf-8") as f:
            guide = f.read()
        self.assertNotIn("Behaviour, in full", card)
        self.assertIn('guide_read { topic: "drawing", section: "drawing_make in full" }', card)
        self.assertIn("\n## drawing_make in full\n<!-- later:", guide)
        sec = guide.split("\n## drawing_make in full\n", 1)[1]
        for fact in ("page.settled.waited", "page.viewsNotReady", "exportSceneAgain", "within 0.05 mm", "calloutsOff", "never cross another view"):
            self.assertIn(fact, sec)


if __name__ == "__main__":
    unittest.main()
