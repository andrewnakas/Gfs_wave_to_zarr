#!/usr/bin/env python3
"""
GFS Wave Data to Zarr Converter

Downloads GFS wave forecast data from NOAA NOMADS, converts to Zarr format,
and manages storage by maintaining only the latest forecast.
"""

import os
import sys
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path
import requests
import xarray as xr
import zarr
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod"
DATA_DIR = Path("data")
TEMP_DIR = Path("temp")
ZARR_STORE = DATA_DIR / "gfs_wave.zarr"

# Wave variables to download
WAVE_VARS = [
    'HTSGW',  # Significant height of combined wind waves and swell
    'PERPW',  # Primary wave mean period
    'DIRPW',  # Primary wave direction
    'WVHGT',  # Significant height of wind waves
    'WVPER',  # Mean period of wind waves
    'WVDIR',  # Direction of wind waves
    'SWELL',  # Significant height of swell waves
    'SWPER',  # Mean period of swell waves
    'SWDIR',  # Direction of swell waves
]


def get_latest_cycle():
    """
    Determine the latest available GFS cycle.
    GFS runs at 00, 06, 12, 18 UTC with ~4 hour delay.
    """
    now = datetime.utcnow()
    # Subtract 5 hours to account for processing delay
    cycle_time = now - timedelta(hours=5)

    # Round down to nearest 6-hour cycle
    cycle_hour = (cycle_time.hour // 6) * 6
    cycle = cycle_time.replace(hour=cycle_hour, minute=0, second=0, microsecond=0)

    return cycle


def build_grib_url(cycle, forecast_hour):
    """
    Build URL for GFS wave GRIB2 file.

    Args:
        cycle: datetime object for the model cycle
        forecast_hour: forecast hour (0-384)

    Returns:
        URL string
    """
    cycle_str = cycle.strftime("%Y%m%d/%H")
    filename = f"gfswave.t{cycle.hour:02d}z.global.0p16.f{forecast_hour:03d}.grib2"
    url = f"{BASE_URL}/gfs.{cycle_str}/wave/gridded/{filename}"
    return url


def download_grib_file(url, output_path):
    """
    Download a GRIB2 file from NOAA.

    Args:
        url: URL to download from
        output_path: Path to save the file

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Downloading {url}")
        response = requests.get(url, timeout=300)
        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(response.content)

        logger.info(f"Downloaded {output_path.name} ({len(response.content) / 1024 / 1024:.2f} MB)")
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download {url}: {e}")
        return False


def load_grib_to_dataset(grib_files):
    """
    Load multiple GRIB2 files into a single xarray Dataset.

    Args:
        grib_files: List of GRIB2 file paths

    Returns:
        xarray.Dataset
    """
    datasets = []

    for grib_file in sorted(grib_files):
        try:
            logger.info(f"Loading {grib_file.name}")
            ds = xr.open_dataset(
                grib_file,
                engine='cfgrib',
                backend_kwargs={'indexpath': ''}
            )
            datasets.append(ds)
        except Exception as e:
            logger.warning(f"Failed to load {grib_file}: {e}")

    if not datasets:
        raise ValueError("No GRIB files could be loaded")

    # Combine all forecast hours along time dimension
    combined = xr.concat(datasets, dim='step')
    return combined


def compress_and_save_zarr(dataset, zarr_path):
    """
    Save dataset to Zarr with compression and chunking.

    Args:
        dataset: xarray.Dataset to save
        zarr_path: Path to Zarr store
    """
    # Configure compression
    compressor = zarr.Blosc(cname='zstd', clevel=3, shuffle=2)

    # Set up encoding for each variable
    encoding = {}
    for var in dataset.data_vars:
        encoding[var] = {
            'compressor': compressor,
            'chunks': {
                'step': 1,
                'latitude': 100,
                'longitude': 100,
            }
        }

    # Remove old zarr store if it exists
    if zarr_path.exists():
        logger.info(f"Removing old Zarr store: {zarr_path}")
        shutil.rmtree(zarr_path)

    # Save to Zarr
    logger.info(f"Saving to Zarr: {zarr_path}")
    dataset.to_zarr(
        zarr_path,
        mode='w',
        encoding=encoding,
        consolidated=True
    )

    # Calculate and log storage size
    total_size = sum(f.stat().st_size for f in zarr_path.rglob('*') if f.is_file())
    logger.info(f"Zarr store size: {total_size / 1024 / 1024:.2f} MB")


def cleanup_temp_files():
    """Remove temporary GRIB files."""
    if TEMP_DIR.exists():
        logger.info("Cleaning up temporary files")
        shutil.rmtree(TEMP_DIR)


def main():
    """Main execution function."""
    try:
        # Create directories
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

        # Get the latest model cycle
        cycle = get_latest_cycle()
        logger.info(f"Processing GFS wave cycle: {cycle.strftime('%Y%m%d %HZ')}")

        # Download forecast hours (0 to 120 hours in 3-hour increments)
        # For storage efficiency, we limit to 5 days of forecast
        forecast_hours = list(range(0, 121, 3))
        grib_files = []

        for fh in forecast_hours:
            url = build_grib_url(cycle, fh)
            grib_file = TEMP_DIR / f"gfswave_f{fh:03d}.grib2"

            if download_grib_file(url, grib_file):
                grib_files.append(grib_file)
            else:
                # If we can't download a file, continue with what we have
                logger.warning(f"Skipping forecast hour {fh}")

        if not grib_files:
            logger.error("No GRIB files downloaded successfully")
            sys.exit(1)

        # Load GRIB files into xarray Dataset
        logger.info("Loading GRIB files into xarray Dataset")
        dataset = load_grib_to_dataset(grib_files)

        # Add metadata
        dataset.attrs['title'] = 'GFS Wave Forecast Data'
        dataset.attrs['institution'] = 'NOAA/NCEP'
        dataset.attrs['source'] = 'GFS Wave Model'
        dataset.attrs['cycle'] = cycle.strftime('%Y%m%d%H')
        dataset.attrs['creation_date'] = datetime.utcnow().isoformat()

        # Save to Zarr
        compress_and_save_zarr(dataset, ZARR_STORE)

        # Cleanup
        cleanup_temp_files()

        logger.info("GFS wave data processing completed successfully")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        cleanup_temp_files()
        sys.exit(1)


if __name__ == "__main__":
    main()
