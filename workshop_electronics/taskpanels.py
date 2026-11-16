# SPDX-License-Identifier: LGPL-2.1-or-later
"""Electronics' task panels (FreeCADGui.Control.showDialog), so its forms sit
in the Tasks tab like FreeCAD's own tools rather than in a modal dialog.
KiCad board: the .kicad_pcb's path (typed, or Browse… for the file picker),
a live line saying what the board is, OK reads it into the document (one
undo step: the panel's transaction), Cancel aborts it."""

import os


def _qt():
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide import QtGui as QtWidgets
    return QtWidgets


def describe(board):
    """One line for a board read: its name, size, layers and holes."""
    w, h = board.get("size") or (0, 0)
    return (f"{board.get('title') or board.get('source') or 'Board'}: {w:g} × {h:g} mm, "
            f"{board.get('thickness', 0):g} mm thick, {board.get('copperLayers', 2)} copper layers, "
            f"{len(board.get('holes') or [])} holes, {len(board.get('footprints') or [])} footprints")


def look(path):
    """(the board or None, the live line) for a path as typed so far."""
    from .refusal import Refused
    from . import api

    path = (path or "").strip()
    if not path:
        return None, "Pick a KiCad board (.kicad_pcb, KiCad 5 to 9; KiCad not needed)."
    if not os.path.isfile(os.path.expanduser(path)):
        return None, "Not a file yet."
    try:
        b = api.read_board(path)
    except (Refused, ValueError) as e:
        return None, getattr(e, "message", str(e))
    return b, describe(b)


class ImportBoardPanel:
    """The KiCad board panel. doc: where the board goes; its transaction is
    opened with the panel."""

    TITLE = "KiCad Board"

    def __init__(self, doc=None, path="", qt=None):
        from workshop import narrow

        Q = qt or _qt()
        self.doc = doc
        self.form = Q.QWidget()
        self.form.setWindowTitle(self.TITLE)
        lay = narrow.form(Q.QFormLayout(self.form))
        row = Q.QWidget()
        h = Q.QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        self.path = narrow.grow(Q.QLineEdit())
        self.path.setText(path)
        self.browse = Q.QPushButton("Browse…")
        h.addWidget(self.path)
        h.addWidget(self.browse)
        lay.addRow("Board file", row)
        self.line = Q.QLabel("")
        self.line.setWordWrap(True)
        lay.addRow(self.line)
        self.msg = Q.QLabel("")
        self.msg.setWordWrap(True)
        lay.addRow(self.msg)
        for w, sig, fn in ((self.path, "textChanged", self.update), (self.browse, "clicked", self.pick)):
            try:
                getattr(w, sig).connect(fn)
            except Exception:
                pass
        self.Q = Q
        if doc is not None:
            doc.openTransaction(self.TITLE)
        self.update()

    def update(self, *_a):
        self.board, text = look(self.path.text())
        self.line.setText(text)

    def pick(self, *_a):
        got = self.Q.QFileDialog.getOpenFileName(self.form, self.TITLE, os.path.dirname(self.path.text().strip()), "KiCad board (*.kicad_pcb)")
        path = got[0] if isinstance(got, (tuple, list)) else got
        if path:
            self.path.setText(path)
            self.update()

    def run(self):
        """(ok, what to say): the board read into the document."""
        import FreeCAD

        from . import api

        if self.board is None:
            return False, self.line.text()
        doc = self.doc or FreeCAD.ActiveDocument or FreeCAD.newDocument()
        try:
            o = api.add_board(doc, self.board)
        except ValueError as e:
            return False, str(e)
        FreeCAD.Console.PrintMessage(f"Workshop: read {o.Label}.\n")
        try:
            import FreeCADGui

            FreeCADGui.SendMsgToActiveView("ViewFit")
        except Exception:
            pass
        return True, ""

    def _close(self):
        try:
            import FreeCADGui

            FreeCADGui.Control.closeDialog()
        except Exception:
            pass

    def accept(self):
        ok, message = self.run()
        if not ok:
            self.msg.setText(message or "Refused.")
            return False
        if self.doc is not None:
            self.doc.commitTransaction()
        self._close()
        return True

    def reject(self):
        if self.doc is not None:
            self.doc.abortTransaction()
        self._close()
        return True


BUSY = "Finish or cancel the open task first."


def busy():
    """True (and the person told) when a task panel is open already: as
    FreeCAD's own commands do, a new one is refused rather than replacing
    it."""
    import FreeCADGui

    if not FreeCADGui.Control.activeDialog():
        return False
    try:
        _qt().QMessageBox.information(FreeCADGui.getMainWindow(), "Workshop Electronics", BUSY)
    except Exception:
        pass
    return True


def show_import_board(doc):
    import FreeCADGui

    if busy():
        return None
    panel = ImportBoardPanel(doc)
    FreeCADGui.Control.showDialog(panel)
    return panel
