# 🚀 Quick Start Guide - DengueCast India Enhanced

## Prerequisites

- Python 3.8+ installed
- Node.js 16+ installed
- npm or yarn package manager

## Installation & Setup

### 1. Install Backend Dependencies

```bash
# Install Python packages
pip install fastapi uvicorn torch xgboost scikit-learn pandas numpy joblib
```

### 2. Install Frontend Dependencies

```bash
cd web
npm install
```

## Running the Application

### Option 1: Two Terminal Windows

**Terminal 1 - Backend:**

```bash
# From project root
cd api
python -m uvicorn main:app --reload --port 8001
```

**Terminal 2 - Frontend:**

```bash
# From project root
cd web
npm run dev
```

### Option 2: Background Processes (Windows)

**Start Backend:**

```powershell
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd api; python -m uvicorn main:app --reload --port 8001"
```

**Start Frontend:**

```powershell
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd web; npm run dev"
```

## Access the Application

- **Frontend:** http://localhost:5174
- **Backend API:** http://localhost:8001
- **API Documentation:** http://localhost:8001/docs

## Using the Enhanced Features

### 1. Select a District

- Use the dropdown in the left sidebar
- The map will automatically fly to the district location

### 2. Switch Map Layers

Click any of the layer buttons:

- 🛰️ **Satellite** - High-resolution imagery
- 🗺️ **Hybrid** - Satellite with labels
- ⛰️ **Terrain** - Topographic view
- 🌙 **Dark** - Operational dark mode

### 3. Toggle Overlays

- ☑️ **🔥 Heatmap** - Show intensity heatmap
- ☑️ **📊 3D Markers** - Enable 3D effects

### 4. Interact with Map

- **Click markers** - View detailed information
- **Scroll wheel** - Zoom in/out
- **Drag** - Pan around the map
- **Watch animations** - Pulsing risk markers

## Features Overview

### Map Layers

| Layer     | Description        | Best For           |
| --------- | ------------------ | ------------------ |
| Satellite | High-res imagery   | Detailed analysis  |
| Hybrid    | Satellite + labels | Navigation         |
| Terrain   | Elevation data     | Geographic context |
| Dark      | Low-light theme    | Night operations   |

### Marker Types

| Color    | Risk Level    | Cases |
| -------- | ------------- | ----- |
| 🟢 Green | Low           | < 10  |
| 🟡 Amber | Medium        | 10-50 |
| 🔴 Red   | High          | > 50  |
| 🔵 Blue  | Breeding Site | N/A   |

### Animations

- **Pulse Effect** - Central district marker (2s cycle)
- **Breathing** - Hotspot markers (3s cycle)
- **Fly-to** - Smooth transitions (2.2s duration)

## Troubleshooting

### Backend Issues

**Problem:** `ModuleNotFoundError`

```bash
# Solution: Install missing packages
pip install <package-name>
```

**Problem:** Port 8001 already in use

```bash
# Solution: Use different port
python -m uvicorn main:app --reload --port 8002
# Update vite.config.js proxy target
```

### Frontend Issues

**Problem:** `npm install` fails

```bash
# Solution: Clear cache and reinstall
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

**Problem:** Map not loading

```bash
# Solution: Check console for errors
# Ensure backend is running
# Check network tab for API calls
```

**Problem:** Heatmap not showing

```bash
# Solution: Toggle checkbox multiple times
# Check browser console for import errors
# Ensure leaflet.heat is installed
```

## Development Tips

### Hot Reload

- Backend: Auto-reloads on file changes (uvicorn --reload)
- Frontend: Auto-reloads on file changes (Vite HMR)

### Debugging

- Backend: Check terminal for Python errors
- Frontend: Open browser DevTools (F12)
- API: Visit http://localhost:8001/docs for interactive testing

### Making Changes

**To modify map behavior:**

```javascript
// Edit: web/src/components/EnhancedMap.jsx
```

**To change styling:**

```css
/* Edit: web/src/index.css */
```

**To update API:**

```python
# Edit: api/main.py
```

## Performance Tips

1. **Reduce Animation Load:**
   - Disable 3D mode on slower devices
   - Use Dark mode instead of Satellite for faster loading

2. **Optimize Heatmap:**
   - Toggle off when not needed
   - Reduces rendering overhead

3. **Limit Zoom:**
   - Very high zoom levels load more tiles
   - Stay at zoom 10-14 for best performance

## Next Steps

1. ✅ Explore all map layers
2. ✅ Test different districts
3. ✅ Try heatmap visualization
4. ✅ Enable 3D marker mode
5. ✅ Check prediction accuracy
6. ✅ Review climate metrics
7. ✅ Test on mobile device

## Support

### Documentation

- `ENHANCEMENTS.md` - Detailed feature documentation
- `IMPLEMENTATION_SUMMARY.md` - Technical overview
- `README.md` - Project information

### Common Commands

```bash
# Install dependencies
npm install                    # Frontend
pip install -r requirements.txt  # Backend (if exists)

# Run development
npm run dev                    # Frontend
python -m uvicorn main:app --reload  # Backend

# Build for production
npm run build                  # Frontend
# Creates: web/dist/

# Preview production build
npm run preview                # Frontend
```

## Quick Reference

### Keyboard Shortcuts

- `+` / `-` - Zoom in/out
- `Arrow keys` - Pan map
- `Esc` - Close popup
- `F12` - Open DevTools

### API Endpoints

- `GET /districts` - List all districts
- `GET /predict_latest?district=<name>` - Get prediction
- `GET /model_accuracy?district=<name>` - Get metrics
- `POST /predict` - Manual prediction

### File Structure

```
DengueCastIndia/
├── api/                    # Backend
│   └── main.py            # FastAPI app
├── web/                    # Frontend
│   ├── src/
│   │   ├── components/
│   │   │   └── EnhancedMap.jsx
│   │   ├── App.jsx
│   │   └── index.css
│   └── package.json
├── models/                 # Trained models
├── data/                   # Datasets
└── src/                    # Training scripts
```

---

**Happy Mapping! 🗺️✨**

For questions or issues, check the documentation files or open an issue in the repository.
