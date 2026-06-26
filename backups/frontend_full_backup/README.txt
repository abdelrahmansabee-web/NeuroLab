============================================================
NeuroLab Frontend — Full Backup
============================================================

Created: June 20, 2026
Source: D:\Thesis app\NeuroLab\frontend\
Version: 7.1.0-sparc-pwa

Backup Structure:
==================
frontend_full_backup/
├── README.txt              ← This file
├── start_frontend.bat      ← Script to serve build on port 3000
├── .gitignore              ← Git ignore rules
├── README.md               ← Create React App default README
│
├── src/                    ← React source code
│   ├── App.js              ← MAIN: 5688 lines - All sections + UI
│   ├── analysisPlan.js     ← 661 lines - Study design, stats, SPSS
│   ├── thesisDocs.js       ← 208 lines - Literature review, CONSORT
│   ├── patientImport.js    ← 281 lines - JSON/PDF import logic
│   ├── index.js            ← React entry point
│   ├── index.css           ← Tailwind + custom glass styles
│   ├── App.css             ← Default CRA styles
│   ├── App.test.js         ← Test file
│   ├── setupTests.js       ← Test setup
│   ├── reportWebVitals.js  ← Web vitals
│   └── logo.svg            ← React logo
│
├── public/                 ← Static assets
│   ├── index.html          ← HTML shell (Tailwind CDN, PWA meta)
│   ├── manifest.json       ← PWA manifest
│   ├── serve.json          ← serve config for Cache-Control
│   ├── bg.b64.txt          ← Background image (base64)
│   ├── bg.jpg              ← Background image (original)
│   ├── pdf.worker.min.js   ← PDF.js worker
│   ├── favicon.ico
│   ├── logo192.png
│   ├── logo512.png
│   └── robots.txt
│
├── config/                 ← Build configuration
│   ├── package.json        ← Dependencies & scripts
│   ├── package-lock.json   ← Lock file
│   ├── tailwind.config.js  ← Tailwind content paths
│   └── postcss.config.js   ← PostCSS plugins
│
└── build/                  ← Production build (deploy-ready)

Key Features in App.js (5688 lines):
=====================================
1. Demographics (participant info, clinical, comorbidities)
2. IPAQ (Physical Activity Questionnaire with MET calculation)
3. VAS (Pain Scale with emoji faces)
4. VAMS-4 (Mood Scale)
5. Motor Change (Muscle Control Scale)
6. KVIQ-10 (Motor Imagery Questionnaire)
7. WMFT-4 (Wolf Motor Function Test with stopwatch)
8. Kinematics AI Lab (video upload, analysis, velocity charts)
9. Patient Database (search, load, delete, sync)
10. Report Export (Glassmorphism HTML, PDF, Excel, SPSS syntax)
11. Analysis Dashboard (preliminary stats, CONSORT flow, thesis docs)

Unique Features:
- Pull-to-refresh on iOS/PWA
- Cross-device patient sync via REST API
- Side-view animated skeleton figures
- Custom thick sliders with drag support
- Glassmorphism design with backdrop-blur
- Dark theme with bg.jpg background
- Bilingual (EN/TR) interface
- SPSS syntax generator
- LOCF imputation for ITT analysis

Dependencies (see config/package.json):
- React 19, Framer Motion 12, Lucide React
- jsPDF + autoTable, xlsx
- pdfjs-dist (PDF import)
- Tailwind CSS 3 (via CDN in index.html)
- React Scripts 5

To Run Locally:
===============
Option A: Production build
  cd frontend_full_backup
  npx serve -s build -l 3000

Option B: Development
  cd frontend_full_backup
  npm install
  npm start
============================================================
