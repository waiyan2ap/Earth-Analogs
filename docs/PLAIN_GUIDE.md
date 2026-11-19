# Earth Analogs Explorer: plain-language guide

For anyone who sees a number or a term in the app and wants to know what it means and how much to trust it.

## The idea in four sentences
Pick a place on the Moon or Mars. We measure its ground (how steep, how bumpy, how hot and cold, how bright). We measure every 1-degree square of Earth the same way. Then we rank Earth squares by how close their numbers are to the Moon or Mars place. A high rank means "the measured ground looks alike", which is a lead for scientists to check, not proof that it is a good stand-in.

## What happens when you click a place on the Moon or Mars
1. The app takes a square of ground about 111 km wide around the nearest 1-degree point (a "patch").
2. It reads the measurements for that patch. Only measurements that really exist are used.
3. "Find similar places on Earth" compares Earth with whatever was measured there.

**Is every feature compared? No, only the ones with a sourced value.**
- **Moon:** slope (steep and typical), relief, landform shape, mean temperature, day-night swing. Six features in three groups: terrain, landform, thermal. If NASA's temperature data has a gap at that spot (about 8% of the Moon), thermal is left out and the match uses terrain and landform only. The panel says "No sourced value".
- **Mars:** slope (steep and typical), relief, landform shape, albedo. Five features in three groups: terrain, landform, albedo. **Temperature is not compared on a clicked Mars point**, because we have no global Mars temperature map (only three named sites have it). The panel shows "No sourced value" for it.
- **Moon albedo is not compared**, because we have no valid Moon albedo map.
- So a Moon score and a Mars score are built from different measurements. Do not compare a Moon percentage with a Mars percentage as if they meant the same thing.

## How the percentage is made
- For each feature: similarity = 1 minus (difference divided by the scale), never below 0. Example: steep slope 10 degrees on Mars, 7 degrees at an Earth square, scale 15. Difference 3, 3/15 = 0.2, similarity 80%.
- The **scale** is the difference we call "completely different". The scales are our starting guesses, not scientific constants. Changing them changes rankings.
- Features are grouped into dimensions (terrain, landform, thermal, albedo). Each dimension counts the same. Inside a dimension, features share its weight.
- An Earth square is scored only if it has a value in every dimension in use. That stops a coastal square with no temperature from scoring 100% on temperature alone.

## Terms
**Analog:** a place on Earth studied as a stand-in for a place on the Moon or Mars.

**Target:** the Moon or Mars place we are trying to match.

**Patch / 1-degree square:** a patch is the ~111 km square measured for a Moon or Mars point. An Earth square is 1 degree wide (about 111 km at the equator). Small features inside a square are averaged away.

**Terrain:** how steep the ground is. *Steep slope (90th percentile)* is the slope that only the steepest 10% of the ground exceeds. *Typical slope (median)* is the middle value.

**Landform:** the shape of the land over the whole patch. *Relief* is the height difference between the high and low ground (95th minus 5th percentile). *Landform shape (hypsometric integral)* is a 0 to 1 number: low means mostly lowland with a few peaks, high means mostly upland cut by valleys or craters.

**Thermal:** surface temperature. *Mean* is the average of day and night. *Swing* is day minus night. These are measured at 10:30 and 22:30 local time on the Moon, and at the matching satellite overpass hours on Earth. *Day thermal* is a daytime temperature only (used for Mars, where we have just three sites).

**Air temperature:** shown for Earth, never scored (the Moon has no air).

**Albedo:** the share of sunlight a surface reflects. Fresh snow is bright (high), dark basalt is low. It helps tell ice and snow from rock and soil. Earth and Mars albedo come from different instruments and are close but not identical.

**Score / match / similarity:** the percentage above. 100% means identical on the measured features, not identical places.

**Rank, "top 0.1% of Earth":** we score every Earth land square (about 25,000 for a typical target). "Top 0.1%" means no more than 0.1% of them score higher, roughly the best 25 squares. We round up, so the label is never too flattering. The tooltip says "Cell k of N" to separate squares that share the same label.

**Question presets** (Find on Earth): pick the question, and the app uses only the features that matter for it.
- *Everything measured:* all features with a sourced value.
- *Rover mobility:* slope, relief and albedo. Can a rover drive here, and is the ground bright (ice/snow) or dark (rock/soil)?
- *Landing hazard:* steep slope and relief only. Is the ground rough or steep enough to be dangerous to land on?
- *Thermal cycling:* temperature mean, swing, daytime and albedo. How hard do hot-cold cycles hit equipment?
Presets use fewer features, so scores are easier to push towards 100%. Read them as "is there a place like this for this one question".

**Verdict** ("Earth has a close analog"): 80% or more of the way there is "close", 60 to 80 is "partial", under 60 is "no close analog". This is our own rule of thumb.

**Strong analogy / Breaks down / Use it for / Not for:** the summary under every comparison. A measurement is "strong" at 80% similarity or more, "partial" from 60 to 80%, and "breaks down" under 60%. "Use it for" names a kind of test (driving, landing approach, thermal, brightness) only when every measurement of that kind is strong. "Not for" names it when any of them breaks down. Our own rule of thumb.

**Copy this report as text** (Find on Earth): copies the selected Earth place as plain text: target, place, question, match, rank, each value side by side, the summary above, the limits and the sources. Paste it into notes or a proposal.

**Curated pair:** a Moon/Mars site and an Earth site that the team lists as analogs (e.g. Shackleton and Devon Island). They come from team judgment, with no citation yet.

**Backtest (Method panel):** for each curated pair, where the Earth site ranks among all Earth squares. If the score is meaningful, known analogs should rank high. Pairs that rank low were chosen for reasons we don't measure (chemistry, ice, history).

**Gap map ("where Earth has no analog"):** for every Moon or Mars point, the best score any Earth square reaches. Low areas are places Earth cannot match on what we measure.

**"No sourced value":** we have no real measurement for that item. We show that instead of a guess.

**Real data / demo:** every value traces to a named source (see SOURCES_AND_METHODS.md).

## Data names
- **ETOPO:** NOAA's Earth elevation map. **MODIS:** NASA satellite that measures Earth surface temperature and albedo.
- **LOLA:** laser altimeter on NASA's Lunar Reconnaissance Orbiter (Moon heights). **Diviner:** the Orbiter's thermal radiometer (Moon temperature).
- **MOLA:** laser altimeter on Mars Global Surveyor (Mars heights). **TES:** its thermal instrument (Mars temperature and albedo).

## What the app cannot tell you
- Earth has no matching gravity, vacuum, radiation, or (for Mars) thin CO2 air. A high score covers only the measured surface.
- The scales and the verdict cut-offs are our choices.
- 1-degree squares hide small features such as a single crater.
- Earth data is recent (2025), Moon and Mars data come from earlier missions.
- The geology tags and curated pairs are not yet cited.
