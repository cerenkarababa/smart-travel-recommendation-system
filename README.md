# Smart Travel Recommendation System

A Flask + PostgreSQL + Machine Learning academic project.

## Planned architecture
Browser (HTML/CSS/JS) -> Flask REST routes -> PostgreSQL
                                      -> pandas / scikit-learn model
Model predictions -> PostgreSQL -> Browser

## Initial setup
1. Install Python 3.11+ and Docker Desktop.
2. Create a virtual environment:
   - macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and update credentials if needed.
5. Start PostgreSQL: `docker compose up -d`
6. Download the Stravl CSV and `destination_ids.txt` from:
   https://github.com/Stravl/Stravl-Data
   Put both files in `data/raw/`.
7. Inspect the real CSV structure:
   `python scripts/inspect_dataset.py data/raw/Stravl_Travel_Preference_Data.csv`

Do not load the source CSV into PostgreSQL or train a model until the inspection
script has confirmed its actual columns, null values, row count and data types.
The final schema and preprocessing pipeline will be based on that inspection.

## Project status
- [ ] Dataset downloaded and profiled
- [ ] Data dictionary confirmed
- [ ] PostgreSQL schema finalized
- [ ] Source data imported
- [ ] Recommendation model trained and evaluated
- [ ] Predictions persisted to PostgreSQL
- [ ] Flask API and frontend completed
- [ ] Demo, report, architecture diagram and Medium article completed
