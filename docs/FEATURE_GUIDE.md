# Feature guide: what each measurement means and how the project uses it

Eleven things are measured or recorded for each place. Eight are scored. Two are shown but never scored. One (geology tags) is recorded but has weight 0. Examples use values from our own data files.

**How any scored feature turns into a percentage:** similarity = 1 minus (difference divided by the *scale*), never below 0. The scale is the difference we call "completely different". Features sit in groups called dimensions; each dimension counts the same, and features inside it share its weight.

| Dimension | Features | Moon point | Mars point | Earth |
|---|---|---|---|---|
| Terrain | Steep slope, Typical slope | yes | yes | yes |
| Landform | Local relief, Landform shape | yes | yes | yes |
| Thermal | Mean surface temperature, Day-night swing | yes (where Diviner has data) | no | yes |
| Day thermal | Daytime surface temperature | no | only 3 named sites | yes |
| Albedo | Surface albedo | no | yes | yes |
| Air (never scored) | Mean air temperature, Annual air range | no | no | shown only |
| Tags (weight 0) | Geology tags | named sites only | named sites only | named sites only |

---

## Terrain: how steep is the ground

**1. Steep slope (90th percentile), degrees. Scale 15.**
Take the slope at every point in the 111 km square. This is the slope that only the steepest 10% of the ground goes above. It catches cliffs, crater walls and canyon sides, which one average would hide.
Examples: Tranquility 1.6 degrees (almost flat), Jezero 5.3, Valles Marineris 21.8, Shackleton 16.0.
Used for: rover mobility and landing hazard. A 20 degree place and a 2 degree place are very different to drive on.

**2. Typical slope (median), degrees. Scale 10.**
The middle slope: half the ground is gentler, half is steeper. It describes the everyday ground a rover crosses.
Examples: Tranquility 0.66, Jezero 1.78, Valles 4.79.
Used for: same as above. Shown next to the steep slope, the two tell you whether a place is gentle with a few cliffs or rough everywhere.

## Landform: what shape is the land

**3. Local relief, metres. Scale 2000.**
Highest ground minus lowest ground in the square, ignoring the top and bottom 5% (so one odd peak does not count). It says how much the land goes up and down.
Examples: Tranquility 916 m, Jezero 1,341 m, Olympus Mons 4,096 m, Valles Marineris 8,337 m.
Used for: landing hazard (rough, hilly ground), rover mobility (big climbs), and telling a plain from a mountain or canyon.

**4. Landform shape (hypsometric integral), a number from 0 to 1. Scale 0.5.**
Where the bulk of the ground sits between the lowest and highest point. Low (near 0): mostly low ground with a few peaks. High (near 1): mostly high ground cut by valleys or craters. Around 0.5: evenly spread. Two places can have the same relief but very different shapes, such as a flat plain with one mountain versus a plateau with canyons.
Examples: Tranquility 0.34, Jezero 0.50, Shackleton 0.58.
Used for: separating look-alike places that the slope and relief numbers cannot.

## Thermal: how hot and cold is the surface

These are the temperature of the ground (skin temperature), not the air. Earth is measured by a satellite at about 10:30 in the day and 22:30 at night; the Moon is measured at the same local times so the two are comparable.

**5. Mean surface temperature, degrees C. Scale 120.**
Average of the day and night temperature. Says if a place is cold or warm overall.
Examples: Tranquility -29 C, Shackleton -173 C.

**6. Day-night swing, degrees C. Scale 60.**
Day temperature minus night temperature. Says how hard the heat-cold cycle hits hardware.
Examples: Tranquility 278 C swing (very harsh), Shackleton 62 C.
Used for: thermal cycling questions (materials, batteries, electronics).

**7. Daytime surface temperature, degrees C. Scale 120. (Day thermal)**
The daytime value alone. We use it for Mars because the Mars data we have is daytime only (MGS TES, three named sites: Jezero 2.3 C, Olympus -0.8 C, Valles 1.9 C). On Earth it is mean plus half the swing. It is its own dimension so it never changes Moon results.
Used for: Thermal cycling preset, on Mars sites.

## Albedo: how bright is the ground

**8. Surface albedo, 0 to 1. Scale 0.3.**
The share of sunlight the ground reflects. 0 is black (reflects nothing), 1 is a perfect mirror. Fresh snow is very bright, dark volcanic rock is dark, sand is in between.
Examples: Valles Marineris 0.128 (dark), Jezero 0.165, Olympus Mons 0.301 (bright dust).
Used for: telling ice and snow (bright) from rock and soil (dark). It also tells you how much sunlight a surface warms from. Earth uses NASA MODIS satellite data, Mars uses MGS TES. **The Moon has no albedo in the project**, because we have no valid Moon albedo map, so Moon scores leave it out.
Caveat: one Earth square averages everything inside it, ice included, so a bright glacier next to dark lava makes a middle value.

## Air temperature (shown, never scored)

**9. Mean air temperature (2 m), degrees C** and **10. Annual air temperature range, degrees C.**
Air temperature at head height, from WorldClim 2.1. Shown for Earth places as background. They are never scored because the Moon has no air and Mars's air is too thin for this to be comparable to the ground temperature.

## Geology tags (recorded, weight 0)

**11. Geology tags.**
Words the team chose for the named sites, such as: acid-water, basalt, canyon, dry, dry-lakebed, ice, impact-crater, iron-minerals, layered-rock, permafrost, plain, polar, regolith, salt, sedimentary, shield-volcano, volcanic.
Used for: reading and explaining named pairs ("both are polar impact craters with ice"). They have no citation yet, so their weight is 0: they are shown but never change a score.

---

## Where each feature is used

| Where in the app | Features used |
|---|---|
| Click a Moon point, then Find similar places | slope (steep and typical), relief, landform shape, mean temperature, swing (temperature left out where Diviner has no data) |
| Click a Mars point, then Find similar places | slope (steep and typical), relief, landform shape, albedo |
| Question: Rover mobility | steep slope, typical slope, relief, albedo |
| Question: Landing hazard | steep slope, relief |
| Question: Thermal cycling | mean temperature, swing, daytime temperature, albedo |
| Question: Thermal cycling on a clicked Mars point | cannot be answered: no temperature there, and the app says so |
| Question: Everything measured | every feature that has a real value at that point |
| Named sites (Match, Profile, Data tabs) | all scored features, with the geology tags shown but not scored |
| GIS maps | each feature as its own map layer, plus the "Earth Analog" maps showing the best Earth match for every point |
| Gap map "Earth Analog" (Moon) | terrain and landform; and terrain, landform and temperature |
| Gap map "Analog + Albedo" (Mars) | terrain, landform and albedo |

## Remember
- The numbers describe a square about 111 km wide, so small features such as one crater are averaged away.
- Where there is no real measurement the app shows "No sourced value" and leaves the feature out. It never guesses.
- The scales in the table are our starting guesses, not scientific constants. They decide how strict "close" is.
- Earth has no matching gravity, vacuum or radiation, so a high score covers only the features above.
