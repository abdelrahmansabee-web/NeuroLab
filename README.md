# KinematicsAI Lab v7.0
## Stroke Rehabilitation Kinematic Analysis System

A complete web application for video-based kinematic analysis of upper limb function in stroke rehabilitation. Uses MediaPipe Pose for markerless motion capture and computes 14 biomechanical variables.

---

## Architecture

```
kinematics-lab/
├── backend/                    # Python FastAPI backend
│   ├── main.py                # Main API server
│   ├── requirements.txt       # Python dependencies
│   └── static_outputs/        # Generated files (CSV, TRC, videos)
│
├── frontend/                   # React + TypeScript frontend
│   ├── src/
│   │   ├── App.tsx            # Main app component
│   │   ├── types.ts           # TypeScript type definitions
│   │   ├── components/        # UI components
│   │   │   ├── Header.tsx
│   │   │   ├── VideoUploader.tsx
│   │   │   ├── SideSelector.tsx
│   │   │   ├── ResultsTable.tsx     # ⭐ Clinically-correct Δ change
│   │   │   ├── KinematicsChart.tsx
│   │   │   ├── DownloadPanel.tsx
│   │   │   ├── ProcessingStatus.tsx
│   │   │   ├── MetricCard.tsx
│   │   │   ├── SettingsModal.tsx
│   │   │   ├── HelpModal.tsx
│   │   │   └── DemoModeIndicator.tsx
│   │   └── services/
│   │       └── api.ts         # Backend communication + mock data
│   └── ...config files
│
└── README.md
```

---

## Key Fix: Clinically-Correct Δ Change Interpretation

The previous version had a critical bug where all delta changes were shown as positive "improvements" regardless of clinical direction. **This version fixes that:**

| Variable | Improvement Direction | Explanation |
|---|---|---|
| Onset Time, Durations | `lower` ↓ | Faster = better |
| Path Lengths | `lower` ↓ | More direct path = better |
| Trunk Displacement/Rotation | `lower` ↓ | Less compensation = better |
| Shoulder Compensation | `lower` ↓ | Less hiking = better |
| **Elbow Extension Range** | **`higher` ↑** | **More range = better** |
| **SPARC** | **`closer_to_zero`** | **Less negative = smoother** |
| NVP | `lower_count` ↓ | Fewer peaks = smoother |

**Color coding in results table:**
- 🟢 Green = Clinical Improvement
- 🔴 Red = Clinical Deterioration

---

## Quick Start

### 1. Backend (Python)

```bash
cd backend
pip install -r requirements.txt
python main.py
```

The API will start at `http://localhost:8000`. Check docs at `http://localhost:8000/docs`.

### 2. Frontend (React)

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173`.

### 3. Demo Mode

If the backend is not running, the frontend automatically switches to **Demo Mode** with clinically-realistic mock data, so you can preview the UI.

---

## API Endpoint

### `POST /process-kinematics`

| Parameter | Type | Description |
|---|---|---|
| `file` | UploadFile | Video file (.mp4, .mov, .avi) |
| `side` | Query string | Affected side: `R` or `L` |
| `phase` | Query string | Treatment phase: `pre`, `during`, `post` |

**Response:**
```json
{
  "success": true,
  "phase": "pre",
  "side": "R",
  "metrics": {
    "onset_time": "0.450",
    "reaching_duration": "1.250",
    "wiping_duration": "2.150",
    "total_duration": "4.850",
    "reaching_path_length": "0.420",
    "wiping_path_length": "0.680",
    "trunk_displacement": "0.250",
    "trunk_rotation": "15.20",
    "elbow_extension_range": "45.3",
    "shoulder_compensation": "1.850",
    "sparc_reaching": "-2.85",
    "sparc_full": "-3.25",
    "nvp_reaching": "5",
    "nvp_wiping": "8"
  },
  "links": {
    "csv": "http://localhost:8000/static/motion_pre.csv",
    "trc": "http://localhost:8000/static/motion_pre.trc",
    "video": "http://localhost:8000/static/validation_pre_1234.mp4"
  }
}
```

---

## Biomechanical Variables (14)

### Temporal (4)
1. **Onset Time** — Time to movement initiation (sec)
2. **Reaching Duration** — Duration of reaching phase (sec)
3. **Wiping Duration** — Duration of wiping phase (sec)
4. **Total Task Duration** — Total movement time (sec)

### Spatial (2)
5. **Reaching Path Length** — 3D path during reaching (m)
6. **Wiping Path Length** — 3D path during wiping (m)

### Pathological Compensation (3)
7. **Trunk Displacement** — Normalized to shoulder width (SW)
8. **Trunk Rotation** — Range of axial rotation (deg)
9. **Shoulder Compensation** — Duration of hiking (sec)

### Joint Kinematics (1)
10. **Elbow Extension Range** — Range during reaching (deg)

### Smoothness (4)
11. **SPARC (Reaching)** — Spectral arc length (unitless, negative)
12. **SPARC (Full)** — Full movement SPARC
13. **NVP Reaching** — Number of velocity peaks
14. **NVP Wiping** — Number of velocity peaks

---

## Tech Stack

- **Backend:** Python 3.10+, FastAPI, MediaPipe, OpenCV, SciPy, NumPy, Pandas
- **Frontend:** React 18, TypeScript, Tailwind CSS, Framer Motion, Lucide Icons
- **Build:** Vite 5
