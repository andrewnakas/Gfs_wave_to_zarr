// Global variables
let map;
let velocityLayer;
let selectedMarker;
let waveData = null;

// Initialize the map
function initMap() {
    map = L.map('map', {
        center: [30, -60],
        zoom: 3,
        minZoom: 2,
        maxZoom: 8
    });

    // Add base map (dark theme)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);

    // Add click handler
    map.on('click', handleMapClick);
}

// Load wave data and create velocity layer
async function loadWaveData() {
    try {
        const response = await fetch('wave_velocity.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        waveData = await response.json();

        // Create velocity layer
        velocityLayer = L.velocityLayer({
            displayValues: true,
            displayOptions: {
                velocityType: 'Wave',
                position: 'bottomleft',
                emptyString: 'No wave data',
                angleConvention: 'meteoCW',
                displayPosition: 'bottomleft',
                displayEmptyString: 'No wave data',
                speedUnit: 'm/s'
            },
            data: waveData,
            maxVelocity: 15,
            velocityScale: 0.01,
            colorScale: [
                "#313695",
                "#4575b4",
                "#74add1",
                "#abd9e9",
                "#e0f3f8",
                "#fee090",
                "#fdae61",
                "#f46d43",
                "#d73027",
                "#a50026"
            ],
            opacity: 0.97,
            particleAge: 90,
            particleMultiplier: 0.005
        });

        velocityLayer.addTo(map);

        // Hide loading screen
        document.getElementById('loading').classList.add('hidden');

    } catch (error) {
        console.error('Error loading wave data:', error);
        document.getElementById('loading').innerHTML =
            '<div style="color: #e53935;">Failed to load wave data. Please try again later.</div>';
    }
}

// Handle map click
function handleMapClick(e) {
    const lat = e.latlng.lat;
    const lon = e.latlng.lng;

    // Remove previous marker
    if (selectedMarker) {
        map.removeLayer(selectedMarker);
    }

    // Add new marker
    const icon = L.divIcon({
        className: 'selected-marker',
        iconSize: [20, 20]
    });

    selectedMarker = L.marker([lat, lon], { icon: icon }).addTo(map);

    // Get forecast data for this location
    getForecastData(lat, lon);
}

// Get forecast data for a location
async function getForecastData(lat, lon) {
    try {
        const response = await fetch('wave_forecast.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const forecastData = await response.json();

        // Find nearest grid point
        const nearest = findNearestPoint(lat, lon, forecastData);

        if (nearest) {
            displayForecastData(lat, lon, nearest);
        } else {
            showError('No data available for this location');
        }

    } catch (error) {
        console.error('Error loading forecast data:', error);
        showError('Failed to load forecast data');
    }
}

// Find nearest grid point
function findNearestPoint(targetLat, targetLon, data) {
    let minDist = Infinity;
    let nearest = null;

    // Normalize longitude to -180 to 180
    targetLon = ((targetLon + 180) % 360) - 180;

    for (const point of data.points) {
        let pointLon = point.lon;
        pointLon = ((pointLon + 180) % 360) - 180;

        const dist = Math.sqrt(
            Math.pow(targetLat - point.lat, 2) +
            Math.pow(targetLon - pointLon, 2)
        );

        if (dist < minDist) {
            minDist = dist;
            nearest = point;
        }
    }

    return nearest;
}

// Display forecast data
function displayForecastData(lat, lon, data) {
    const forecastPanel = document.getElementById('forecastData');
    const locationInfo = document.getElementById('locationInfo');
    const waveHeight = document.getElementById('waveHeight');
    const waveDetails = document.getElementById('waveDetails');
    const timestamp = document.getElementById('timestamp');

    // Show forecast panel
    forecastPanel.classList.add('active');

    // Location info
    locationInfo.innerHTML = `
        <strong>Latitude:</strong> ${lat.toFixed(2)}°<br>
        <strong>Longitude:</strong> ${lon.toFixed(2)}°
    `;

    // Current wave height (first forecast hour)
    const currentHeight = data.wave_height[0];
    waveHeight.innerHTML = `
        ${currentHeight ? currentHeight.toFixed(2) : 'N/A'} <span class="unit">meters</span>
    `;

    // Wave details
    let detailsHTML = '';

    if (data.wave_period && data.wave_period[0]) {
        detailsHTML += `
            <div class="data-item">
                <span class="data-label">Wave Period</span>
                <span class="data-value">${data.wave_period[0].toFixed(1)} s</span>
            </div>
        `;
    }

    if (data.wave_direction && data.wave_direction[0]) {
        detailsHTML += `
            <div class="data-item">
                <span class="data-label">Wave Direction</span>
                <span class="data-value">${data.wave_direction[0].toFixed(0)}°</span>
            </div>
        `;
    }

    if (data.wind_wave_height && data.wind_wave_height[0]) {
        detailsHTML += `
            <div class="data-item">
                <span class="data-label">Wind Wave Height</span>
                <span class="data-value">${data.wind_wave_height[0].toFixed(2)} m</span>
            </div>
        `;
    }

    if (data.swell_height && data.swell_height[0]) {
        detailsHTML += `
            <div class="data-item">
                <span class="data-label">Swell Height</span>
                <span class="data-value">${data.swell_height[0].toFixed(2)} m</span>
            </div>
        `;
    }

    if (data.swell_period && data.swell_period[0]) {
        detailsHTML += `
            <div class="data-item">
                <span class="data-label">Swell Period</span>
                <span class="data-value">${data.swell_period[0].toFixed(1)} s</span>
            </div>
        `;
    }

    waveDetails.innerHTML = detailsHTML;

    // Timestamp
    if (data.forecast_times && data.forecast_times.length > 0) {
        timestamp.innerHTML = `
            Forecast valid: ${data.forecast_times[0]}<br>
            Updated: ${data.cycle || 'N/A'}
        `;
    }

    // Hide error if showing
    document.getElementById('error').classList.remove('active');
}

// Show error message
function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = message;
    errorDiv.classList.add('active');

    setTimeout(() => {
        errorDiv.classList.remove('active');
    }, 5000);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    loadWaveData();
});
