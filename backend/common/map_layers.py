"""Map layer bounds, read from data/json/map_layers.json.

Pure python so the datagen scripts (generate_map_objects.py, validate.py,
slice_map.py) share it with the backend. The frontend imports the same JSON.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

DEFAULT_LAYER = 'MainMap'


def load_map_layers(path: Path) -> Dict[str, Dict]:
    """{name: {label, source, tiles, x: [min, max], y: [min, max]}}, in file order."""
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)
    layers = {k: v for k, v in raw.items() if not k.startswith('_')}
    for name, m in layers.items():
        for key in ('source', 'tiles', 'x', 'y'):
            if key not in m:
                raise ValueError(f'map_layers.json: layer {name!r} is missing {key!r}')
    return layers


def which_map(layers: Dict[str, Dict], x: float, y: float) -> str:
    """The layer whose bounds contain (x, y); first listed wins on overlap.

    Out-of-bounds objects are kept on the default layer rather than dropped,
    so they stay addressable.
    """
    for name, m in layers.items():
        (x0, x1), (y0, y1) = m['x'], m['y']
        if x0 <= x <= x1 and y0 <= y <= y1:
            return name
    return next(iter(layers), DEFAULT_LAYER)
