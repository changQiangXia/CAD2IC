"""Handwritten CPU infrastructure fixture; not model-generated."""
from pathlib import Path
from build123d import Cylinder, Align, export_stl

def gen_step():
    body = Cylinder(0.75, 0.20923, align=(Align.CENTER, Align.CENTER, Align.MIN))
    export_stl(body, str(Path(__file__).with_suffix(".stl")))
    return body
