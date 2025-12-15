#!/usr/bin/env python3
"""
Generate JSON files for web visualization from Zarr data

Creates two JSON files:
1. wave_velocity.json - for leaflet-velocity particle animation
2. wave_forecast.json - for point-click forecast data
"""

import json
import logging
from pathlib import Path
import numpy as np
import xarray as xr
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
ZARR_STORE = Path("data/gfs_wave.zarr")
OUTPUT_DIR = Path(".")


def convert_wave_to_uv(direction_deg, magnitude):
    """
    Convert wave direction and magnitude to U/V components.

    Wave direction is the direction FROM which waves are coming (meteorological convention).
    We need to convert to U (east-west) and V (north-south) components.

    Args:
        direction_deg: Wave direction in degrees (0-360, 0=North, 90=East)
        magnitude: Wave magnitude (height or other measure)

    Returns:
        tuple: (u, v) components
    """
    # Convert degrees to radians
    direction_rad = np.deg2rad(direction_deg)

    # Calculate U and V components
    # Note: We negate because direction is FROM, but we want TO
    u = -magnitude * np.sin(direction_rad)
    v = -magnitude * np.cos(direction_rad)

    return u, v


def subsample_grid(data, target_points=10000):
    """
    Subsample grid to reduce data size for web visualization.

    Args:
        data: xarray DataArray with lat/lon dimensions
        target_points: Target number of grid points

    Returns:
        Subsampled data
    """
    # Get dimensions
    dims = data.dims
    lat_dim = [d for d in dims if 'lat' in d.lower()][0]
    lon_dim = [d for d in dims if 'lon' in d.lower()][0]

    lat_size = data.sizes[lat_dim]
    lon_size = data.sizes[lon_dim]

    total_points = lat_size * lon_size

    if total_points <= target_points:
        return data

    # Calculate stride to achieve target points
    stride = int(np.sqrt(total_points / target_points))
    stride = max(1, stride)

    logger.info(f"Subsampling grid from {total_points} to ~{total_points // (stride * stride)} points (stride={stride})")

    # Subsample
    return data.isel({lat_dim: slice(None, None, stride), lon_dim: slice(None, None, stride)})


def generate_velocity_json(dataset):
    """
    Generate leaflet-velocity compatible JSON from wave data.

    Args:
        dataset: xarray Dataset with wave data

    Returns:
        dict: Velocity data in leaflet-velocity format
    """
    logger.info("Generating velocity JSON for particle animation")

    # Get first time step
    ds = dataset.isel(step=0)

    # Get dimensions
    dims = list(ds.dims.keys())
    lat_dim = [d for d in dims if 'lat' in d.lower()][0]
    lon_dim = [d for d in dims if 'lon' in d.lower()][0]

    # Try to get wave direction and height
    wave_height_var = None
    wave_dir_var = None

    for var_name in ['HTSGW', 'htsgw', 'hs', 'swh']:
        if var_name in ds:
            wave_height_var = var_name
            break

    for var_name in ['DIRPW', 'dirpw', 'dir', 'mwd']:
        if var_name in ds:
            wave_dir_var = var_name
            break

    if not wave_height_var or not wave_dir_var:
        logger.warning(f"Could not find wave height or direction. Available vars: {list(ds.data_vars)}")
        # Use first two variables as fallback
        vars_list = list(ds.data_vars)
        wave_height_var = vars_list[0] if len(vars_list) > 0 else None
        wave_dir_var = vars_list[1] if len(vars_list) > 1 else None

    if not wave_height_var or not wave_dir_var:
        raise ValueError("Insufficient data to generate velocity field")

    logger.info(f"Using {wave_height_var} for magnitude and {wave_dir_var} for direction")

    # Subsample for web performance
    height_data = subsample_grid(ds[wave_height_var])
    dir_data = subsample_grid(ds[wave_dir_var])

    # Get coordinates
    lats = height_data[lat_dim].values
    lons = height_data[lon_dim].values

    # Ensure longitude is in -180 to 180 range
    lons = np.where(lons > 180, lons - 360, lons)

    # Convert to U/V components
    u, v = convert_wave_to_uv(dir_data.values, height_data.values)

    # Replace NaN with None for JSON
    u = np.where(np.isnan(u), None, u)
    v = np.where(np.isnan(v), None, v)

    # Create velocity JSON structure
    velocity_data = [
        {
            "header": {
                "parameterCategory": 0,
                "parameterNumber": 2,
                "dx": float(np.median(np.diff(lons))) if len(lons) > 1 else 1.0,
                "dy": float(np.median(np.diff(lats))) if len(lats) > 1 else 1.0,
                "nx": len(lons),
                "ny": len(lats),
                "la1": float(lats[0]),
                "la2": float(lats[-1]),
                "lo1": float(lons[0]),
                "lo2": float(lons[-1]),
                "refTime": dataset.attrs.get('cycle', datetime.now().strftime('%Y%m%d%H'))
            },
            "data": u.flatten().tolist()
        },
        {
            "header": {
                "parameterCategory": 0,
                "parameterNumber": 3,
                "dx": float(np.median(np.diff(lons))) if len(lons) > 1 else 1.0,
                "dy": float(np.median(np.diff(lats))) if len(lats) > 1 else 1.0,
                "nx": len(lons),
                "ny": len(lats),
                "la1": float(lats[0]),
                "la2": float(lats[-1]),
                "lo1": float(lons[0]),
                "lo2": float(lons[-1]),
                "refTime": dataset.attrs.get('cycle', datetime.now().strftime('%Y%m%d%H'))
            },
            "data": v.flatten().tolist()
        }
    ]

    return velocity_data


def generate_forecast_json(dataset):
    """
    Generate forecast data JSON for point selection.

    Args:
        dataset: xarray Dataset with wave data

    Returns:
        dict: Forecast data for all grid points
    """
    logger.info("Generating forecast JSON for point data")

    # Get dimensions
    dims = list(dataset.dims.keys())
    lat_dim = [d for d in dims if 'lat' in d.lower()][0]
    lon_dim = [d for d in dims if 'lon' in d.lower()][0]
    time_dim = [d for d in dims if 'step' in d.lower() or 'time' in d.lower()][0]

    # Subsample grid more aggressively for forecast data (larger file)
    ds_sub = dataset.isel({
        lat_dim: slice(None, None, 4),
        lon_dim: slice(None, None, 4)
    })

    lats = ds_sub[lat_dim].values
    lons = ds_sub[lon_dim].values

    # Ensure longitude is in -180 to 180 range
    lons = np.where(lons > 180, lons - 360, lons)

    # Map variable names
    var_map = {
        'wave_height': ['HTSGW', 'htsgw', 'hs', 'swh'],
        'wave_period': ['PERPW', 'perpw', 'tp', 'mwp'],
        'wave_direction': ['DIRPW', 'dirpw', 'dir', 'mwd'],
        'wind_wave_height': ['WVHGT', 'wvhgt'],
        'swell_height': ['SWELL', 'swell', 'shww'],
        'swell_period': ['SWPER', 'swper'],
        'swell_direction': ['SWDIR', 'swdir']
    }

    # Build forecast points
    points = []

    # Limit to first 10 forecast hours to reduce file size
    n_times = min(10, ds_sub.sizes[time_dim])

    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            point = {
                'lat': float(lat),
                'lon': float(lon)
            }

            # Extract data for each variable
            for key, possible_names in var_map.items():
                for var_name in possible_names:
                    if var_name in ds_sub:
                        data = ds_sub[var_name].isel({
                            lat_dim: i,
                            lon_dim: j,
                            time_dim: slice(0, n_times)
                        }).values

                        # Convert to list, replacing NaN with null
                        data_list = [float(x) if not np.isnan(x) else None for x in data]
                        point[key] = data_list
                        break

            # Add forecast times
            if time_dim in ds_sub:
                times = ds_sub[time_dim].values[:n_times]
                point['forecast_times'] = [str(t) for t in times]

            points.append(point)

    forecast_data = {
        'cycle': dataset.attrs.get('cycle', 'unknown'),
        'creation_date': dataset.attrs.get('creation_date', datetime.utcnow().isoformat()),
        'points': points
    }

    return forecast_data


def main():
    """Main execution function."""
    try:
        if not ZARR_STORE.exists():
            logger.error(f"Zarr store not found: {ZARR_STORE}")
            logger.error("Run update_gfs_wave.py first to download data")
            return

        # Load Zarr data
        logger.info(f"Loading Zarr data from {ZARR_STORE}")
        dataset = xr.open_zarr(ZARR_STORE)

        logger.info(f"Dataset dimensions: {dict(dataset.dims)}")
        logger.info(f"Dataset variables: {list(dataset.data_vars)}")

        # Generate velocity JSON
        velocity_data = generate_velocity_json(dataset)
        velocity_file = OUTPUT_DIR / "wave_velocity.json"

        logger.info(f"Writing velocity data to {velocity_file}")
        with open(velocity_file, 'w') as f:
            json.dump(velocity_data, f)

        logger.info(f"Velocity JSON size: {velocity_file.stat().st_size / 1024 / 1024:.2f} MB")

        # Generate forecast JSON
        forecast_data = generate_forecast_json(dataset)
        forecast_file = OUTPUT_DIR / "wave_forecast.json"

        logger.info(f"Writing forecast data to {forecast_file}")
        with open(forecast_file, 'w') as f:
            json.dump(forecast_data, f)

        logger.info(f"Forecast JSON size: {forecast_file.stat().st_size / 1024 / 1024:.2f} MB")

        logger.info("Web data generation completed successfully")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
