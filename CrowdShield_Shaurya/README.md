# CrowdShield — Clean Team Package

This package is the clean backend package for the CrowdShield project. It is intended to be shared with the frontend teammate (Shaurya) and to let another teammate reproduce the current backend run without copying the original virtual environment.

## Project flow

`Video → YOLO11 Detection/Tracking → Zone Density → Trend Analysis → Risk Engine → Prevention Engine → live_prevention.json → Frontend`

## Included

- `src/detection/detect.py` — current detection + tracking + risk/prevention pipeline
- `models/yolo11n.pt` — YOLO11n weights currently used by the code
- `data/videos/crowd_test.mp4` — sample/test video
- `data/logs/live_prevention.json` — live frontend-facing output
- `data/logs/*.csv` — historical density/trend/risk logs
- `requirements.txt` — Python dependencies

## 1. Python setup (Windows)

Open PowerShell in the project root.

```powershell python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell does not allow activation, use the environment directly:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 2. Model setup

### Easiest option

The required model is **already included** in this package:

```text
models/yolo11n.pt
```

The current detection script loads exactly:

```python
model = YOLO("models/yolo11n.pt")
```

So no model download is needed when this file is present.

### If the model is missing

The project uses **Ultralytics YOLO11n**. The official Ultralytics documentation lists `yolo11n.pt` as the pretrained YOLO11 detection model and shows it being loaded with `YOLO("yolo11n.pt")`.

Official model documentation:
https://docs.ultralytics.com/models/yolo11

You can also let the installed Ultralytics package obtain the pretrained model by running this from the project root:

```powershell
python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"
```

Then place/copy the resulting `yolo11n.pt` into:

```text
models/yolo11n.pt
```

Do not replace it with a different YOLO variant unless the detection code is also intentionally changed.

## 3. Run the backend

From the project root:

```powershell
.\venv\Scripts\python.exe src\detection\detect.py
```

The current script uses:

```text
data/videos/crowd_test.mp4
```

as its test video source.

## 4. Frontend integration

Shaurya should primarily consume:

```text
data/logs/live_prevention.json
```

The detection script also starts a small local HTTP endpoint:

```text
http://127.0.0.1:8765/live_prevention.json
```

The frontend can poll this endpoint while the backend is running instead of directly reading the CSV files.

### JSON fields

The live JSON contains the current state, including:

- `status`
- `timestamp`
- `threat_detected`
- `highest_risk_zone`
- `highest_risk_level`
- `total_people`
- `threat_count`
- `threats[]`

Each threat can contain:

- `zone`
- `density`
- `risk_score`
- `risk_level`
- `risk_cause`
- `possible_origin`
- `safe_alternative`
- `recommended_action`

These are the fields to use for the prevention/action screen.

## 5. Historical data

For charts/analytics, the backend writes:

```text
data/logs/density_history.csv
data/logs/density_trend_history.csv
data/logs/risk_history.csv
```

The frontend does **not** need these files for the live threat/prevention panel.

## 6. Suggested frontend screens

1. **Live Dashboard** — total people, overall/highest risk, threat status.
2. **3×3 Zone Map (Z1–Z9)** — highlight HIGH/CRITICAL zones.
3. **Prevention Panel** — threat zone, density, risk, possible origin, cause, safe alternative and recommended action.
4. **Analytics** (optional) — historical density/risk graphs from the CSVs.

## 7. Important behaviour

If the JSON says:

```json
"threat_detected": false
```

that can simply mean the current video window has no active threat. It is not automatically an error.

If `threats` is empty, the frontend should show a safe/normal state rather than treating it as a crash.

## 8. Troubleshooting

### `ModuleNotFoundError`

Make sure the virtual environment is active and run:

```powershell
pip install -r requirements.txt
```

### `Model ... not found`

Check that this exact file exists:

```text
models/yolo11n.pt
```

### `ERROR: Could not open video`

Check that this file exists:

```text
data/videos/crowd_test.mp4
```

and run the command from the project root.

### Frontend cannot read the JSON

Start the backend first, then open:

```text
http://127.0.0.1:8765/live_prevention.json
```

The backend already sends `Access-Control-Allow-Origin: *` for the live endpoint.

## 9. Team note

Do not copy the original `venv/` folder between machines. Create a fresh virtual environment and install `requirements.txt` instead.

The model file is intentionally included here so the current tested setup can be reproduced immediately.
