# SPDX-License-Identifier: LGPL-2.1-or-later
# This add-on's own copy; it was AddonKit's addonkit.ui.form, retired 14 Nov 2026.
# A dialog built from a parameter table ({name: {kind, min, max, default,
# values, tip}}), the same tables the add-ons check an agent's values
# against: one field per parameter, its range and tip shown. The person's
# way into the same function an agent calls.


def ask(title, table, intro=""):
    """The values chosen, or None when cancelled."""
    from PySide import QtGui

    try:
        QtWidgets = QtGui.QtWidgets if hasattr(QtGui, "QtWidgets") else QtGui
    except Exception:
        QtWidgets = QtGui
    import FreeCADGui

    dlg = QtWidgets.QDialog(FreeCADGui.getMainWindow())
    dlg.setWindowTitle(title)
    lay = QtWidgets.QFormLayout(dlg)
    if intro:
        lab = QtWidgets.QLabel(intro)
        lab.setWordWrap(True)
        lay.addRow(lab)
    fields = {}
    for k, spec in table.items():
        kind, d = spec.get("kind"), spec.get("default")
        if kind == "bool":
            w = QtWidgets.QCheckBox()
            w.setChecked(bool(d))
        elif kind == "enum":
            w = QtWidgets.QComboBox()
            w.addItems([str(v) for v in spec["values"]])
            if d in spec["values"]:
                w.setCurrentIndex(list(spec["values"]).index(d))
        elif kind == "int":
            w = QtWidgets.QSpinBox()
            w.setRange(int(spec["min"]), int(spec["max"]))
            w.setValue(int(d if d is not None else spec["min"]))
        elif kind == "num":
            w = QtWidgets.QDoubleSpinBox()
            w.setDecimals(2)
            w.setRange(float(spec["min"]), float(spec["max"]))
            w.setValue(float(d if d is not None else spec["min"]))
            w.setSuffix(" mm" if "mm" in (spec.get("tip") or "") else "")
        else:
            continue
        if spec.get("tip"):
            w.setToolTip(spec["tip"])
        lay.addRow(k, w)
        fields[k] = (kind, w, spec)
    bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addRow(bb)
    if not dlg.exec_():
        return None
    out = {}
    for k, (kind, w, spec) in fields.items():
        if kind == "bool":
            out[k] = w.isChecked()
        elif kind == "enum":
            out[k] = list(spec["values"])[w.currentIndex()]
        else:
            out[k] = w.value()
    return out
