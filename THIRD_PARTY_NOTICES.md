# Third-party notices

## Cardia

- Repository: https://github.com/nisamaasoglu/Cardia
- Imported upstream branch: `main`
- Imported upstream commit: `3f8b655f3a92de3579836d19c95a2e33c8e6f7f2`
- License: MIT; the upstream `LICENSE` file is retained verbatim.
- Author attribution: Nisa Maaşoğlu, as identified in the upstream README and source files.
- Imported paths: `web/`, `firmware/cardia_ecg/`, `docs/`, `README.md`, and `LICENSE` (along with the upstream `.gitignore`).
- Project modifications to `web/`: `index.html` now names the PhysioNet/Python replay source and removes the Arduino address, demo, and unrelated simulated metrics; `app.js` now polls the local Flask `/api/ecg` snapshot and renders physical ECG units; `style.css` retains Cardia's instrument-panel design with small changes for the new controls and alert visibility. `web/assets/` remains upstream material.
- The Python virtual device and Flask integration are project additions, not work by the Cardia original author.
