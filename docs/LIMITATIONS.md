# Honest limitations, in plain words

Each item: **what is limited**, **why**, **what it means**, and **what would fix it**. Read the first block aloud if a judge asks "what are the weaknesses?"

## If you only say three sentences
1. "Our scores compare measured ground shape, temperature and brightness, and nothing else, so they find leads to check, not proven test sites."
2. "Where we have no real measurement, such as Mars temperature outside three sites, we show 'no sourced value' and leave it out instead of guessing."
3. "The scales and cut-offs are our own starting choices, and the next step is to tune them with scientists."

---

## A. Missing data

**1. Mars surface temperature is only at 3 sites (Jezero, Olympus Mons, Valles Marineris).**
- *Why:* the Mars temperature we used (MGS TES) comes from a per-region data request, not a ready global map. We requested it for the three named sites only. A global map would mean downloading and gridding a very large archive (for example MRO Mars Climate Sounder), which did not fit our time.
- *Means:* when you click a Mars point, the comparison uses slope, relief, landform shape and albedo, with no temperature. Mars thermal questions only work at those three sites.
- *Fix:* build a global Mars temperature grid from a measured source.

**2. About 8% of the Moon has no temperature.**
- *Why:* the Diviner instrument did not observe those spots at the two local times we match to Earth (10:15 to 10:45 and 22:15 to 22:45) often enough. They are scattered strips.
- *Means:* at those points the app compares terrain and landform only and says so. We do not fill gaps, because a made-up number is worse than a missing one.
- *Fix:* widen the time windows, or add other Diviner data and document the change.

**3. No Moon albedo.**
- *Why:* the only Moon image we downloaded is a morphology mosaic, not a calibrated albedo map.
- *Means:* Moon scores never use brightness. A bright ice patch and dark rock look the same to the Moon score.
- *Fix:* find a properly calibrated lunar albedo map.

**4. Sunlight, ice and Earth visibility exist only at Shackleton.**
- *Why:* those maps (NASA PGDA) were available for the south pole site only.
- *Means:* the Base plan's Sunlight and Earth view layers show only there. Other sites get terrain only.

## B. The measurements are coarse
**5. Every place is a 1-degree square, about 111 km wide.**
- *Why:* Earth, Moon and Mars are measured on the same grid so they can be compared.
- *Means:* one crater, one cliff or one landing ellipse is averaged away. A square can mix very different ground, such as a glacier beside lava.
- *Fix:* a finer grid, which takes much more compute and storage.

**6. Elevation maps are not identical across places.**
- *Why:* the Moon grid uses a 16-pixels-per-degree map (about 1.9 km per pixel), the Mars grid a 463 m map, and the three named Mars sites a finer 200 m blend. All are averaged to the same 1.85 km spacing, but they are different datasets.
- *Means:* a named Mars site and the same spot on the gap map can differ by a few points.

**7. Earth and Mars albedo come from different instruments.**
- *Why:* MODIS (Earth, white-sky albedo) and MGS TES (Mars) cover slightly different light bands and times of day. The TES map is also clipped to 0.06 to 0.32 by its makers.
- *Means:* they are the closest pair available, not identical. Very dark or very bright Mars places read slightly less extreme than they are.

**8. Time periods differ.**
- *Why:* Earth temperature and albedo are 2025 averages. The Moon is 2009 to 2015 (Diviner). Mars comes from the older TES mission. WorldClim air temperature (shown, not scored) is 1970 to 2000.
- *Means:* one Earth year may not represent a normal year. We compare surfaces, not seasons.

## C. The scoring is a model, not a measurement
**9. The scales are guesses.**
- *Why:* the scale is how big a gap counts as "completely different" (for example 2,000 m of relief). We set a starting value for each feature without scientific calibration.
- *Means:* change a scale and the ranking changes. Percentages are for ranking and exploring, not exact truth.
- *Fix:* tune the scales with analog scientists, and publish the reasoning.

**10. The "close analog" cut-offs (80% and 60%) are ours.**
- *Means:* the verdict is a rule of thumb. The app labels it so.

**11. Each feature is judged on its own.**
- *Means:* the formula does not model things that act together, such as low pressure and cold at the same time.

**12. Scores are not comparable between Moon and Mars.**
- *Why:* they use different features (Moon has temperature, Mars has albedo).
- *Means:* never say "the Moon is easier to match than Mars" from the percentages.

**13. High percentages are easy to reach with few features.**
- *Means:* question presets use fewer features, so they score higher. Read them as "is there a place like this for this one question".

## D. What Earth cannot copy
**14. Gravity, vacuum, radiation and thin CO2 air.**
- *Why:* they cannot be reproduced on Earth's surface.
- *Means:* a high score covers only the measured ground. Testing for vacuum or radiation needs a chamber or a flight.

**15. We do not measure boulders, dust, soil strength, chemistry, water or ice below the surface.**
- *Means:* flat and low-relief does not mean safe to land or build on. This is not a landing-site tool.

## E. Curation and checking
**16. The geology tags and curated analog pairs have no citations yet.**
- *Means:* tags have weight 0 and never change a score. Pair reasons are team judgment.

**17. Most site coordinates are not checked against a gazetteer.**
- *Why:* 12 of the 18 Earth sites were typed from general knowledge, and 10 more were carried over from the original dataset. Only Tranquility is checked.
- *Means:* errors under about 0.3 degrees do not change a 1-degree square's values, so values are probably fine, but they are not verified.
- *Fix:* check each coordinate against a named source.

**18. Some site descriptions (for example "Apollo astronauts trained here") have no source.**
- *Means:* do not repeat them as fact until cited.

**19. The backtest is small.**
- *Why:* only 9 curated pairs.
- *Means:* it is a sanity check, not proof. Pairs that rank low were chosen for reasons the grid cannot see (chemistry, signs of life, ice).

**20. Nothing here has been reviewed by planetary scientists.**
- *Means:* treat results as leads for experts to check.

## F. Base planner
**21. Design numbers are yours.**
- *Why:* efficiency, losses, margins and similar parameters have no agreed source, so they start empty.
- *Means:* the planner only sizes power and habitat after you enter them. Presets fill only numbers quoted by NASA documents (Artemis Base Camp, Mars DRA 5.0).

**22. Night length and Mars sunlight are simplified.**
- *Means:* Tranquility's night is half the 29.53-day cycle, and Mars uses half a sol at the equinox. Seasons and dust storms are ignored. Dust transmission has no sourced value, so you type it.

## G. How it was built
**23. AI helped.**
- *Means:* Claude helped write code, check data and draft text. The team reviewed it. Say so if asked.

---

## One-line answers for a judge
- **Why only 3 Mars temperature sites?** "Our Mars temperature data comes from a per-region request, so we have three sites. A global grid is the next step."
- **Why leave gaps blank?** "A blank is honest; a guess is not."
- **Is it accurate?** "It is a transparent ranking of measured ground, not a verdict. The scales are our starting choices."
- **Can it pick a landing site?** "No. It finds Earth places that resemble a target. Landing safety needs sunlight, boulders and soil, which we do not measure globally."
- **What would you do next?** "Global Mars temperature, a Moon albedo map, finer grids, cited analog pairs and checked coordinates, tuned with scientists."
