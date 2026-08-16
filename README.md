# Bartlett PD — Patrol Allocation Dashboard

## Setup

```bash
cd patrol_dashboard
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Add the zone boundary shapefile

Copy your shapefile set into the `PATROL_DISTRICTS_2025/` folder so it looks like:

```
PATROL_DISTRICTS_2025/
  PATROL_DISTRICTS_2025.shp
  PATROL_DISTRICTS_2025.dbf
  PATROL_DISTRICTS_2025.shx
  PATROL_DISTRICTS_2025.prj
```

The app auto-detects the zone-id field in the shapefile by checking common
names (`ZONE_ID`, `ZONE`, `Zone`, `zone_id`, `PATROL_ZON`, `DISTRICT`, `Name`, `Id`, ...).
If your field is named something else, open `utils/config.py` and set:

```python
SHAPEFILE_ZONE_FIELD_OVERRIDE = "YOUR_FIELD_NAME"
```

Until the shapefile is added, the app runs fine using zone center-point
markers (from `data/zone_schedule.csv`) as a fallback — no crash, no missing
pages.

## Run

```bash
streamlit run app.py
```

## Data folder

All CSV/XLSX result files already live in `data/`. To refresh with new runs,
just overwrite the files with the same names (or add new
`dynamic_alloc_<date>_*.csv` / `gis_alloc_<date>_<Day>_<Shift>.csv` files —
the app picks up any file matching those patterns automatically).

## Project structure

```
patrol_dashboard/
├── app.py                              # Landing page + citywide snapshot
├── pages/
│   ├── 1_📊_Data_Insights.py           # Filterable spatial/temporal analytics
│   ├── 2_🗺️_Allocation_Comparison.py   # Uniform/Static/Dynamic maps by date+shift
│   └── 3_❓_Help_Guide.py              # Plain-language how-to-read guide
├── utils/
│   ├── config.py                       # Paths, zone-key mapping, display names
│   ├── data_loader.py                  # Cached CSV/XLSX loaders
│   ├── geo_utils.py                    # Shapefile loading + centroid fallback
│   └── interpret.py                    # Filter-reactive interpretation text
├── data/                               # All result CSVs/XLSX
├── PATROL_DISTRICTS_2025/              # <-- put your shapefile set here
└── requirements.txt
```
