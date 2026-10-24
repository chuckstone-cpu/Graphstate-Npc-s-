"""Reproducible seeds for every random choice in the experiments.

derive_seed(42, "select_maps", "dao") always gives the same number, on any machine.
Each part of the experiment gets its own seed this way, so changing one part
(say, the problem filter) does not change the random choices made in another.

We hash the labels with SHA-256 instead of using Python's hash(), because
hash() of a string changes every time Python starts.
"""

import hashlib


def derive_seed(master_seed, *labels):
    text = "|".join([str(master_seed)] + [str(label) for label in labels])
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)      # first 64 bits -> a plain integer seed
