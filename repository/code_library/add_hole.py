# CadQuery Code Library - Add Holes
# Examples for creating holes in solids

# Example 1: Simple hole through a box
import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(50, 50, 10)
    .faces(">Z")
    .workplane()
    .hole(diameter=10)
)

# Example 2: Multiple holes using pattern
import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(100, 50, 5)
    .faces(">Z")
    .workplane()
    .rarray(40, 20, 2, 2)
    .hole(diameter=5)
)

# Example 3: Hole at specific position
import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(50, 50, 10)
    .faces(">Z")
    .workplane()
    .center(15, 15)
    .hole(diameter=8)
)

# Example 4: Counterbore hole
import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(50, 50, 10)
    .faces(">Z")
    .workplane()
    .cboreHole(diameter=5, cboreDiameter=10, cboreDepth=3)
)
