# SPDX-License-Identifier: LGPL-2.1-or-later
# A stand-in for FreeCAD's PartDesign Hole thread tables (threads.use()),
# for tests where FreeCAD is not: (series, designation, major, tap drill),
# as read_freecad answers them. Test data only; Make reads FreeCAD's own.
ROWS = [
    ('metric', 'M1.6x0.35', 1.6, 1.25),
    ('metric', 'M2x0.4', 2.0, 1.6),
    ('metric', 'M2.5x0.45', 2.5, 2.05),
    ('metric', 'M3x0.5', 3.0, 2.5),
    ('metric', 'M3.5x0.6', 3.5, 2.9),
    ('metric', 'M4x0.7', 4.0, 3.3),
    ('metric', 'M5x0.8', 5.0, 4.2),
    ('metric', 'M6x1.0', 6.0, 5.0),
    ('metric', 'M8x1.25', 8.0, 6.8),
    ('metric', 'M10x1.5', 10.0, 8.5),
    ('metric', 'M12x1.75', 12.0, 10.2),
    ('metric', 'M14x2.0', 14.0, 12.0),
    ('metric', 'M16x2.0', 16.0, 14.0),
    ('metric', 'M18x2.5', 18.0, 15.5),
    ('metric', 'M20x2.5', 20.0, 17.5),
    ('metric', 'M22x2.5', 22.0, 19.5),
    ('metric', 'M24x3.0', 24.0, 21.0),
    ('metric-fine', 'M3x0.35', 3.0, 2.65),
    ('metric-fine', 'M4x0.5', 4.0, 3.5),
    ('metric-fine', 'M5x0.5', 5.0, 4.5),
    ('metric-fine', 'M6x0.75', 6.0, 5.25),
    ('metric-fine', 'M8x1.0', 8.0, 7.0),
    ('metric-fine', 'M10x1.25', 10.0, 8.75),
    ('metric-fine', 'M10x1.0', 10.0, 9.0),
    ('metric-fine', 'M12x1.5', 12.0, 10.5),
    ('metric-fine', 'M12x1.25', 12.0, 10.75),
    ('metric-fine', 'M14x1.5', 14.0, 12.5),
    ('metric-fine', 'M16x1.5', 16.0, 14.5),
    ('metric-fine', 'M18x1.5', 18.0, 16.5),
    ('metric-fine', 'M18x2.0', 18.0, 16.0),
    ('metric-fine', 'M20x1.5', 20.0, 18.5),
    ('metric-fine', 'M20x2.0', 20.0, 18.0),
    ('metric-fine', 'M22x1.5', 22.0, 20.5),
    ('metric-fine', 'M22x2.0', 22.0, 20.0),
    ('metric-fine', 'M24x2.0', 24.0, 22.0),
    ('metric-fine', 'M24x1.5', 24.0, 22.5),
    ('unc', '#4', 2.845, 2.261),
    ('unf', '#4', 2.845, 2.375),
    ('unc', '#5', 3.175, 2.578),
    ('unf', '#5', 3.175, 2.642),
    ('unc', '#6', 3.505, 2.705),
    ('unf', '#6', 3.505, 2.87),
    ('unc', '#8', 4.166, 3.454),
    ('unf', '#8', 4.166, 3.454),
    ('unc', '#10', 4.826, 3.797),
    ('unf', '#10', 4.826, 4.039),
    ('unc', '#12', 5.486, 4.496),
    ('unf', '#12', 5.486, 4.623),
    ('unc', '1/4', 6.35, 5.105),
    ('unf', '1/4', 6.35, 5.41),
    ('unc', '5/16', 7.938, 6.528),
    ('unf', '5/16', 7.938, 6.909),
    ('unc', '3/8', 9.525, 7.938),
    ('unf', '3/8', 9.525, 8.433),
    ('unc', '7/16', 11.112, 9.347),
    ('unf', '7/16', 11.112, 9.921),
    ('unc', '1/2', 12.7, 10.716),
    ('unf', '1/2', 12.7, 11.509),
]


def rows():
    return [{"series": s, "designation": n, "major": d, "tapDrill": t} for s, n, d, t in ROWS]


def install():
    from workshop_make import threads

    threads.use(rows)
    return threads
