These notes interpret the generated numbers above. Every number here was computed with pandas
from `results/runs.csv` / `events.csv` (not estimated) and can be recomputed from those files.

- **Does D* Lite's more expensive first plan pay off?** Its first plan costs a median **1.84x**
  A*'s expansions (IQR 1.06-4.95, range 0.21-42.9; D* Lite's first plan was cheaper in 80 of 360
  problems). Against the two *random* pranksters that cost is **not** repaid when compared with
  lazy A*: D* Lite's total work is higher (median ratio about 1.6-1.7). Against the **saboteur** it
  is repaid: D* Lite's total work is lower than lazy A*'s in 305 of 360 problems (median ratio
  0.36). Against A* restart, D* Lite's total work is lower under every prankster that blocks.
- **Lazy A* = A* restart under the saboteur, exactly.** Every saboteur block lies on the
  planner's current path (100% of saboteur events, vs 0.5% random global and 4.5% random local),
  so lazy A* must replan at every event, exactly like A* restart. Their runs are identical in every
  count column on all 360 problems. This is why the two "D* Lite vs" rows are identical for the
  saboteur.
- **The worst single replan (hitch) under the saboteur is NOT a clear win.** The paired test
  favours D* Lite only weakly (213 wins / 147 losses, r = 0.17, Holm p = 0.042), and it is not
  significant on street or room. The typical hitch is smaller (median 1,049 vs 1,697 expansions),
  but the mean is the same or slightly higher (20,442 vs 20,388): a few D* Lite repairs are very
  large. A heavy tail like this is what a player would notice, so "D* Lite avoids hitches" is
  not supported.
- **Random global: tiny numbers, opposite signals.** Lazy A* almost never replans (median 0) and
  D* Lite does a little bookkeeping work after most blocks. The paired test therefore says D* Lite
  does MORE replanning work (135 losses vs 37 wins), while D* Lite's mean is lower (10.8 vs 69.7
  expansions per run) because lazy A* sometimes has to do a full re-search. Both amounts are
  negligible next to the first plan (about 1,600-2,600 expansions).
- **Expansions are not time.** Measured per expansion, D* Lite costs about 54-70 microseconds,
  A* about 16-18, BFS about 3.5-4 (sum of time / sum of expansions). That 3-4x per-expansion
  difference is far larger than the timing noise we measured (6-38%), and it cancels D* Lite's
  advantage in expansions: under the saboteur D* Lite does about 4x fewer expansions than A*
  restart, yet its mean time per run is not lower (6,079 vs 5,573 ms, secondary table). That 9%
  time difference itself is inside the noise, so we do NOT claim D* Lite is slower, only that the
  expansion advantage does not show up as a time advantage in this Python implementation. The
  time columns also leave out D* Lite's per-step `move_start` + `compute_shortest_path` calls
  (0 expansions; their time was not logged).
- **Per map set** (heterogeneity list above): the direction of every significant overall result
  holds on each set, except where a set is not significant (dao for the random-global tiny
  amounts; street and room for the saboteur hitch; room for random-local total work). No set
  shows the opposite direction.
