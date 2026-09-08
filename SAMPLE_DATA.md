# CRFOS RSET-Modeled Sample Data

This dataset is synthetic demonstration data for the CRFOS project.

Department and facility names are modeled after publicly available information about Rajagiri School of Engineering & Technology (RSET). The seed data does not represent official RSET inventory or institutional records.

**Operational bookings, usage, procurement, sharing, maintenance, sensor, and prediction records are synthetic demonstration data and are not represented as official RSET institutional records.**

## Seed Command

From the project directory:

```powershell
python seed_data.py
```

The script connects to the configured `crfos` database, uses parameterized SQL, runs in a transaction, and prints the resulting demo-record summary.

## Repeat and Reset Behavior

The script is safe to run repeatedly. Before reseeding, it removes only records carrying the CRFOS RSET demo markers:

- department codes beginning with `RSET_`
- demo users using hidden `rset.demo.*@example.invalid` identifiers
- resource descriptions beginning with the hidden `[CRFOS DEMO RSET]` seed marker
- demo booking purposes, usage sources, procurement notes, sharing reasons, maintenance notes, and related foreign-key records
- demo suppliers using hidden `demo-*@example.invalid` identifiers

Legitimate non-demo records are not targeted.

## Current Seed Size

The current dataset creates approximately:

- 10 departments
- 20 demo users
- 36 resources
- 220 bookings
- 196 actual usage records
- 6 suppliers
- 25 purchases
- 20 sharing requests
- 34 stored predictions
- 25 maintenance records
- 108 sensor readings

## Deliberate Demonstration Scenarios

The dataset intentionally includes:

- high-use computing resources and AI/data-science resources
- underutilized laboratories and project/workshop resources
- compatible computer-lab resources across departments for sharing review
- pending, approved, rejected, cancelled, and completed sharing requests
- phantom/no-show-style bookings without actual usage records
- partial and full actual usage for Black Box comparisons
- synthetic procurement expenditure across several departments and categories
- high-demand prediction history
- active, completed, and repeated maintenance records
- normal, attention, and high sensor readings
- a high-demand resource with maintenance attention

All records are intended for screenshots, demonstrations, analytics testing, and project presentation only.

## Notes

No schema changes are made by `seed_data.py`. It uses the existing CRFOS tables and status conventions. The seed does not create authentication accounts or claim that the fictional demo users are real institutional users.
