"""Identify versioned zoning and aggregate outputs by their source filename."""

import os
import re


def result_generation(source: str, stem: str):
    """Return 1 for ``stem.ext``, N for ``stem_vN.ext``, or None."""
    filename = os.path.basename(source.split("|", 1)[0])
    name = os.path.splitext(filename)[0]
    if name.lower() == stem.lower():
        return 1
    match = re.fullmatch(re.escape(stem) + r"_v([0-9]+)", name, re.I)
    return int(match.group(1)) if match else None


def is_result_label(name: str, display_name: str) -> bool:
    """Recognize both legacy labels and labels with a generation suffix."""
    return name == display_name or re.fullmatch(
        re.escape(display_name) + r" \(v[0-9]+\)", name
    ) is not None


def latest_result_layer(project, stem: str, layer_type):
    """Find the highest loaded output generation, regardless of UI label."""
    candidates = []
    for layer in project.mapLayers().values():
        if not isinstance(layer, layer_type):
            continue
        generation = result_generation(layer.source(), stem)
        if generation is not None:
            candidates.append((generation, layer))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def generation_group(root, generation: int):
    """Return the parent group shared by outputs of one iteration."""
    name = f"検討 第{generation}世代"
    for child in root.children():
        if child.name() == name and hasattr(child, "addLayer"):
            return child
    return root.insertGroup(0, name)
