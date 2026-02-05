# CadQuery Code Library - Boolean Operations
# Examples for union, subtraction, intersection

# Example 1: Boolean Union (combining two boxes)
import cadquery as cq

box1 = cq.Workplane("XY").box(50, 40, 5)
box2 = cq.Workplane("XY").workplane(offset=5).box(40, 50, 10)

result = box1.union(box2)

# Example 2: Boolean Subtract (hole in box)
import cadquery as cq

box = cq.Workplane("XY").box(50, 50, 10)
hole = cq.Workplane("XY").cylinder(height=10, radius=5)

result = box.cut(hole)

# Example 3: Union with translation
import cadquery as cq

base = cq.Workplane("XY").box(100, 50, 5)
leg = cq.Workplane("XY").transformed(offset=(0, 0, 5)).box(50, 100, 5)

result = base.union(leg)
