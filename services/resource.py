"""Resource registry operations for Stage 3.

Authentication is not implemented in the current CRFOS foundation. The
mutation routes are therefore ready to be protected by DEPARTMENT_ADMIN and
ADMIN checks when the existing user system gains a login context.
"""

from services.booking import ValidationError


RESOURCE_STATUSES = {"AVAILABLE", "UNAVAILABLE", "MAINTENANCE", "RETIRED"}


def validate_resource(connection, data):
    name = data.get("name", "").strip()
    resource_type = data.get("resource_type", "").strip()
    location = data.get("location", "").strip()
    status = data.get("status", "AVAILABLE").upper()
    if not name:
        raise ValidationError("Resource name is required.")
    if not resource_type:
        raise ValidationError("Resource type is required.")
    if not location:
        raise ValidationError("Location is required.")
    if status not in RESOURCE_STATUSES:
        raise ValidationError("Select a valid resource status.")
    capacity_value = data.get("capacity", "").strip()
    try:
        capacity = int(capacity_value) if capacity_value else None
    except ValueError as error:
        raise ValidationError("Capacity must be a whole number.") from error
    if capacity is not None and capacity < 0:
        raise ValidationError("Capacity cannot be negative.")

    department_value = data.get("department_id", "").strip()
    if not department_value:
        raise ValidationError("Department is required.")
    try:
        department_id = int(department_value)
    except ValueError as error:
        raise ValidationError("Select a valid department.") from error
    cursor = connection.cursor()
    cursor.execute("SELECT id FROM departments WHERE id = %s", (department_id,))
    if cursor.fetchone() is None:
        raise ValidationError("Select an existing department.")

    return department_id, name, resource_type, location, capacity, status, data.get("description", "").strip() or None


def save_resource(connection, data, resource_id=None):
    values = validate_resource(connection, data)
    cursor = connection.cursor()
    if resource_id is None:
        cursor.execute(
            """INSERT INTO resources (department_id, name, resource_type, location, capacity, status, description)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            values,
        )
        result = cursor.lastrowid
    else:
        cursor.execute(
            """UPDATE resources SET department_id=%s, name=%s, resource_type=%s, location=%s,
               capacity=%s, status=%s, description=%s WHERE id=%s""",
            (*values, resource_id),
        )
        result = resource_id
    connection.commit()
    return result
