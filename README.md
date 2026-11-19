# Earth Analogs Explorer

*This is cloned repo, (click here)[https://github.com/Phyokyawkaung/Pipilapu_NASA.git] for original repo*

Interactive 3D Planetary Geovisualization, Comparative Terrestrial Analogs Engine, and Extraterrestrial Base Siting Planner.

Developed for the NASA International Space Apps Challenge ("Earth Analogs for Moon and Mars").

---

## Executive Overview

The Earth Analogs Explorer is a scientific geovisualization and planetary comparative analysis platform designed to identify, evaluate, and visualize terrestrial sites that best replicate physical, morphological, and environmental conditions found on the Moon and Mars.

Terrestrial analogs are indispensable for planetary exploration missions: they provide accessible proving grounds for rover mobility, autonomous navigation, spacesuit mobility trials, in-situ resource utilization (ISRU) testing, and instrument calibration. This platform eliminates subjective guessing by applying a rigorous quantitative similarity framework across empirical remote-sensing datasets from NASA, NOAA, and USGS.

In addition to analog matching, the system integrates a parametric surface infrastructure planner that optimizes lunar and martian base layouts on high-resolution digital elevation models (DEMs), taking into account local slopes, solar illumination, and direct line-of-sight communications with Earth.

---

## Key Capabilities

### 1. Interactive 3D Planetary System
- Real-time Three.js WebGL visualization of Earth, the Moon, and Mars.
- Seamless orbital transitions, planetary surface focus, dynamic lighting, and site markers for historic missions and candidate landing sites.
- Self-contained offline capability with local texture fallbacks and bundled dependencies.

### 2. Terrestrial Analog Engine ("Find on Earth")
- Compares target locations on the Moon or Mars against a global 1-degree terrestrial grid comprising approximately 25,000 land cells.
- Evaluates similarity across four scientific dimensions: Terrain, Landform, Thermal Regimes, and Shortwave Albedo.
- Computes match percentages, dimensional score breakdowns, and rankings (e.g., "Top 0.1% of Earth").
- Generates automated analytical summaries detailing where the terrestrial analogy is scientifically robust, where it breaks down, and suitable experimental applications.

### 3. Arbitrary Planetary Probing ("Pick Any Point")
- Interactively select any 1-degree coordinate on the Moon or Mars.
- Instantly queries a pre-computed 111 km planetary surface patch (derived from LRO LOLA and MGS MOLA global mosaics).
- Executes real-time similarity queries across the entire Earth grid to identify the closest terrestrial analogs for any arbitrary extraterrestrial point.

### 4. Planetary GIS Environmental Layers
- Continuous 1-degree planetary environmental rasters across Earth (8 layers), Moon (6 layers), and Mars (4 layers).
- Scientific color ramps with real-time opacity controls, bilinear interpolation toggles, and dynamic scale legends.
- Click-to-probe inspector displaying exact coordinate values and raw measurements.

### 5. Specialized Mission Presets
- Custom weighting matrices tailored for specific mission validation questions:
  - **Rover Mobility:** Prioritizes slope medians, local relief, and surface albedo (identifying bedrock vs. soft sediment or snow/ice).
  - **Landing Hazards:** Evaluates extreme terrain variation using 90th percentile slope and peak-to-valley relief.
  - **Thermal Cycling:** Matches diurnal surface temperature swing, mean skin temperature, and solar absorption.

### 6. Extraterrestrial Base Siting & Infrastructure Planner
- Interactive parametric surface engineering tool executing over real high-resolution terrain patches (e.g., 20 m/pixel LOLA DEM at Shackleton Crater, USGS MOLA-HRSC 200 m at Jezero Crater).
- Procedural placement and safety zone buffering for critical infrastructure:
  - Primary Habitation Module
  - Photovoltaic Arrays and Energy Storage Systems
  - Surface Fission Power Reactor (with safety exclusion buffer)
  - Launch / Landing Pads (with dust ejecta standoff distances)
  - Communication Antennas (constrained by direct line-of-sight to Earth)
  - In-Situ Volatile / Ice Prospecting Corridors
- Slope-constrained least-cost transit pathing for surface rovers and utility corridors.
- Mission architectural sizing based on NASA mission parameters (e.g., Artemis Base Camp concept, Mars Design Reference Architecture 5.0).

---

## Scientific Methodology & Scoring Model

### Similarity Metric Formulation
To compare continuous geospatial measurements without artificial distortion, each individual feature $i$ is evaluated using a normalized linear distance function bounded within $[0, 1]$:

$$S_i = \max\left(0, 1 - \frac{|x_{\text{target}} - x_{\text{candidate}}|}{\sigma_i}\right)$$

Where:
- $x_{\text{target}}$ is the empirical value measured at the lunar or martian target site.
- $x_{\text{candidate}}$ is the measured value for a candidate 1-degree Earth grid cell.
- $\sigma_i$ is the empirical feature scale representing the divergence threshold at which the physical analogy breaks down completely.

### Feature Parameters and Scaling Thresholds
| Dimension | Feature Metric | Scale ($\sigma$) | Physical Rationale |
|---|---|---|---|
| **Terrain** | Steep Slope (90th Percentile) | 15.0 deg | Captures cliff faces, crater walls, and acute landing hazards. |
| **Terrain** | Typical Slope (Median) | 10.0 deg | Reflects nominal traverse gradients for robotic and crewed rovers. |
| **Landform** | Local Relief | 2000.0 m | Elevation delta (95th - 5th percentile) within a 111 km window. |
| **Landform** | Hypsometric Integral | 0.50 | Convexity/concavity index describing stage of geomorphic landscape evolution. |
| **Thermal** | Mean Skin Temperature | 120.0 deg C | Average diurnal surface equilibrium temperature. |
| **Thermal** | Diurnal Temperature Swing | 120.0 deg C | Day-night surface temperature variation. |
| **Day Thermal** | Daytime Skin Temperature | 100.0 deg C | Peak insolation skin temperature (used for Mars site evaluations). |
| **Albedo** | Shortwave Surface Albedo | 0.40 | Ratio of reflected to incoming solar radiation (0.0 to 1.0). |

### Composite Dimensional Weighting
1. Features are grouped into distinct physical dimensions ($D_k \in \{\text{Terrain}, \text{Landform}, \text{Thermal}, \text{Albedo}\}$).
2. Each active dimension is weighted equally in the final composite score:
   $$S_{\text{total}} = \frac{1}{|D_{\text{active}}|} \sum_{d \in D_{\text{active}}} \left( \frac{1}{|F_d|} \sum_{i \in F_d} S_i \right)$$
3. **Strict Completeness Constraint:** A terrestrial cell is scored only if verified empirical data exists across all active dimensions. Missing attributes in a candidate cell prevent partial scoring, eliminating false high-ranking anomalies (e.g., coastal cells cannot register false 100% scores on isolated features).

---

## Empirical Planetary Datasets

The platform enforces a strict data provenance standard: every metric is derived directly from peer-reviewed, open-access instruments and mission archives. No placeholder or synthetic numbers are utilized.

### 1. Earth Datasets
- **Topography and Slope:** NOAA NCEI ETOPO 2022 Global Relief Model (ice surface, 60 arc-second resolution).
- **Land Surface Temperature:** NASA MODIS Terra MOD11C3 Version 6.1 (12-month diurnal land surface temperature composite at 0.05 degree resolution).
- **Shortwave Albedo:** NASA MODIS MCD43C3 Version 6.1 BRDF/Albedo product (white-sky shortwave albedo 0.3-5.0 um).
- **Bioclimatic Air Temperatures:** WorldClim Version 2.1 (BIO1 annual mean, BIO7 annual range; displayed for environmental context, excluded from extraterrestrial scoring).
- **Geopolitical Boundaries:** Natural Earth 1:10m Admin 0 and Admin 1 public domain cartographic boundaries.

### 2. Lunar Datasets
- **Global Elevation and Slopes:** NASA Lunar Reconnaissance Orbiter (LRO) Lunar Orbiter Laser Altimeter (LOLA) Gridded Data Record (LDEM_16, 16 pixels/degree).
- **Apollo 11 Tranquility Base DEM:** USGS Astrogeology LRO LOLA Global DEM (118 m/pixel).
- **Shackleton Crater High-Resolution Siting:** NASA Planetary Geodesy Data Archive (PGDA) Product 90 LOLA South Pole DEM (20 m/pixel) by Barker et al. (2023), paired with PGDA solar illumination and Earth-visibility probability layers.
- **Surface Skin Temperature:** LRO Diviner Lunar Radiometer Experiment Level 4 Global Cumulative Product (bolometric surface temperature, 0.5-degree bins sampled at 10:15-10:45 and 22:15-22:45 local solar time to align with MODIS orbital passes).

### 3. Martian Datasets
- **Global Topography and Slopes:** USGS Astrogeology Mars Global Surveyor (MGS) Mars Orbiter Laser Altimeter (MOLA) Global DEM (463 m/pixel).
- **Candidate Site DEMs (Jezero, Olympus Mons, Valles Marineris):** USGS Mars MOLA-HRSC Blended DEM Mosaic Version 2 (200 m/pixel) by Fergason et al. (2018).
- **Daytime Surface Temperature:** MGS Thermal Emission Spectrometer (TES) Standard Data Products (surface day observations, 13:20-14:54 local time, filtered for clear atmospheric optical depth).
- **Global Bolometric Albedo:** USGS Astrogeology MGS TES Global Bolometric Albedo Map (7410 m/pixel) by Christensen et al. (2001).

---

## System Architecture

The project is architected with a decoupled model: an offline computational Python pipeline processes raw multi-gigabyte raster archives into compact, web-optimized binary payloads, which are rendered client-side by a zero-build WebGL application.

```
Pipilapu_NASA/
|-- docs/                          Production Web Application (Static)
|   |-- index.html                 Main UI, 3D Canvas, Geospatial Panels, GIS Raster Engine
|   |-- planner.js                 Parametric Base Siting and Optimization Engine
|   |-- textures.js                Fallback Procedural Planet Textures
|   |-- FEATURE_GUIDE.md           Comprehensive Feature Metric Documentation
|   |-- SOURCES_AND_METHODS.md     Scientific Provenance, Data Ingestion, Processing Methodology
|   |-- LIMITATIONS.md             Model Assumptions, Boundary Conditions, Spatial Trade-offs
|   |-- PLAIN_GUIDE.md             Plain-Language Educational Overview
|   |-- assets/textures/           High-Resolution Planetary Surface Maps
|   |-- vendor/three-0.128.0/      Standalone Three.js Engine and OrbitControls (MIT)
|   `-- data/                      Optimized Scientific Payloads
|       |-- grid.json, *.bin       Global 1-Degree Earth Grid (Binary float32 layers)
|       |-- targets.json           Precomputed Metrics for Key Lunar/Martian Sites
|       |-- moon_grid.json, *.bin  Precomputed Lunar Surface Metric Grid
|       |-- mars_grid.json, *.bin  Precomputed Martian Surface Metric Grid
|       |-- places.json            Indexed Global Administrative Gazetteer
|       |-- siting.json            Siting Rules, Physical Constants, Mission Presets
|       `-- siting/<site>.json     High-Resolution DEM Patches for Base Planner
|-- pipeline/                      Python Geospatial Data Pipeline
|   |-- fetch_data.py              Automated Raw Dataset Ingestion and Checksum Validation
|   |-- build_grid.py              Earth Grid Generation from Global GeoTIFF Rasters
|   |-- build_targets.py           Target Measurement Extraction over 111 km Patches
|   |-- build_body_grid.py         Global Planetary Surface Grid Builder (Moon/Mars)
|   |-- build_site_terrain.py      Base Planner High-Resolution Elevation Patch Generator
|   |-- build_named_sites.py       Metadata Synthesis for Curated Terrestrial Analog Sites
|   |-- build_places.py            Natural Earth Administrative Feature Mapping
|   |-- prep_lst.py                MODIS Terra HDF Land Surface Temperature Processing
|   |-- prep_diviner.py            LRO Diviner Bolometric Table Processing
|   |-- prep_tes.py                MGS TES Temperature Record Processing
|   |-- prep_albedo.py             MODIS MCD43C3 Shortwave Albedo Processing
|   |-- finder_pipeline.py         Shared Geospatial Algorithms (Slope, Hypsometry, Relief)
|   |-- raster_io.py               GeoTIFF and Raster Transformation Utilities
|   `-- requirements.txt           Pipeline Python Dependencies
|-- vercel.json                    Static Deployment and Cache Control Configuration
`-- README.md                      Project Showcase and Technical Documentation
```

---

## Quickstart: Running the Web Application

The web interface is completely self-contained. It requires no Node.js compilation, package installations, or external build steps.

### Prerequisites
- Python 3.9 or higher (used solely to serve files locally via HTTP).
- A modern web browser supporting WebGL (Chrome, Edge, Firefox, Safari).

### Launching Locally
1. Clone or download the repository:
   ```bash
   git clone <repository-url>
   cd Pipilapu_NASA
   ```

2. Start a local HTTP server:
   ```bash
   python3 -m http.server 8000
   ```

3. Open the application in your browser:
   ```
   http://localhost:8000/docs/
   ```

*(Note: Browsers restrict local file `fetch` requests when launched directly via `file://`. Running via a local HTTP server ensures all binary data layers and textures load properly.)*

---

## Data Pipeline: Reproducing from Source

The repository includes pre-built binary data files in `docs/data/`, enabling immediate out-of-the-box execution without processing raw planetary rasters. 

For full scientific reproducibility or dataset updates, the complete pipeline can be re-executed using the scripts in `pipeline/`.

### 1. Environment Setup
```bash
pip install -r pipeline/requirements.txt
```
Key libraries: `numpy`, `rasterio`, `pyhdf`, `requests`.

### 2. Download Raw Datasets
```bash
python pipeline/fetch_data.py --only earth
python pipeline/fetch_data.py --only moon
```
*Note: Datasets requiring NASA Earthdata authentication (such as MODIS LST) require free Earthdata login credentials.*

### 3. Generate Geospatial Grids
- **Earth Multi-Feature Grid:**
  ```bash
  python pipeline/build_grid.py
  ```
- **Moon & Mars Named Target Metrics:**
  ```bash
  python pipeline/build_targets.py
  ```
- **Global Planetary Grids ("Pick Any Point"):**
  ```bash
  python pipeline/build_body_grid.py --body moon --dem pipeline/raw/moon_dem/ldem_16.lbl
  python pipeline/build_body_grid.py --body mars --dem pipeline/raw/mars_dem/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif
  ```
- **High-Resolution Base Siting Terrain Patches:**
  ```bash
  python pipeline/build_site_terrain.py --site shackleton
  python pipeline/build_site_terrain.py --site jezero
  ```

---

## Deployment

### GitHub Pages
1. Push the repository to GitHub.
2. In the repository settings, navigate to **Pages**.
3. Under **Build and deployment > Source**, select **Deploy from a branch**.
4. Choose the `main` branch and specify the `/docs` folder.
5. The application will be live at `https://<username>.github.io/<repo>/`.

### Vercel
The repository includes a ready-to-use `vercel.json` configuring static output routing to `docs/` and enforcing proper cache-control headers on static binary arrays:
```bash
vercel --prod
```

---

## Scientific Documentation

For comprehensive technical derivations, data limitations, and operational guides, consult the reference documents in the `docs/` directory:
- [FEATURE_GUIDE.md](docs/FEATURE_GUIDE.md): Mathematical definitions and physical significance of all measured features.
- [SOURCES_AND_METHODS.md](docs/SOURCES_AND_METHODS.md): In-depth sensor specifications, data processing algorithms, and calibration protocols.
- [LIMITATIONS.md](docs/LIMITATIONS.md): Critical analysis of spatial resolution constraints, sensor disparities, and analytical limits.
- [PLAIN_GUIDE.md](docs/PLAIN_GUIDE.md): Non-technical overview for educational and outreach use.

---

## Acknowledgments & Data Sources

- **NASA International Space Apps Challenge:** Challenge design and operational framework.
- **NASA Planetary Data System (PDS) Geosciences Node:** LRO LOLA, LRO Diviner, and MGS TES datasets.
- **USGS Astrogeology Science Center:** High-resolution blended DEMs for Moon and Mars.
- **NASA Land Processes Distributed Active Archive Center (LP DAAC):** MODIS Terra Land Surface Temperature and Albedo products.
- **NOAA National Centers for Environmental Information (NCEI):** ETOPO 2022 Global Relief Model.
- **Natural Earth:** Public domain cartographic vector datasets.
# Earth-Analogs
