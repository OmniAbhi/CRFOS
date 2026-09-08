# CRFOS

CRFOS (Campus Resource Forensics & Optimization System) is a Flask and MySQL college-project prototype for campus resource registry, booking, forensic utilization analysis, procurement visibility, sharing, demand prediction, predictive maintenance, unified analytics, deterministic recommendations, and optional AI explanations.

## Important Data Notice

The included RSET-modeled dataset is synthetic demonstration data. Department and facility names are modeled after publicly available RSET information, but operational bookings, usage, procurement, sharing, maintenance, sensor, and prediction records are fictional and are not official RSET institutional records.

## Requirements

- Python 3.11+ recommended
- MySQL Server 8.0+
- Windows PowerShell or an equivalent shell

Install Python dependencies:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## MySQL Setup

1. Start the MySQL server.
2. Create the `crfos` database and apply the existing schema:

```powershell
mysql -u root -p < schema.sql
```

3. Copy `.env.example` to `.env` and set the local MySQL password. Do not commit `.env`.

Required database settings:

```text
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-local-password
DB_NAME=crfos
```

The optional AI settings are disabled unless configured:

```text
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

The AI explanation feature only explains existing deterministic recommendations and is not required for the application to run.

## Seed Demonstration Data

Run the repeatable RSET-modeled synthetic dataset seed:

```powershell
python seed_data.py
```

The seed uses the existing schema, foreign keys, and status values. It removes only its own marked demo records before reseeding. It does not delete legitimate non-demo records.

## Run Flask

```powershell
python app.py
```

Open `http://127.0.0.1:5000/`.

## Main Routes

- `/` unified CRFOS dashboard
- `/resources` Resource Registry
- `/bookings` Smart Booking
- `/blackbox` Resource Black Box
- `/cost` Cost Optimization / RCOS
- `/sharing` Resource Sharing
- `/prediction` Demand Prediction
- `/maintenance` Predictive Maintenance
- `/recommendations` deterministic recommendations with optional AI explanations

## Project Structure

- `app.py` Flask application factory and home dashboard route
- `routes.py` module routes
- `analytics.py` read-only unified analytics layer
- `recommendations.py` deterministic recommendation engine
- `services/` MySQL-backed module services
- `templates/` Jinja views
- `static/` CSS and JavaScript
- `schema.sql` existing MySQL schema
- `seed_data.py` repeatable synthetic demonstration data

## Limitations

Authentication, role-based authorization, notifications, physical IoT connectivity, autonomous decisions, and advanced machine-learning models are not implemented. Administrators remain responsible for reviewing bookings, maintenance, sharing, procurement, and recommendation evidence.
