# GFS Wave Data to Zarr

Automated pipeline to download NOAA GFS wave forecast data and convert it to cloud-optimized Zarr format with interactive web visualization.

## 🌊 Live Visualization

**[View Live Wave Forecast Map](https://andrewnakas.github.io/Gfs_wave_to_zarr/)**

Interactive global wave forecast visualization featuring:
- Real-time particle animation using leaflet-velocity
- Click anywhere on the map to see detailed wave data
- Updated every 6 hours with latest GFS model runs
- Wave height, period, direction, wind waves, and swell data

## Overview

This project uses GitHub Actions to automatically:
- Download GFS wave model forecasts from NOAA NOMADS every 6 hours
- Convert GRIB2 data to compressed Zarr format
- Generate JSON data for web visualization
- Deploy interactive map to GitHub Pages
- Maintain only the latest forecast to prevent storage bloat
- Provide easy access to wave forecast data via xarray

## Wave Variables Included

The dataset includes the following wave parameters:

- **HTSGW**: Significant height of combined wind waves and swell (m)
- **PERPW**: Primary wave mean period (s)
- **DIRPW**: Primary wave direction (degrees)
- **WVHGT**: Significant height of wind waves (m)
- **WVPER**: Mean period of wind waves (s)
- **WVDIR**: Direction of wind waves (degrees)
- **SWELL**: Significant height of swell waves (m)
- **SWPER**: Mean period of swell waves (s)
- **SWDIR**: Direction of swell waves (degrees)

## Data Specifications

- **Source**: NOAA GFS Wave Model (0.16° resolution, global)
- **Update Frequency**: Every 6 hours (00Z, 06Z, 12Z, 18Z cycles)
- **Forecast Range**: 0-72 hours (3 days) in 3-hour increments
- **Compression**: Zstd level 3 with Blosc
- **Storage**: Rolling dataset (only latest forecast maintained)
- **Note**: Zarr data is generated temporarily for web visualization, only JSON files are stored

## Usage

### Accessing the Data

Clone this repository and load the Zarr data with xarray:

```python
import xarray as xr

# Open the Zarr store
ds = xr.open_zarr('data/gfs_wave.zarr')

# View the dataset
print(ds)

# Access specific variables
wave_height = ds['HTSGW']  # Significant wave height
wave_period = ds['PERPW']  # Wave period
wave_direction = ds['DIRPW']  # Wave direction

# Select data for a specific location
lat, lon = 40.0, -70.0  # Example: Atlantic Ocean
point_data = ds.sel(latitude=lat, longitude=lon, method='nearest')

# Plot wave height forecast
wave_height.isel(step=0).plot()
```

### Running Locally

To update the data manually:

```bash
# Install dependencies
pip install -r requirements.txt

# Install system dependencies (Ubuntu/Debian)
sudo apt-get install libeccodes-dev

# Run the update script
python scripts/update_gfs_wave.py
```

## GitHub Actions Workflow

The workflow runs automatically:
- **Schedule**: 30 minutes after each GFS cycle completes (05:30, 11:30, 17:30, 23:30 UTC)
- **Manual**: Trigger via "Actions" tab → "Update GFS Wave Data" → "Run workflow"
- **On Push**: Runs when pushing to Claude branches (`claude/**`)

The workflow:
1. Downloads latest GFS wave GRIB2 files
2. Converts to Zarr with compression
3. Removes old Zarr store (rolling dataset)
4. Commits and pushes updated data

## Storage Management

The pipeline implements automatic cleanup:
- Old Zarr stores are deleted before saving new data
- Temporary GRIB2 files are removed after processing
- Only one forecast cycle is kept at a time
- Typical storage: 50-200 MB per cycle (compressed)

## Data Source

Data is sourced from NOAA NOMADS:
```
https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/
```

GFS wave forecasts are produced by NOAA's National Centers for Environmental Prediction (NCEP).

## Requirements

- Python 3.11+
- xarray
- zarr
- cfgrib
- eccodes
- numpy
- requests
- numcodecs
- dask

## License

This project is open source. The GFS wave data is public domain from NOAA.

## References

- [GFS Wave Model Documentation](https://www.emc.ncep.noaa.gov/emc/pages/numerical_forecast/gfswave.php)
- [NOMADS Data Server](https://nomads.ncep.noaa.gov/)
- [Zarr Format](https://zarr.readthedocs.io/)
