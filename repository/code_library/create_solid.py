# CadQuery Code Library - Create Solid
# Examples for creating basic solid geometry

# Example 1: Simple rectangular block
import cadquery as cq

result = cq.Workplane("XY").box(50, 40, 5)

# Example 2: Rectangular block with positioning
import cadquery as cq

result = (
    cq.Workplane("XY")
    .box(50, 40, 5, centered=False)
)

# Example 3: Cylinder
import cadquery as cq

result = (
    cq.Workplane("XY")
    .cylinder(height=50, radius=10)
)

# Example 4: Sphere
import cadquery as cq

result = (
    cq.Workplane("XY")
    .sphere(radius=25)
)

# Example 5: Rectangular block on custom plane
import cadquery as cq

result = (
    cq.Workplane("XZ")
    .box(100, 50, 10)
)

# Example 6: Torus
import cadquery as cq

# Parameters
major_radius = 50.0  # Distance from center to tube center
minor_radius = 10.0  # Radius of the tube itself

# 1. Select Side Plane (XZ)
# 2. Offset by Major Radius (CRITICAL STEP)
# 3. Draw Circle (Minor Radius)
# 4. Revolve around Z axis
result = (
    cq.Workplane("XZ")
    .center(major_radius, 0)
    .circle(minor_radius)
    .revolve()
)
