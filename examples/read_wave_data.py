#!/usr/bin/env python3
"""
Example: Reading GFS Wave Data from Zarr

This script demonstrates how to load and work with the GFS wave forecast data.
"""

import xarray as xr
import matplotlib.pyplot as plt
from pathlib import Path


def main():
    # Path to Zarr store
    zarr_path = Path("../data/gfs_wave.zarr")

    if not zarr_path.exists():
        print(f"Error: Zarr store not found at {zarr_path}")
        print("Run 'python scripts/update_gfs_wave.py' first to download data")
        return

    # Load the dataset
    print("Loading GFS wave data from Zarr...")
    ds = xr.open_zarr(zarr_path)

    # Display dataset information
    print("\n=== Dataset Overview ===")
    print(ds)

    print("\n=== Dataset Attributes ===")
    for key, value in ds.attrs.items():
        print(f"{key}: {value}")

    print("\n=== Available Variables ===")
    for var in ds.data_vars:
        print(f"- {var}: {ds[var].attrs.get('long_name', 'No description')}")

    # Example 1: Get wave height at a specific location
    print("\n=== Example 1: Wave Height at Specific Location ===")
    lat, lon = 40.0, -70.0  # Atlantic Ocean
    point = ds.sel(latitude=lat, longitude=lon, method='nearest')

    print(f"Location: {lat}°N, {lon}°W")
    print(f"Wave Height (HTSGW) forecast:")
    if 'HTSGW' in point:
        print(point['HTSGW'].values)
    else:
        print("HTSGW not available in dataset")

    # Example 2: Plot global wave height for first forecast hour
    print("\n=== Example 2: Plotting Global Wave Height ===")
    if 'HTSGW' in ds:
        fig, ax = plt.subplots(figsize=(12, 6))
        ds['HTSGW'].isel(step=0).plot(ax=ax, cmap='viridis')
        ax.set_title('GFS Wave Height Forecast (Hour 0)')
        plt.tight_layout()
        plt.savefig('wave_height_global.png', dpi=150, bbox_inches='tight')
        print("Saved plot to 'wave_height_global.png'")
    else:
        print("HTSGW not available for plotting")

    # Example 3: Time series at a location
    print("\n=== Example 3: Time Series at Location ===")
    if 'HTSGW' in point:
        fig, ax = plt.subplots(figsize=(10, 4))
        point['HTSGW'].plot(ax=ax)
        ax.set_xlabel('Forecast Time')
        ax.set_ylabel('Wave Height (m)')
        ax.set_title(f'Wave Height Forecast at {lat}°N, {lon}°W')
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig('wave_height_timeseries.png', dpi=150, bbox_inches='tight')
        print("Saved plot to 'wave_height_timeseries.png'")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
