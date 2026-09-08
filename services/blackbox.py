"""Deterministic planned-versus-actual analysis for the Resource Black Box."""

from services.booking import ValidationError, parse_datetime


USAGE_STATUSES = {"SCHEDULED", "IN_USE", "COMPLETED", "CANCELLED", "NO_SHOW", "PARTIALLY_USED"}
UNDERUTILIZATION_THRESHOLD = 0.50


def _minutes(start, end):
    if not start or not end or end <= start:
        return None
    return (end - start).total_seconds() / 60


def _event_from_row(row):
    planned_minutes = _minutes(row["planned_start"], row["planned_end"])
    actual_minutes = _minutes(row["actual_start"], row["actual_end"])
    idle_minutes = max(planned_minutes - (actual_minutes or 0), 0) if planned_minutes is not None else 0
    utilization = (actual_minutes / planned_minutes * 100) if planned_minutes and actual_minutes is not None else None
    phantom = row["status"] == "NO_SHOW" or (row["usage_id"] is None and row["status"] != "CANCELLED")
    return {
        "booking_id": row["booking_id"],
        "booking_date": row["planned_start"].date() if row["planned_start"] else None,
        "planned_start": row["planned_start"],
        "planned_end": row["planned_end"],
        "actual_start": row["actual_start"],
        "actual_end": row["actual_end"],
        "planned_minutes": planned_minutes,
        "actual_minutes": actual_minutes,
        "idle_minutes": idle_minutes,
        "utilization": utilization,
        "booking_status": row["status"],
        "purpose": row["purpose"],
        "usage_id": row["usage_id"],
        "actual_occupancy": row["actual_occupancy"],
        "usage_status": row["usage_status"],
        "phantom": phantom,
    }


def _build_report(resource, rows):
    events = [_event_from_row(row) for row in rows]
    planned_minutes = sum(event["planned_minutes"] or 0 for event in events)
    actual_minutes = sum(event["actual_minutes"] or 0 for event in events)
    idle_minutes = sum(event["idle_minutes"] for event in events)
    utilization = actual_minutes / planned_minutes * 100 if planned_minutes else None
    usage_count = sum(event["actual_minutes"] is not None for event in events)
    phantom_count = sum(event["phantom"] for event in events)
    return {
        "resource": resource,
        "events": events,
        "metrics": {
            "booking_count": len(events),
            "usage_count": usage_count,
            "phantom_count": phantom_count,
            "planned_minutes": planned_minutes,
            "actual_minutes": actual_minutes,
            "idle_minutes": idle_minutes,
            "utilization": utilization,
            "underutilized": planned_minutes > 0 and (utilization or 0) < UNDERUTILIZATION_THRESHOLD * 100,
        },
    }


def get_forensic_reports(connection, resource_id=None, start_date=None, end_date=None, resource_type=None):
    """Return one deterministic report per active resource from joined source data."""
    resource_filters = ["r.status <> 'RETIRED'"]
    resource_parameters = []
    if resource_id is not None:
        resource_filters.append("r.id = %s")
        resource_parameters.append(resource_id)
    if resource_type:
        resource_filters.append("r.resource_type = %s")
        resource_parameters.append(resource_type)
    resource_where = " AND ".join(resource_filters)
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        f"""SELECT r.id, r.name, r.resource_type, r.location, r.capacity, r.status,
                   d.name AS department_name
            FROM resources r LEFT JOIN departments d ON d.id = r.department_id
            WHERE {resource_where}
            ORDER BY r.name""",
        resource_parameters,
    )
    resources = cursor.fetchall()
    if not resources:
        return []

    event_filters = ["b.status <> 'CANCELLED'"]
    event_parameters = []
    if start_date:
        event_filters.append("DATE(b.start_time) >= %s")
        event_parameters.append(start_date)
    if end_date:
        event_filters.append("DATE(b.start_time) <= %s")
        event_parameters.append(end_date)
    event_where = " AND ".join(event_filters)
    cursor.execute(
        f"""SELECT b.id AS booking_id, b.resource_id, b.start_time AS planned_start,
                   b.end_time AS planned_end, b.status, b.purpose,
                   ur.id AS usage_id, ur.actual_start_time AS actual_start,
                   ur.actual_end_time AS actual_end, ur.actual_occupancy,
                   ur.usage_status
            FROM bookings b LEFT JOIN usage_records ur ON ur.booking_id = b.id
            WHERE {event_where}
            ORDER BY b.start_time""",
        event_parameters,
    )
    rows_by_resource = {resource["id"]: [] for resource in resources}
    for row in cursor.fetchall():
        if row["resource_id"] in rows_by_resource:
            rows_by_resource[row["resource_id"]].append(row)
    return [_build_report(resource, rows_by_resource[resource["id"]]) for resource in resources]


def summarize_reports(reports):
    planned = sum(report["metrics"]["planned_minutes"] for report in reports)
    actual = sum(report["metrics"]["actual_minutes"] for report in reports)
    return {
        "resource_count": len(reports),
        "resources_with_usage": sum(report["metrics"]["usage_count"] > 0 for report in reports),
        "planned_minutes": planned,
        "actual_minutes": actual,
        "idle_minutes": sum(report["metrics"]["idle_minutes"] for report in reports),
        "utilization": actual / planned * 100 if planned else None,
        "phantom_count": sum(report["metrics"]["phantom_count"] for report in reports),
        "underutilized_count": sum(report["metrics"]["underutilized"] for report in reports),
    }


def get_analysis_data(reports):
    underutilized = sorted(
        (report for report in reports if report["metrics"]["underutilized"]),
        key=lambda report: report["metrics"]["utilization"] or 0,
    )
    highest = sorted(
        (report for report in reports if report["metrics"]["planned_minutes"]),
        key=lambda report: report["metrics"]["utilization"] or 0,
        reverse=True,
    )
    phantom = [
        (report["resource"], event)
        for report in reports
        for event in report["events"]
        if event["phantom"]
    ]
    usage_by_day = {}
    for report in reports:
        for event in report["events"]:
            if event["actual_start"] and event["actual_minutes"] is not None:
                day = event["actual_start"].date().isoformat()
                usage_by_day[day] = usage_by_day.get(day, 0) + event["actual_minutes"]
    return {
        "underutilized": underutilized,
        "highest_utilization": highest[:5],
        "phantom": phantom,
        "usage_by_day": sorted(usage_by_day.items()),
    }


def get_usage_form_data(connection):
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """SELECT b.id, b.resource_id, b.start_time, b.end_time, b.status,
                  r.name AS resource_name, r.resource_type, r.location, r.capacity
           FROM bookings b JOIN resources r ON r.id = b.resource_id
           WHERE b.status <> 'CANCELLED'
             AND NOT EXISTS (SELECT 1 FROM usage_records ur WHERE ur.booking_id = b.id)
           ORDER BY b.start_time DESC"""
    )
    return cursor.fetchall()


def create_usage_record(connection, data):
    """Record one explicit actual-usage event against an existing booking."""
    try:
        booking_id = int(data.get("booking_id", ""))
    except (TypeError, ValueError) as error:
        raise ValidationError("Select an existing booking.") from error
    actual_start = parse_datetime(data.get("actual_start_time"), "Actual start time")
    actual_end = parse_datetime(data.get("actual_end_time"), "Actual end time")
    if actual_end <= actual_start:
        raise ValidationError("Actual end time must be after actual start time.")
    occupancy_value = data.get("actual_occupancy", "").strip()
    try:
        actual_occupancy = int(occupancy_value) if occupancy_value else None
    except ValueError as error:
        raise ValidationError("Actual occupancy must be a whole number.") from error
    if actual_occupancy is not None and actual_occupancy < 0:
        raise ValidationError("Actual occupancy cannot be negative.")

    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """SELECT b.resource_id, b.start_time, b.end_time, r.capacity
           FROM bookings b JOIN resources r ON r.id = b.resource_id WHERE b.id = %s""",
        (booking_id,),
    )
    booking = cursor.fetchone()
    if not booking:
        raise ValidationError("Select an existing booking.")
    if booking["capacity"] is not None and actual_occupancy is not None and actual_occupancy > booking["capacity"]:
        raise ValidationError("Actual occupancy exceeds the resource capacity.")
    cursor.execute("SELECT id FROM usage_records WHERE booking_id = %s", (booking_id,))
    if cursor.fetchone():
        raise ValidationError("This booking already has an actual usage record.")

    planned_minutes = _minutes(booking["start_time"], booking["end_time"])
    actual_minutes = _minutes(actual_start, actual_end)
    cursor = connection.cursor()
    cursor.execute(
        """INSERT INTO usage_records
           (booking_id, resource_id, planned_start_time, planned_end_time,
            actual_start_time, actual_end_time, planned_duration_minutes,
            actual_duration_minutes, actual_occupancy, capacity_at_usage,
            idle_time_minutes, is_phantom_booking, usage_status, source, notes)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, 'COMPLETED', 'MANUAL', %s)""",
        (booking_id, booking["resource_id"], booking["start_time"], booking["end_time"],
         actual_start, actual_end, int(planned_minutes), int(actual_minutes), actual_occupancy,
         booking["capacity"], int(max(planned_minutes - actual_minutes, 0)), data.get("notes", "").strip() or None),
    )
    connection.commit()
    return cursor.lastrowid
