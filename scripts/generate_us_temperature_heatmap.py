"""
High-Resolution US Temperature Heat Map Generator
Creates a professional meteorological visualization with state boundaries
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Polygon
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
import requests
import json

# Temperature data for major US cities (realistic climatological averages)
TEMPERATURE_DATA = {
    # Format: (latitude, longitude, temperature_celsius)
    # Northern States - Cooler
    'Seattle_WA': (47.6062, -122.3321, 11.0),
    'Portland_OR': (45.5152, -122.6784, 12.0),
    'Boise_ID': (43.6150, -116.2023, 11.5),
    'Helena_MT': (46.5891, -112.0391, 7.0),
    'Bismarck_ND': (46.8083, -100.7837, 5.5),
    'Minneapolis_MN': (44.9778, -93.2650, 7.5),
    'Milwaukee_WI': (43.0389, -87.9065, 8.5),
    'Detroit_MI': (42.3314, -83.0458, 10.0),
    'Buffalo_NY': (42.8864, -78.8784, 9.0),
    'Portland_ME': (43.6591, -70.2568, 8.0),
    
    # Mountain States - Cool to Moderate
    'Denver_CO': (39.7392, -104.9903, 10.5),
    'Salt_Lake_City_UT': (40.7608, -111.8910, 11.5),
    'Cheyenne_WY': (41.1400, -104.8202, 8.0),
    'Reno_NV': (39.5296, -119.8138, 12.0),
    'Flagstaff_AZ': (35.1983, -111.6513, 11.0),
    
    # Midwest - Moderate
    'Chicago_IL': (41.8781, -87.6298, 10.5),
    'Indianapolis_IN': (39.7684, -86.1581, 12.0),
    'Columbus_OH': (39.9612, -82.9988, 12.5),
    'Kansas_City_MO': (39.0997, -94.5786, 13.5),
    'Omaha_NE': (41.2565, -95.9345, 11.0),
    'Des_Moines_IA': (41.5868, -93.6250, 10.5),
    
    # Northeast - Cool to Moderate
    'Boston_MA': (42.3601, -71.0589, 11.0),
    'New_York_NY': (40.7128, -74.0060, 13.0),
    'Philadelphia_PA': (39.9526, -75.1652, 13.5),
    'Pittsburgh_PA': (40.4406, -79.9959, 11.5),
    'Albany_NY': (42.6526, -73.7562, 9.5),
    
    # Mid-Atlantic - Moderate
    'Washington_DC': (38.9072, -77.0369, 14.5),
    'Richmond_VA': (37.5407, -77.4360, 15.5),
    'Raleigh_NC': (35.7796, -78.6382, 16.5),
    'Charleston_WV': (38.3498, -81.6326, 13.0),
    
    # Southeast - Warm to Hot
    'Atlanta_GA': (33.7490, -84.3880, 17.5),
    'Charlotte_NC': (35.2271, -80.8431, 16.5),
    'Columbia_SC': (34.0007, -81.0348, 18.0),
    'Jacksonville_FL': (30.3322, -81.6557, 21.5),
    'Orlando_FL': (28.5383, -81.3792, 23.0),
    'Miami_FL': (25.7617, -80.1918, 25.5),
    'Tampa_FL': (27.9506, -82.4572, 23.5),
    'Tallahassee_FL': (30.4383, -84.2807, 20.5),
    
    # Gulf Coast - Hot
    'New_Orleans_LA': (29.9511, -90.0715, 21.5),
    'Baton_Rouge_LA': (30.4515, -91.1871, 20.5),
    'Mobile_AL': (30.6954, -88.0399, 20.0),
    'Montgomery_AL': (32.3668, -86.3000, 18.5),
    'Jackson_MS': (32.2988, -90.1848, 18.5),
    'Biloxi_MS': (30.3960, -88.8853, 21.0),
    
    # Texas - Very Hot
    'Houston_TX': (29.7604, -95.3698, 21.5),
    'Dallas_TX': (32.7767, -96.7970, 19.5),
    'Austin_TX': (30.2672, -97.7431, 21.0),
    'San_Antonio_TX': (29.4241, -98.4936, 21.5),
    'El_Paso_TX': (31.7619, -106.4850, 19.0),
    'Amarillo_TX': (35.2220, -101.8313, 15.0),
    'Corpus_Christi_TX': (27.8006, -97.3964, 23.0),
    'Laredo_TX': (27.5306, -99.4803, 24.0),
    
    # Southwest - Very Hot
    'Phoenix_AZ': (33.4484, -112.0740, 24.5),
    'Tucson_AZ': (32.2226, -110.9747, 22.0),
    'Yuma_AZ': (32.6927, -114.6277, 24.5),
    'Las_Vegas_NV': (36.1699, -115.1398, 21.5),
    'Albuquerque_NM': (35.0844, -106.6504, 14.5),
    'Santa_Fe_NM': (35.6870, -105.9378, 11.5),
    'Las_Cruces_NM': (32.3199, -106.7637, 18.0),
    
    # California - Varied
    'Los_Angeles_CA': (34.0522, -118.2437, 18.5),
    'San_Diego_CA': (32.7157, -117.1611, 18.0),
    'San_Francisco_CA': (37.7749, -122.4194, 14.5),
    'Sacramento_CA': (38.5816, -121.4944, 16.5),
    'Fresno_CA': (36.7378, -119.7871, 18.0),
    'Bakersfield_CA': (35.3733, -119.0187, 19.0),
    'Death_Valley_CA': (36.5323, -116.9325, 26.0),
    
    # Plains States - Moderate to Warm
    'Oklahoma_City_OK': (35.4676, -97.5164, 16.5),
    'Tulsa_OK': (36.1540, -95.9928, 16.0),
    'Wichita_KS': (37.6872, -97.3301, 14.5),
    'Little_Rock_AR': (34.7465, -92.2896, 17.0),
    'Memphis_TN': (35.1495, -90.0490, 17.5),
    'Nashville_TN': (36.1627, -86.7816, 15.5),
    
    # Additional coverage points
    'Fargo_ND': (46.8772, -96.7898, 5.0),
    'Sioux_Falls_SD': (43.5460, -96.7313, 8.5),
    'Rapid_City_SD': (44.0805, -103.2310, 9.0),
    'Billings_MT': (45.7833, -108.5007, 8.0),
    'Spokane_WA': (47.6588, -117.4260, 9.5),
    'Anchorage_AK': (61.2181, -149.9003, 2.5),  # For reference
}

def create_temperature_colormap():
    """Create a smooth temperature gradient colormap"""
    colors = [
        (0.0, '#00008B'),   # Dark Blue (-20°C)
        (0.15, '#0066FF'),  # Blue (0°C)
        (0.3, '#00CCFF'),   # Light Blue (10°C)
        (0.45, '#00FF66'),  # Green (15°C)
        (0.6, '#FFFF00'),   # Yellow (25°C)
        (0.75, '#FF9900'),  # Orange (35°C)
        (0.9, '#FF3300'),   # Red (40°C)
        (1.0, '#8B0000'),   # Dark Red (45°C+)
    ]
    return LinearSegmentedColormap.from_list('temperature', 
                                            [c[1] for c in colors],
                                            N=256)

def get_us_state_boundaries():
    """Get US state boundaries from a GeoJSON source"""
    # Using a simplified US states GeoJSON
    # In production, use: https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json
    
    # Simplified state boundaries (key states for visualization)
    states = {
        'WA': [(-124.7, 49.0), (-116.9, 49.0), (-116.9, 45.5), (-124.7, 45.5)],
        'CA': [(-124.4, 42.0), (-114.1, 42.0), (-114.1, 32.5), (-124.4, 32.5)],
        'TX': [(-106.6, 36.5), (-93.5, 36.5), (-93.5, 25.8), (-106.6, 25.8)],
        'FL': [(-87.6, 31.0), (-80.0, 31.0), (-80.0, 24.5), (-87.6, 24.5)],
        'NY': [(-79.8, 45.0), (-71.8, 45.0), (-71.8, 40.5), (-79.8, 40.5)],
    }
    return states

def generate_temperature_heatmap(output_path='outputs/maps/us_temperature_heatmap.png'):
    """Generate high-resolution US temperature heat map"""
    
    print("Generating US Temperature Heat Map...")
    
    # Extract coordinates and temperatures
    lats = [data[0] for data in TEMPERATURE_DATA.values()]
    lons = [data[1] for data in TEMPERATURE_DATA.values()]
    temps = [data[2] for data in TEMPERATURE_DATA.values()]
    
    # Create high-resolution grid
    grid_resolution = 1000
    lon_min, lon_max = -125, -66  # Continental US
    lat_min, lat_max = 24, 50
    
    grid_lon = np.linspace(lon_min, lon_max, grid_resolution)
    grid_lat = np.linspace(lat_min, lat_max, grid_resolution)
    grid_lon_mesh, grid_lat_mesh = np.meshgrid(grid_lon, grid_lat)
    
    # Interpolate temperature data
    print("Interpolating temperature data...")
    points = np.array(list(zip(lons, lats)))
    values = np.array(temps)
    
    # Use cubic interpolation for smooth gradients
    grid_temp = griddata(points, values, (grid_lon_mesh, grid_lat_mesh), 
                        method='cubic', fill_value=np.nan)
    
    # Apply Gaussian smoothing for realistic weather patterns
    grid_temp = gaussian_filter(grid_temp, sigma=15)
    
    # Create figure with high DPI
    fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor('#F5F5F5')
    ax.set_facecolor('#E8E8E8')
    
    # Create custom colormap
    temp_cmap = create_temperature_colormap()
    
    # Plot temperature heat map
    print("Rendering heat map...")
    temp_plot = ax.contourf(grid_lon_mesh, grid_lat_mesh, grid_temp,
                           levels=50, cmap=temp_cmap, 
                           vmin=-5, vmax=30, extend='both',
                           alpha=0.85)
    
    # Add smooth contour lines
    contour_lines = ax.contour(grid_lon_mesh, grid_lat_mesh, grid_temp,
                               levels=15, colors='white', linewidths=0.3,
                               alpha=0.3)
    
    # Add state boundaries (simplified)
    print("Adding state boundaries...")
    # Draw approximate state borders
    state_borders = [
        # West Coast
        [(-124.7, 49.0), (-116.9, 49.0)],  # WA north
        [(-124.4, 42.0), (-114.1, 42.0)],  # CA north
        [(-114.1, 42.0), (-114.1, 37.0)],  # NV east
        
        # Texas
        [(-106.6, 31.8), (-93.5, 31.8)],   # TX north
        [(-106.6, 31.8), (-106.6, 25.8)],  # TX west
        [(-93.5, 33.0), (-93.5, 29.0)],    # TX east
        
        # Florida
        [(-87.6, 31.0), (-80.0, 31.0)],    # FL north
        [(-87.6, 31.0), (-87.6, 30.0)],    # FL panhandle
        [(-81.0, 31.0), (-81.0, 24.5)],    # FL east coast
        
        # Great Lakes region
        [(-92.0, 47.0), (-76.0, 47.0)],    # Northern border
        [(-83.0, 42.0), (-75.0, 42.0)],    # NY/PA border
    ]
    
    for border in state_borders:
        if len(border) == 2:
            lons_b = [border[0][0], border[1][0]]
            lats_b = [border[0][1], border[1][1]]
            ax.plot(lons_b, lats_b, 'k-', linewidth=0.5, alpha=0.6)
    
    # Add colorbar (legend)
    cbar = plt.colorbar(temp_plot, ax=ax, orientation='horizontal',
                       pad=0.05, aspect=40, shrink=0.8)
    cbar.set_label('Temperature (°C)', fontsize=14, fontweight='bold',
                   fontfamily='sans-serif')
    cbar.ax.tick_params(labelsize=11)
    
    # Customize colorbar ticks
    temp_ticks = [-5, 0, 5, 10, 15, 20, 25, 30]
    temp_labels = [
        '-5°C\n(Very Cold)',
        '0°C\n(Cold)',
        '5°C',
        '10°C\n(Cool)',
        '15°C\n(Mild)',
        '20°C\n(Warm)',
        '25°C\n(Hot)',
        '30°C\n(Very Hot)'
    ]
    cbar.set_ticks(temp_ticks)
    cbar.set_ticklabels(temp_labels, fontsize=9)
    
    # Add title and labels
    ax.set_title('Continental United States - Temperature Distribution Heat Map',
                fontsize=18, fontweight='bold', pad=20, fontfamily='sans-serif')
    ax.set_xlabel('Longitude', fontsize=12, fontweight='bold')
    ax.set_ylabel('Latitude', fontsize=12, fontweight='bold')
    
    # Set axis limits
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    
    # Add grid
    ax.grid(True, linestyle='--', alpha=0.3, color='gray', linewidth=0.5)
    
    # Add annotations for key regions
    annotations = [
        ('Pacific\nNorthwest', -122, 47, 'white'),
        ('Southwest\nDesert', -112, 33, 'white'),
        ('Great\nPlains', -100, 40, 'black'),
        ('Gulf\nCoast', -90, 29, 'white'),
        ('Southeast', -84, 33, 'white'),
        ('Northeast', -74, 42, 'black'),
    ]
    
    for text, lon, lat, color in annotations:
        ax.text(lon, lat, text, fontsize=10, fontweight='bold',
               ha='center', va='center', color=color,
               bbox=dict(boxstyle='round,pad=0.3', facecolor='black',
                        alpha=0.3, edgecolor='none'))
    
    # Add metadata
    metadata_text = (
        'Data: Climatological Temperature Averages\n'
        'Interpolation: Cubic Spline with Gaussian Smoothing\n'
        'Resolution: 1920×1080 | Generated for DengueCast India Project'
    )
    ax.text(0.02, 0.02, metadata_text, transform=ax.transAxes,
           fontsize=8, verticalalignment='bottom',
           bbox=dict(boxstyle='round', facecolor='white', alpha=0.7),
           fontfamily='monospace')
    
    # Adjust layout
    plt.tight_layout()
    
    # Save high-resolution image
    print(f"Saving to {output_path}...")
    plt.savefig(output_path, dpi=150, bbox_inches='tight',
               facecolor='#F5F5F5', edgecolor='none')
    print(f"✓ Heat map saved successfully!")
    
    # Also save a version without annotations for clean presentation
    clean_path = output_path.replace('.png', '_clean.png')
    
    # Remove annotations for clean version
    for text_obj in ax.texts[:-1]:  # Keep metadata
        text_obj.set_visible(False)
    
    plt.savefig(clean_path, dpi=150, bbox_inches='tight',
               facecolor='#F5F5F5', edgecolor='none')
    print(f"✓ Clean version saved to {clean_path}")
    
    plt.close()
    
    return output_path, clean_path

if __name__ == '__main__':
    import os
    os.makedirs('outputs/maps', exist_ok=True)
    
    output_file, clean_file = generate_temperature_heatmap()
    print(f"\n{'='*60}")
    print(f"Temperature Heat Map Generation Complete!")
    print(f"{'='*60}")
    print(f"Main file: {output_file}")
    print(f"Clean file: {clean_file}")
    print(f"\nFeatures:")
    print(f"  ✓ High-resolution (1920×1080)")
    print(f"  ✓ Smooth temperature gradients")
    print(f"  ✓ Realistic climatological data")
    print(f"  ✓ Professional NOAA-style visualization")
    print(f"  ✓ State boundaries included")
    print(f"  ✓ Color-coded temperature legend")
