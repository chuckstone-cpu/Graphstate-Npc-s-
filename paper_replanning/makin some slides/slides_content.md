# Final Review: Slide Content
**Replanning Against a Saboteur: Does Incremental Search Still Save Effort When the Opponent Blocks the Route?**
Fundamentals of AI, Amrita (AIE). Project: Outwit / Graphstate NPCs

How this deck is split:
- **Part A (slides 1–6), teammates:** the simpler slides (intro, problem, literature, dataset).
- **Part B (slides 7–17), Arvind:** all the core research slides (gap, objective, method, results, novelty, limitations, demo).
- **Part C (slide 18), teammate:** references.

All the slides the review requires are covered, in a logical order.
Every number here comes from the paper and `results/SUMMARY.md`. Don't round or change them.

---

# PART A: Teammates (simpler slides)

## Slide 1: Title
- Replanning Against a Saboteur: Does Incremental Search Still Save Effort When the Opponent Blocks the Route?
- Team names, roll numbers, guide name, course (Fundamentals of AI), Amrita
- Visual: an Outwit screenshot (the knight blocking the thief)

## Slide 2: Introduction
- Game characters (NPCs) walk through worlds that change: doors close, crates fall, players put obstacles in the way.
- When the route breaks, the NPC must **replan**, i.e. find a new path.
- The usual game approach is to run **A\*** again from scratch.
- **Incremental search (D\* Lite)** reuses its old search and repairs only what changed. It's famous for saving work in robotics.
- Our game **Outwit**: you play a knight who locks doors and drops barrels to stop an AI thief stealing a treasure. The thief replans with D\* Lite.
- Speaker note: "Every time you block the thief, it has to rethink its route. We asked which way of rethinking is cheapest."

## Slide 3: Problem Statement
- Incremental search has been tested almost only with **random** map changes, or changes a robot discovers by sensing.
- In games, changes are often made **on purpose** by an opponent (the player) who wants the NPC to fail.
- **Problem:** we don't know whether D\* Lite still saves search effort when an opponent deliberately blocks the NPC's route, compared with:
  - replanning from scratch (BFS, A\*), and
  - a simple **lazy A\*** that only replans when its path is actually broken.

## Slide 4: Literature Review (table)

| # | Work | What they did | Key point | Gap / relevance to us |
|---|---|---|---|---|
| 1 | Hart, Nilsson & Raphael (1968) | A\* search | Optimal shortest paths with an admissible heuristic | Static maps only; our baseline |
| 2 | Stentz (1994, 1995) | D\*, Focussed D\* | Replanning for robots in partially known terrain | Changes come from sensing, not an opponent |
| 3 | Koenig, Likhachev & Furcy (2004) | Lifelong Planning A\* | Reuses earlier search after edge-cost changes | Random/unknown changes |
| 4 | Koenig & Likhachev (2002, 2005) | **D\* Lite** | Simpler incremental replanner, big savings in unknown terrain | Evaluated on robot navigation, not adversaries |
| 5 | Likhachev et al. (2005) | Anytime Dynamic A\* | Combines anytime + incremental replanning | No deliberate opponent |
| 6 | Sun, Yeoh & Koenig (2010) | Moving Target D\* Lite | Incremental search when the goal moves | The target moves; the map isn't sabotaged |
| 7 | Hernández et al. (2012) | Position paper | "Incremental search is poorly understood": unclear when D\* Lite beats A\* | Motivates careful baselines like lazy A\* |
| 8 | Hernández, Baier & Asín (2014) | Fast A\* variant | A\* can run faster than D\* Lite in partially known terrain | Again no opponent |
| 9 | Sturtevant (2012) | Moving AI grid benchmarks | Standard maps + problems for pathfinding | **Our dataset** |
| 10 | Botea et al. (2004); Harabor & Grastien (2011) | HPA\*, Jump Point Search | Faster pathfinding on static game grids | Static maps, no replanning focus |
| 11 | Orkin (2006); Uludağlı & Oğuz (2023) | Game NPC AI (F.E.A.R., survey) | Games usually just re-run A\* | Shows the industry default we test against |
| 12 | Israeli & Wood (2002); Smith & Song (2020) | Shortest-path network interdiction | An attacker blocks edges to make the shortest path as long as possible | Never linked to NPC replanning effort. **That's our gap** |

## Slide 5: Summary of Literature Review
- Search: A\* is the standard; incremental methods (LPA\*, D\* Lite) were built to reuse work when maps change.
- Evaluations use **random or sensed** changes, mostly in robotics.
- Researchers themselves say it's unclear when D\* Lite actually beats A\*, and strong A\* variants can win.
- Games mostly re-run A\*.
- Operations research has studied **deliberate blocking (interdiction)** for decades, but only from the attacker's side.
- **Nobody has measured** what deliberate blocking does to the cost of incremental replanning. (This leads into Arvind's Research Gap slide.)

## Slide 6: Dataset Description
- **Source:** Moving AI Lab 2D grid benchmarks (Sturtevant 2012), Open Data Commons Attribution License.
- **Three map sets:**
  - **dao:** maps from the game *Dragon Age: Origins*
  - **street:** grid maps of real city street layouts
  - **room:** artificial maps made of rooms joined by doorways (512×512)
- **Selection (random, fixed seed):**
  - 8 maps per set, so **24 maps** in total
  - max side 256 cells (room allowed 512, since all room maps are 512×512)
  - at least 30% walkable
  - 15 start→goal problems per map, so **360 problems**
  - problem length 60–250 steps
- **Our grid model:** 4-connected moves (no diagonals), each step costs 1, water treated as a wall.
- The benchmark's own "optimal length" assumes diagonal moves, so we **recomputed every length with our own BFS**.
- Median problem length: dao 87, street 163, room 157 steps.
- Visual: one map image from each set, plus a small table (set / maps / problems / median length).

---

# PART B: Arvind (core research slides)

## Slide 7: Research Gap
- **Gap 1:** incremental replanning has only been evaluated under random or sensed changes, never against an opponent who **chooses** the blocks.
- **Gap 2:** most comparisons use A\*-restart as the baseline. A **lazy A\*** (replan only when the path is hit) is a much stronger baseline that is rarely used.
- **Gap 3:** game AI evaluations rarely use the **real search code from a game** or measure the worst single replan, the "hitch" a player would notice.

## Slide 8: Research Objective (one objective, four modules)
**Objective:** measure whether incremental replanning (D\* Lite) still saves search effort when an opponent deliberately blocks the NPC's route on game maps, against replan-from-scratch and lazy baselines.
- **Module 1, Verified port:** port the game's BFS, A\*, D\* Lite and heap to Python and prove they match the game's own test numbers.
- **Module 2, Change models:** four "pranksters":
  - none
  - random global
  - random local
  - **saboteur** (greedy interdiction)
- **Module 3, Experiment:** 5,760 paired runs on 24 benchmark maps, logging every replan.
- **Module 4, Analysis:**
  - total effort, replan effort and hitch
  - bootstrap CIs, Wilcoxon tests, effect sizes, Holm correction

## Slide 9: Methodology
- Pipeline: **maps → problems → planners × pranksters → runs → logs → statistics**
- **Four planners:**
  - BFS restart (blind, replans from scratch)
  - A\* restart (Manhattan heuristic, replans from scratch)
  - **Lazy A\*** (keeps its path, replans only if a new block lands on it)
  - **D\* Lite** (searches backward from the goal, repairs only what changed)
- **One run:** the NPC walks one step at a time.
  - Every **K = 5** steps, the prankster may place a block, up to **B = 30** blocks per trip.
  - Blocks never touch the NPC's cell or the goal, and never disconnect the goal (checked first).
- **Saboteur:**
  - takes up to **C = 12** cells on the NPC's current path
  - tries blocking each one with its own A\*
  - blocks the one that lengthens the trip the most
- **Main metric: expansions** (cells the search examines). Time in ms is secondary, because Python timing is noisy.
- **Fairness:** the same maps, problems and seeds for every planner; each prankster has its own seeded random generator.
- Visual: a flow diagram, plus a tiny grid showing the saboteur choosing a block.

## Slide 10: Proposed Work (what we built)
- **Outwit:** a Godot 4.5 game.
  - The player is a knight; the AI thief senses with a 7-tile field of view.
  - The thief uses minimax with alpha-beta for fights and D\* Lite for movement.
  - Search code is hand-written: BFS, A\*, D\* Lite, minimax.
- **Verified Python port.** It matches the game exactly:

  | Check on level1 | Game | Python |
  |---|---|---|
  | BFS | 190 expansions | 190 expansions |
  | A\* | 67 expansions | 67 expansions |
  | D\* Lite | 75 expansions | 75 expansions |
  | Wall-drop repair, D\* vs fresh A\* | 3 vs 58 | 3 vs 58 |

  We also deliberately broke the code to check the tests catch bugs (mutation testing).
- **Experiment framework:**
  - simulator and resumable parallel runner (11 workers)
  - 66 automated tests
  - full run: 5,760 runs in 2 h 43 min, 0 errors, 100% success
- **Data integrity:**
  - 52 runs that hit the step cap were re-run with a bigger cap; their expansion counts matched exactly.
  - The path-limit check never fired. The longest measured path was 1,999 cells.

## Slide 11: Results (1/3): Total search effort
Mean expansions, initial plan + all replans (n = 360 per cell):

| Planner | No change | Random global | Random local | **Saboteur** |
|---|---|---|---|---|
| BFS restart | 17,701 | 266,291 | 268,998 | 1,137,497 |
| A\* restart | 1,571 | 18,687 | 18,874 | 354,770 |
| Lazy A\* | 1,571 | **1,641** | **2,328** | 354,770 |
| D\* Lite | 2,599 | 2,610 | 2,718 | **86,989** |

- **Random blocks: lazy A\* wins.**
  - Most random blocks miss the path, so it barely replans.
  - D\* Lite's first plan costs a median **1.84×** A\*'s and is never paid back.
- **Saboteur: D\* Lite wins.**
  - About **4× fewer expansions** than both A\* variants.
  - Fewer on **305 of 360** problems (median ratio 0.36, rank-biserial r = 0.89, Holm p < 0.001).
- Under the saboteur, lazy A\* = A\* restart exactly, because **100% of saboteur blocks land on the planner's path**.
- Visual: Figure 5 (total effort).

## Slide 12: Results (2/3): The hitch (worst single replan)

| Planner | Random global | Random local | Saboteur |
|---|---|---|---|
| A\* restart | 1,480 | 1,485 | 20,388 |
| Lazy A\* | 67.8 | 510 | 20,388 |
| D\* Lite | 10.0 | 106 | 20,442 |

- Under the saboteur, D\* Lite's **mean hitch is the same** as A\*'s, roughly 20.4k each.
- Its median is lower (1,049 vs 1,697), but a few huge repairs balance it out.
- The paired test favours D\* Lite only weakly overall (213/0/147, p = 0.042).
- It's **not significant on street (p = 0.351) or room (p = 1.000)**.
- **So "D\* Lite gives smoother gameplay" is not supported.**
- Visual: Figure 3 (hitch).

## Slide 13: Results (3/3): Discussion
- **Where the block lands matters.** D\* Lite searches backward from the goal.
  - Blocks within 25 cells of the goal: no advantage (1,387 vs 1,370 expansions per event).
  - Blocks 100–149 cells from the goal: about **7× fewer** (2,505 vs 18,441).
- **Expansions ≠ time.** A D\* Lite expansion costs **3–4× longer** than an A\* one (54–70 vs 16–18 µs), which cancels its savings in wall-clock time in our Python code.
- **Path length:** the saboteur makes every planner walk **2.8–2.9× the optimum**. All planners walk equally optimal routes; only the thinking cost differs.
- **Consistency:** the results point the same way in all three map sets.
- Visual: Figure 1 (expansions vs. distance to goal) and Figure 2 (box plot).

## Slide 14: Conclusions
- **Who changes the map decides which replanner is best.**
- **Random changes:** a simple lazy A\* does the least work, and D\* Lite's setup cost never pays off.
- **Deliberate saboteur:** D\* Lite needs about **4× fewer expansions** than both A\* variants.
- But it does **not reliably reduce the worst freeze**, and in Python its costlier expansions cancel the time saving.
- **For Outwit**, where the player *is* the saboteur, D\* Lite is the right choice for the thief in search effort.

## Slide 15: Novelty of the Research
- **First measurement of incremental replanning against a deliberate opponent:**
  - a greedy shortest-path interdiction saboteur, a concept from operations research
  - applied to NPC pathfinding
- **A strong lazy-A\* baseline**, which overturns the usual "D\* Lite beats A\*" story under random changes.
- **Real game code:** the planners are a verified, literal port of our own game's search code, matching its test numbers, tie-breaking and expansion counts.
- **The hitch as a metric:** we report the worst single replan, what players actually feel, not just averages.
- **Rigorous and reproducible:**
  - 5,760 paired runs, bootstrap CIs, Wilcoxon + Holm, effect sizes
  - seeded, resumable, with all data and code in the repository

## Slide 16: Scope and Limitations
**Scope:**
- 2D grid pathfinding, 4-connected, unit cost
- 3 benchmark map sets
- blocking-only changes
- one greedy saboteur

**Limitations:**
- **Full knowledge:** the NPC learns of each block instantly. (In Outwit, the thief senses within 7 tiles.)
- **Block-only:** cells never reopen. (In Outwit, doors unlock and barrels can be smashed.)
- **Timing measured in Python**, with timings varying 6–38% between identical runs. A compiled language could change the time ratio.
- **No diagonal moves**, a map-size cap of 256 (room allowed 512), 24 maps.
- **The saboteur is greedy** (best single block), not an optimal interdiction plan.
- **It reacts to each planner's own path**, so trajectories differ slightly between planners.
- **Heap tie-order** was verified only on the game's level1 map.
- **Future work:**
  - partial sensing
  - cells that reopen
  - stronger / human-style saboteurs from playtest logs
  - in-game frame-time measurement

## Slide 17: Demo (Outwit)
- Live in Godot: play as the knight, drop barrels and lock doors, and watch the thief replan around them.
- Optional: an animation of one experiment run on a room map (see note below).
- Speaker note: "In the game you are the saboteur, which is exactly the case where D\* Lite won."

---

# PART C: Teammate

## Slide 18: References (IEEE style, from paper/refs.bib)
1. P. E. Hart, N. J. Nilsson, B. Raphael, "A formal basis for the heuristic determination of minimum cost paths," *IEEE Trans. Syst. Sci. Cybern.*, 4(2):100–107, 1968.
2. S. Russell, P. Norvig, *Artificial Intelligence: A Modern Approach*, 4th ed., Pearson, 2020.
3. A. Stentz, "Optimal and efficient path planning for partially-known environments," *Proc. IEEE ICRA*, 1994, pp. 3310–3317.
4. A. Stentz, "The focussed D\* algorithm for real-time replanning," *Proc. IJCAI*, 1995, pp. 1652–1659.
5. S. Koenig, M. Likhachev, D. Furcy, "Lifelong Planning A\*," *Artificial Intelligence*, 155(1–2):93–146, 2004.
6. S. Koenig, M. Likhachev, Y. Liu, D. Furcy, "Incremental heuristic search in artificial intelligence," *AI Magazine*, 25(2):99–112, 2004.
7. S. Koenig, M. Likhachev, "D\* Lite," *Proc. AAAI*, 2002, pp. 476–483.
8. S. Koenig, M. Likhachev, "Fast replanning for navigation in unknown terrain," *IEEE Trans. Robotics*, 21(3):354–363, 2005.
9. M. Likhachev et al., "Anytime Dynamic A\*: An anytime, replanning algorithm," *Proc. ICAPS*, 2005, pp. 262–271.
10. X. Sun, W. Yeoh, S. Koenig, "Moving Target D\* Lite," *Proc. AAMAS*, 2010, pp. 67–74.
11. C. Hernández, J. A. Baier, T. Uras, S. Koenig, "Position paper: Incremental search algorithms considered poorly understood," *Proc. SoCS*, 2012, pp. 159–161.
12. C. Hernández, J. A. Baier, R. Asín, "Making A\* run faster than D\*-Lite for path-planning in partially known terrain," *Proc. ICAPS*, 2014, pp. 504–508.
13. N. R. Sturtevant, "Benchmarks for grid-based pathfinding," *IEEE Trans. Comput. Intell. AI Games*, 4(2):144–148, 2012.
14. A. Botea, M. Müller, J. Schaeffer, "Near optimal hierarchical path-finding," *J. Game Development*, 1(1):7–28, 2004.
15. D. Harabor, A. Grastien, "Online graph pruning for pathfinding on grid maps," *Proc. AAAI*, 2011, pp. 1114–1119.
16. J. Orkin, "Three states and a plan: The A.I. of F.E.A.R.," *Proc. GDC*, 2006.
17. M. Ç. Uludağlı, K. Oğuz, "Non-player character decision-making in computer games," *Artif. Intell. Rev.*, 56(12):14159–14191, 2023.
18. D. R. Fulkerson, G. C. Harding, "Maximizing the minimum source-sink path subject to a budget constraint," *Math. Programming*, 13(1):116–118, 1977.
19. E. Israeli, R. K. Wood, "Shortest-path network interdiction," *Networks*, 40(2):97–111, 2002.
20. J. C. Smith, Y. Song, "A survey of network interdiction models and algorithms," *Eur. J. Oper. Res.*, 283(3):797–811, 2020.
21. F. Wilcoxon, "Individual comparisons by ranking methods," *Biometrics Bulletin*, 1(6):80–83, 1945.
22. B. Efron, "Bootstrap methods: Another look at the jackknife," *Ann. Statist.*, 7(1):1–26, 1979.
23. S. Holm, "A simple sequentially rejective multiple test procedure," *Scand. J. Statist.*, 6(2):65–70, 1979.

(The full bib also has Ramalingam & Reps 1996, Baier et al. 2015 and Kerby 2014. Add them if the slide has room.)

---

# Notes for the slide-making chat
- Figures to insert are in `paper_replanning/results/figures/`: fig5 (total effort), fig3 (hitch), fig1 (distance), fig2 (box plot), fig4 (path overhead).
- Keep a maximum of 5 bullets per slide. Put long details in speaker notes.
- Theme suggestion: dark dungeon colours to match Outwit, with an Outwit screenshot on the title slide.
- Wording rule: say "benchmark maps" (dao is a game, street is real cities, room is artificial), not "real game maps".

# Demo note (Godot)
- Godot runs **Outwit's own levels** (the castle and level1), not the Moving AI maps. The game has no loader for `.map` files.
- For the review: show Outwit live for the "player is the saboteur" story, and show the figures for the experiment.
- If you want a visual of an experiment run, ask Claude Code: *"Write scripts/replay_run.py that replays one run (map, problem, planner, prankster from runs.csv) as a matplotlib animation/GIF: walls, blocks appearing, the NPC's path updating. Make one GIF for D\* Lite vs saboteur on a room map."* Test it the day before. Don't edit the Godot game before the review.
