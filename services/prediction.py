"""Demand prediction service placeholder for later AI/ML work."""
"""Simple, explainable demand forecasting from historical booking-hours."""

from datetime import date, datetime, timedelta
from decimal import Decimal

from services.booking import ValidationError


FORECAST_WEEKS = 4
MINIMUM_HISTORICAL_WEEKS = 4
MODEL_VERSION = "4-week moving average"
TREND_TOLERANCE = 0.05
HIGH_DEMAND_RATIO = 1.20
LOW_DEMAND_RATIO = 0.80


def _week_start(value):
	current = value.date() if isinstance(value, datetime) else value
	return current - timedelta(days=current.weekday())


def _hours(start_time, end_time):
	if not start_time or not end_time or end_time <= start_time:
		return 0.0
	return (end_time - start_time).total_seconds() / 3600


def _aggregate(rows, key_name):
	buckets = {}
	for row in rows:
		key = row[key_name]
		week = _week_start(row["start_time"])
		buckets.setdefault(key, {})
		buckets[key][week] = buckets[key].get(week, 0.0) + _hours(row["start_time"], row["end_time"])
	return buckets


def _trend(values):
	if len(values) < MINIMUM_HISTORICAL_WEEKS:
		return "INSUFFICIENT DATA"
	midpoint = len(values) // 2
	previous = sum(values[:midpoint]) / midpoint
	recent = sum(values[midpoint:]) / (len(values) - midpoint)
	if previous == 0:
		return "Increasing" if recent > 0 else "Stable"
	change = (recent - previous) / previous
	if change > TREND_TOLERANCE:
		return "Increasing"
	if change < -TREND_TOLERANCE:
		return "Decreasing"
	return "Stable"


def _classification(predicted, historical_average, sufficient):
	if not sufficient:
		return "INSUFFICIENT DATA"
	if historical_average and predicted >= historical_average * HIGH_DEMAND_RATIO:
		return "HIGH DEMAND"
	if historical_average and predicted <= historical_average * LOW_DEMAND_RATIO:
		return "LOW DEMAND"
	return "MODERATE DEMAND"


def _build_forecast(label, identifier, rows, key_name):
	periods = _aggregate(rows, key_name).get(identifier, {})
	history = sorted(periods.items())
	values = [value for _, value in history]
	sufficient = len(values) >= MINIMUM_HISTORICAL_WEEKS
	recent_values = values[-FORECAST_WEEKS:]
	historical_average = sum(recent_values) / len(recent_values) if recent_values else None
	baseline_average = sum(values) / len(values) if values else None
	predicted = historical_average if sufficient else None
	last_week = history[-1][0] if history else None
	target_start = last_week + timedelta(days=7) if last_week else None
	target_end = target_start + timedelta(days=6) if target_start else None
	return {
		"label": label,
		"identifier": identifier,
		"history": [{"week_start": week, "hours": hours} for week, hours in history[-FORECAST_WEEKS:]],
		"historical_average": historical_average,
		"predicted_demand": predicted,
		"target_start": target_start,
		"target_end": target_end,
		"historical_week_count": len(history),
		"trend": _trend(values),
		"classification": _classification(predicted, baseline_average, sufficient),
		"baseline_average": baseline_average,
		"sufficient": sufficient,
		"method": MODEL_VERSION,
		"metric": "planned booking-hours per week",
	}


def get_booking_rows(connection):
	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		"""SELECT b.resource_id, r.resource_type, r.name AS resource_name,
				  b.start_time, b.end_time
		   FROM bookings b JOIN resources r ON r.id = b.resource_id
		   WHERE b.status <> 'CANCELLED' AND r.status <> 'RETIRED'
		   ORDER BY b.start_time"""
	)
	return cursor.fetchall()


def get_resource_options(connection):
	cursor = connection.cursor(dictionary=True)
	cursor.execute("SELECT id, name, resource_type, location, status FROM resources WHERE status <> 'RETIRED' ORDER BY name")
	return cursor.fetchall()


def get_prediction_data(connection):
	rows = get_booking_rows(connection)
	resources = get_resource_options(connection)
	resource_forecasts = []
	for resource in resources:
		forecast = _build_forecast(resource["name"], resource["id"], rows, "resource_id")
		forecast["resource"] = resource
		resource_forecasts.append(forecast)
	type_rows = {}
	for row in rows:
		type_rows.setdefault(row["resource_type"], []).append(row)
	type_forecasts = [
		_build_forecast(resource_type, resource_type, type_rows[resource_type], "resource_type")
		for resource_type in sorted(type_rows)
	]
	sufficient = [forecast for forecast in resource_forecasts if forecast["sufficient"]]
	return {
		"resources": resource_forecasts,
		"types": type_forecasts,
		"summary": {
			"resources_analyzed": len(resource_forecasts),
			"sufficient_resources": len(sufficient),
			"high_demand": sum(forecast["classification"] == "HIGH DEMAND" for forecast in sufficient),
			"attention": sum(forecast["classification"] == "LOW DEMAND" for forecast in sufficient),
		},
	}


def get_resource_forecast(connection, resource_id):
	data = get_prediction_data(connection)
	return next((forecast for forecast in data["resources"] if forecast["identifier"] == resource_id), None)


def get_type_forecast(connection, resource_type):
	data = get_prediction_data(connection)
	return next((forecast for forecast in data["types"] if forecast["identifier"] == resource_type), None)


def store_prediction(connection, forecast):
	if not forecast or not forecast["sufficient"]:
		return None
	resource = forecast.get("resource")
	resource_id = resource["id"] if resource else None
	resource_type = None if resource else forecast["identifier"]
	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		"""SELECT id FROM predictions
		   WHERE target_start_date = %s AND target_end_date = %s
			 AND model_version = %s
			 AND ((resource_id = %s) OR (resource_id IS NULL AND resource_type = %s))""",
		(forecast["target_start"], forecast["target_end"], MODEL_VERSION, resource_id, resource_type),
	)
	existing = cursor.fetchone()
	values = (resource_id, resource_type, date.today(), forecast["target_start"], forecast["target_end"], Decimal(str(round(forecast["predicted_demand"], 2))), MODEL_VERSION)
	cursor = connection.cursor()
	if existing:
		cursor.execute(
			"""UPDATE predictions SET predicted_demand = %s, prediction_date = %s
			   WHERE id = %s""",
			(values[5], date.today(), existing["id"]),
		)
		prediction_id = existing["id"]
	else:
		cursor.execute(
			"""INSERT INTO predictions
			   (resource_id, resource_type, prediction_date, target_start_date,
				target_end_date, predicted_demand, model_version)
			   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
			values,
		)
		prediction_id = cursor.lastrowid
	connection.commit()
	return prediction_id
