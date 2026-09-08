"""Predictive maintenance service placeholder for incremental implementation."""
"""Maintenance records, sensor readings, and explainable attention evidence."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from services.booking import ValidationError, parse_datetime
from services.blackbox import get_forensic_reports
from services.prediction import get_resource_forecast


MAINTENANCE_STATUSES = ("SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED")
ACTIVE_MAINTENANCE_STATUSES = ("SCHEDULED", "IN_PROGRESS")
SENSOR_THRESHOLDS = {
	"TEMPERATURE": {"attention": 40, "high": 60, "unit": "C", "direction": "above"},
	"VIBRATION": {"attention": 5, "high": 10, "unit": "mm/s", "direction": "above"},
	"BATTERY": {"attention": 20, "high": 10, "unit": "%", "direction": "below"},
	"USAGE_HOURS": {"attention": 1000, "high": 2000, "unit": "hours", "direction": "above"},
}


def _optional_datetime(value, field_name):
	return parse_datetime(value, field_name) if value else None


def _optional_decimal(value, field_name):
	if not value:
		return None
	try:
		result = Decimal(value)
	except (InvalidOperation, TypeError, ValueError) as error:
		raise ValidationError(f"{field_name} must be a valid amount.") from error
	if result < 0:
		raise ValidationError(f"{field_name} cannot be negative.")
	return result


def get_resource_options(connection):
	cursor = connection.cursor(dictionary=True)
	cursor.execute("SELECT id, name, resource_type, location, capacity, status FROM resources ORDER BY name")
	return cursor.fetchall()


def validate_maintenance(connection, data):
	try:
		resource_id = int(data.get("resource_id", ""))
	except (TypeError, ValueError) as error:
		raise ValidationError("Select a resource.") from error
	maintenance_type = data.get("maintenance_type", "").strip()
	description = data.get("description", "").strip()
	status = data.get("status", "SCHEDULED").upper()
	if not maintenance_type or not description:
		raise ValidationError("Maintenance type and description are required.")
	if status not in MAINTENANCE_STATUSES:
		raise ValidationError("Select a valid maintenance status.")
	cursor = connection.cursor(dictionary=True)
	cursor.execute("SELECT id, status FROM resources WHERE id = %s", (resource_id,))
	resource = cursor.fetchone()
	if resource is None:
		raise ValidationError("Select an existing resource.")
	if resource["status"] == "RETIRED":
		raise ValidationError("Retired resources cannot receive maintenance records.")
	reported_date = _optional_datetime(data.get("reported_date"), "Reported date") or datetime.now()
	scheduled_date = _optional_datetime(data.get("scheduled_date"), "Scheduled date")
	completed_date = _optional_datetime(data.get("completed_date"), "Completed date")
	if completed_date and completed_date < reported_date:
		raise ValidationError("Completed date cannot be before reported date.")
	try:
		downtime = int(data.get("downtime_minutes", "")) if data.get("downtime_minutes") else None
	except ValueError as error:
		raise ValidationError("Downtime must be a whole number.") from error
	if downtime is not None and downtime < 0:
		raise ValidationError("Downtime cannot be negative.")
	return (resource_id, data.get("technician_user_id") or None, maintenance_type, description, status,
			reported_date, scheduled_date, completed_date, downtime,
			_optional_decimal(data.get("cost"), "Cost"), data.get("notes", "").strip() or None)


def create_maintenance_record(connection, data):
	values = validate_maintenance(connection, data)
	cursor = connection.cursor()
	cursor.execute(
		"""INSERT INTO maintenance_records
		   (resource_id, technician_user_id, maintenance_type, description, status,
			reported_date, scheduled_date, completed_date, downtime_minutes, cost, notes)
		   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
		values,
	)
	record_id = cursor.lastrowid
	if values[4] in ACTIVE_MAINTENANCE_STATUSES:
		cursor.execute("UPDATE resources SET status = 'MAINTENANCE' WHERE id = %s AND status <> 'RETIRED'", (values[0],))
	connection.commit()
	return record_id


def complete_maintenance_record(connection, record_id):
	cursor = connection.cursor(dictionary=True)
	cursor.execute("SELECT id, resource_id, status, reported_date FROM maintenance_records WHERE id = %s", (record_id,))
	record = cursor.fetchone()
	if not record:
		raise ValidationError("Maintenance record not found.")
	if record["status"] not in ACTIVE_MAINTENANCE_STATUSES:
		raise ValidationError("Only active maintenance records can be completed.")
	cursor = connection.cursor()
	cursor.execute("UPDATE maintenance_records SET status = 'COMPLETED', completed_date = CURRENT_TIMESTAMP WHERE id = %s", (record_id,))
	cursor.execute("SELECT COUNT(*) AS active_count FROM maintenance_records WHERE resource_id = %s AND status IN ('SCHEDULED', 'IN_PROGRESS')", (record["resource_id"],))
	active_count = cursor.fetchone()[0]
	if active_count == 0:
		cursor.execute("UPDATE resources SET status = 'AVAILABLE' WHERE id = %s AND status = 'MAINTENANCE'", (record["resource_id"],))
	connection.commit()


def get_maintenance_records(connection, resource_id=None, status=None):
	clauses, parameters = [], []
	if resource_id is not None:
		clauses.append("m.resource_id = %s")
		parameters.append(resource_id)
	if status in MAINTENANCE_STATUSES:
		clauses.append("m.status = %s")
		parameters.append(status)
	where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		f"""SELECT m.*, r.name AS resource_name, r.resource_type, r.location, r.status AS resource_status,
				   d.name AS department_name, u.full_name AS technician_name
			FROM maintenance_records m JOIN resources r ON r.id = m.resource_id
			LEFT JOIN departments d ON d.id = r.department_id
			LEFT JOIN users u ON u.id = m.technician_user_id{where}
			ORDER BY m.reported_date DESC, m.id DESC""",
		parameters,
	)
	return cursor.fetchall()


def classify_sensor(sensor_type, value, unit):
	normalized = sensor_type.strip().upper()
	threshold = SENSOR_THRESHOLDS.get(normalized)
	if not threshold:
		return {"level": "INFORMATIONAL", "reason": "Unknown sensor type; reading is informational."}
	reading = float(value)
	if threshold["direction"] == "above":
		if reading >= threshold["high"]:
			return {"level": "HIGH", "reason": f"{normalized} exceeds the critical threshold of {threshold['high']} {threshold['unit']}."}
		if reading >= threshold["attention"]:
			return {"level": "ATTENTION", "reason": f"{normalized} exceeds the attention threshold of {threshold['attention']} {threshold['unit']}."}
	else:
		if reading <= threshold["high"]:
			return {"level": "HIGH", "reason": f"{normalized} is at or below the critical threshold of {threshold['high']} {threshold['unit']}."}
		if reading <= threshold["attention"]:
			return {"level": "ATTENTION", "reason": f"{normalized} is at or below the attention threshold of {threshold['attention']} {threshold['unit']}."}
	return {"level": "NORMAL", "reason": "Reading is within the configured known range."}


def create_sensor_reading(connection, data):
	try:
		resource_id = int(data.get("resource_id", ""))
		value = Decimal(data.get("reading_value", ""))
	except (TypeError, ValueError, InvalidOperation) as error:
		raise ValidationError("Select a resource and enter a valid sensor value.") from error
	sensor_type = data.get("sensor_type", "").strip()
	if not sensor_type:
		raise ValidationError("Sensor type is required.")
	recorded_at = _optional_datetime(data.get("recorded_at"), "Recorded date") or datetime.now()
	cursor = connection.cursor()
	cursor.execute("SELECT id FROM resources WHERE id = %s AND status <> 'RETIRED'", (resource_id,))
	if cursor.fetchone() is None:
		raise ValidationError("Select an active resource.")
	cursor.execute(
		"INSERT INTO sensor_readings (resource_id, recorded_at, sensor_type, reading_value, unit) VALUES (%s, %s, %s, %s, %s)",
		(resource_id, recorded_at, sensor_type.upper(), value, data.get("unit", "").strip() or None),
	)
	connection.commit()
	return cursor.lastrowid


def get_sensor_readings(connection, resource_id=None, limit=None):
	cursor = connection.cursor(dictionary=True)
	parameters = []
	where = ""
	if resource_id is not None:
		where = " WHERE s.resource_id = %s"
		parameters.append(resource_id)
	query = f"""SELECT s.*, r.name AS resource_name FROM sensor_readings s
				JOIN resources r ON r.id = s.resource_id{where} ORDER BY s.recorded_at DESC"""
	if limit:
		query += " LIMIT %s"
		parameters.append(int(limit))
	cursor.execute(query, parameters)
	readings = cursor.fetchall()
	for reading in readings:
		reading.update(classify_sensor(reading["sensor_type"], reading["reading_value"], reading["unit"]))
	return readings


def get_resource_maintenance_report(connection, resource_id):
	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		"""SELECT r.*, d.name AS department_name FROM resources r
		   LEFT JOIN departments d ON d.id = r.department_id WHERE r.id = %s""",
		(resource_id,),
	)
	resource = cursor.fetchone()
	if not resource:
		return None
	records = get_maintenance_records(connection, resource_id=resource_id)
	readings = get_sensor_readings(connection, resource_id=resource_id, limit=10)
	active = [record for record in records if record["status"] in ACTIVE_MAINTENANCE_STATUSES]
	attention = [reading for reading in readings if reading["level"] in ("ATTENTION", "HIGH")]
	if any(reading["level"] == "HIGH" for reading in attention) or len(active) > 1:
		level = "HIGH"
	elif active or attention or len(records) >= 3:
		level = "ATTENTION"
	else:
		level = "NORMAL"
	reasons = []
	if active:
		reasons.append(f"{len(active)} active maintenance case(s).")
	reasons.extend(reading["reason"] for reading in attention)
	if len(records) >= 3:
		reasons.append("Repeated maintenance activity in recorded history.")
	if not reasons:
		reasons.append("No active maintenance issues or abnormal known sensor readings.")
	forecast = get_resource_forecast(connection, resource_id)
	return {
		"resource": resource,
		"records": records,
		"readings": readings,
		"metrics": {"total": len(records), "open": len(active), "completed": sum(record["status"] == "COMPLETED" for record in records), "downtime": sum(record["downtime_minutes"] or 0 for record in records)},
		"attention_level": level,
		"reasons": reasons,
		"forecast": forecast,
	}


def get_maintenance_analysis(connection):
	resources = get_resource_options(connection)
	reports = [get_resource_maintenance_report(connection, resource["id"]) for resource in resources]
	reports = [report for report in reports if report]
	return {
		"attention": sorted((report for report in reports if report["attention_level"] != "NORMAL"), key=lambda report: (report["attention_level"] != "HIGH", -report["metrics"]["open"])),
		"repeated": [report for report in reports if report["metrics"]["total"] >= 3],
		"downtime": sorted((report for report in reports if report["metrics"]["downtime"]), key=lambda report: report["metrics"]["downtime"], reverse=True),
		"alerts": [reading for report in reports for reading in report["readings"] if reading["level"] in ("ATTENTION", "HIGH")],
	}


def get_maintenance_summary(connection):
	cursor = connection.cursor(dictionary=True)
	cursor.execute("SELECT COUNT(*) AS total, SUM(status IN ('SCHEDULED', 'IN_PROGRESS')) AS open_cases, SUM(status = 'COMPLETED') AS completed FROM maintenance_records")
	summary = cursor.fetchone()
	cursor.execute("SELECT COUNT(DISTINCT resource_id) AS under_maintenance FROM maintenance_records WHERE status IN ('SCHEDULED', 'IN_PROGRESS')")
	summary.update(cursor.fetchone())
	summary["abnormal_readings"] = sum(reading["level"] in ("ATTENTION", "HIGH") for reading in get_sensor_readings(connection))
	return summary
