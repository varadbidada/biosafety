import pandas as pd
import folium
import numpy as np
import os

os.makedirs("outputs/maps", exist_ok=True)

# Load ensemble results
df = pd.read_csv("data/processed/ensemble_results.csv")
df = df.dropna(subset=["ensemble_pred"])

# Synthetic district coordinates (grid layout)
districts = df["district"].unique()
n = len(districts)

# Arrange districts in a simple grid pattern
grid_size = int(np.ceil(np.sqrt(n)))

coords = {}
lat_base = 20.0  # reference latitude
lon_base = 78.0  # reference longitude

for i, district in enumerate(districts):
    row = i // grid_size
    col = i % grid_size
    coords[district] = (
        lat_base + row * 0.4,   # spacing vertically
        lon_base + col * 0.4    # spacing horizontally
    )

# Compute average predicted risk for each district
avg_risk = df.groupby("district")["ensemble_pred"].mean()

# Create map
m = folium.Map(location=[20.0, 78.0], zoom_start=5)

# Color function
def risk_color(value):
    if value < 5:
        return "green"
    elif value < 10:
        return "orange"
    else:
        return "red"

# Add markers
for district in districts:
    lat, lon = coords[district]
    risk = avg_risk[district]
    color = risk_color(risk)

    folium.CircleMarker(
        location=[lat, lon],
        radius=12,
        popup=f"{district}<br>Avg Predicted Cases: {risk:.2f}",
        color=color,
        fill=True,
        fill_opacity=0.8,
    ).add_to(m)

# Save map
m.save("outputs/maps/dengue_risk_map.html")
print("Map saved to outputs/maps/dengue_risk_map.html")