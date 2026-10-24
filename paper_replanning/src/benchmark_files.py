"""Find the downloaded benchmark files on disk and pair each .map with its .scen.

Moving AI names a scenario file after its map: "arena.map" -> "arena.map.scen".
"""

from pathlib import Path


def find_map_files(set_dir):
    """Return {map_name: (map_path, scen_path or None)} for one map set, sorted by name.

    map_name is the file name without ".map", e.g. "arena".
    """
    set_dir = Path(set_dir)
    scens = {p.name: p for p in set_dir.rglob("*.scen")}
    found = {}
    for map_path in sorted(set_dir.rglob("*.map")):
        name = map_path.stem
        if name in found:
            raise ValueError(f"two maps called {name!r} in {set_dir}")
        found[name] = (map_path, scens.get(map_path.name + ".scen"))
    return found
