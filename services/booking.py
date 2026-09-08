"""Planned-usage booking operations and validation."""

from datetime import datetime


class ValidationError(ValueError):
    """Raised when submitted booking data is not valid."""


ACTIVE_BOOKING_STATUSES = ("PENDING", "APPROVED")
BOOKING_STATUSES = ("PENDING", "APPROVED", "CANCELLED", "COMPLETED", "NO_SHOW")


def parse_datetime(value, field_name):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ValidationError(f"{field_name} must be a valid date and time.") from error


def validate_booking(connection, data, booking_id=None):
    """Validate booking input and reject overlaps before writing it."""
    start_time = parse_datetime(data.get("start_time"), "Start time")
    end_time = parse_datetime(data.get("end_time"), "End time")
    if end_time <= start_time:
        raise ValidationError("End time must be after start time.")

    try:
        resource_id = int(data.get("resource_id", ""))
        user_id = int(data.get("user_id", ""))
    except (TypeError, ValueError) as error:
        raise ValidationError("A resource and user are required.") from error

    purpose = data.get("purpose", "").strip()
    if not purpose:
        raise ValidationError("Purpose is required.")

    occupancy_value = data.get("expected_occupancy", "").strip()
    try:
        expected_occupancy = int(occupancy_value) if occupancy_value else None
    except ValueError as error:
        raise ValidationError("Expected occupancy must be a whole number.") from error
    if expected_occupancy is not None and expected_occupancy < 0:
        raise ValidationError("Expected occupancy cannot be negative.")

    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, capacity, status FROM resources WHERE id = %s", (resource_id,))
    resource = cursor.fetchone()
    if not resource or resource["status"] != "AVAILABLE":
        raise ValidationError("Select an available resource.")
    if resource["capacity"] is not None and expected_occupancy is not None and expected_occupancy > resource["capacity"]:
        raise ValidationError("Expected occupancy exceeds the resource capacity.")

    cursor.execute("SELECT id FROM users WHERE id = %s AND is_active = TRUE", (user_id,))
    if cursor.fetchone() is None:
        raise ValidationError("Select an active user.")

    department_value = data.get("department_id", "").strip()
    if department_value:
        try:
            department_id = int(department_value)
        except ValueError as error:
            raise ValidationError("Select a valid department.") from error
        cursor.execute("SELECT id FROM departments WHERE id = %s", (department_id,))
        if cursor.fetchone() is None:
            raise ValidationError("Select an existing department.")

    query = """SELECT id FROM bookings
               WHERE resource_id = %s
                 AND status IN ('PENDING', 'APPROVED')
                 AND start_time < %s AND end_time > %s"""
    parameters = [resource_id, end_time, start_time]
    if booking_id is not None:
        query += " AND id <> %s"
        parameters.append(booking_id)
    cursor.execute(query, tuple(parameters))
    if cursor.fetchone():
        raise ValidationError("This resource already has an overlapping active booking.")

    return resource_id, user_id, start_time, end_time, purpose, expected_occupancy


def create_booking(connection, data):
    values = validate_booking(connection, data)
    department_id = data.get("department_id") or None
    cursor = connection.cursor()
    cursor.execute(
        """INSERT INTO bookings
           (resource_id, user_id, department_id, start_time, end_time, purpose, status, expected_occupancy)
           VALUES (%s, %s, %s, %s, %s, %s, 'PENDING', %s)""",
        (*values[:2], department_id, *values[2:]),
    )
    connection.commit()
    return cursor.lastrowid


def update_booking(connection, booking_id, data):
    """Update an active booking after the same conflict validation."""
    values = validate_booking(connection, data, booking_id)
    department_id = data.get("department_id") or None
    cursor = connection.cursor()
    cursor.execute(
        """UPDATE bookings SET resource_id=%s, user_id=%s, department_id=%s,
           start_time=%s, end_time=%s, purpose=%s, expected_occupancy=%s
           WHERE id=%s AND status IN ('PENDING', 'APPROVED')""",
        (*values[:2], department_id, *values[2:], booking_id),
    )
    connection.commit()
