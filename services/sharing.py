"""Resource sharing service placeholder for incremental implementation."""
"""Resource sharing requests and evidence-based candidate search."""

from services.blackbox import get_forensic_reports
from services.booking import ValidationError


SHARING_STATUSES = ("PENDING", "APPROVED", "REJECTED", "CANCELLED", "COMPLETED")


def _as_int(value, message):
	try:
		return int(value)
	except (TypeError, ValueError) as error:
		raise ValidationError(message) from error


def get_sharing_candidates(connection, filters=None):
	filters = filters or {}
	clauses = ["r.status = 'AVAILABLE'"]
	parameters = []
	if filters.get("resource_type"):
		clauses.append("r.resource_type = %s")
		parameters.append(filters["resource_type"])
	if filters.get("department_id", "").isdigit():
		clauses.append("r.department_id = %s")
		parameters.append(int(filters["department_id"]))
	if filters.get("capacity", "").isdigit():
		clauses.append("r.capacity >= %s")
		parameters.append(int(filters["capacity"]))
	if filters.get("q"):
		clauses.append("(r.name LIKE %s OR r.location LIKE %s)")
		value = f"%{filters['q']}%"
		parameters.extend((value, value))
	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		f"""SELECT r.id, r.name, r.resource_type, r.location, r.capacity, r.status,
				   d.id AS department_id, d.name AS department_name
			FROM resources r LEFT JOIN departments d ON d.id = r.department_id
			WHERE {' AND '.join(clauses)} ORDER BY r.name""",
		parameters,
	)
	candidates = cursor.fetchall()
	reports = {report["resource"]["id"]: report for report in get_forensic_reports(connection)}
	for candidate in candidates:
		report = reports.get(candidate["id"])
		candidate["utilization"] = report["metrics"]["utilization"] if report else None
		candidate["underutilized"] = report["metrics"]["underutilized"] if report else False
	return candidates


def validate_request(connection, data):
	requesting_department_id = _as_int(data.get("requesting_department_id"), "Select a requesting department.")
	requested_resource_id = _as_int(data.get("requested_resource_id"), "Select a resource to request.")
	requested_quantity = _as_int(data.get("requested_quantity", "1"), "Quantity must be a whole number.")
	if requested_quantity <= 0:
		raise ValidationError("Requested quantity must be greater than zero.")
	reason = data.get("reason", "").strip()
	if not reason:
		raise ValidationError("Purpose or reason is required.")

	cursor = connection.cursor(dictionary=True)
	cursor.execute("SELECT id FROM departments WHERE id = %s", (requesting_department_id,))
	if cursor.fetchone() is None:
		raise ValidationError("Select an existing requesting department.")
	requesting_user_id = data.get("requesting_user_id") or None
	if requesting_user_id:
		requesting_user_id = _as_int(requesting_user_id, "Select a valid requester.")
		cursor.execute("SELECT id FROM users WHERE id = %s AND is_active = TRUE", (requesting_user_id,))
		if cursor.fetchone() is None:
			raise ValidationError("Select an active requester.")
	cursor.execute(
		"""SELECT id, department_id, resource_type, status FROM resources WHERE id = %s""",
		(requested_resource_id,),
	)
	resource = cursor.fetchone()
	if not resource:
		raise ValidationError("Select an existing resource.")
	if resource["status"] != "AVAILABLE":
		raise ValidationError("Select an available resource for sharing.")
	return (
		requesting_department_id,
		requesting_user_id,
		resource["department_id"],
		requested_resource_id,
		resource["resource_type"],
		requested_resource_id,
		requested_quantity,
		reason,
	)


def create_sharing_request(connection, data):
	values = validate_request(connection, data)
	cursor = connection.cursor()
	cursor.execute(
		"""INSERT INTO sharing_requests
		   (requesting_department_id, requesting_user_id, source_department_id,
			requested_resource_id, requested_resource_type, matched_resource_id,
			requested_quantity, reason)
		   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
		values,
	)
	connection.commit()
	return cursor.lastrowid


def get_request_rows(connection, status=""):
	clauses = []
	parameters = []
	if status in SHARING_STATUSES:
		clauses.append("sr.status = %s")
		parameters.append(status)
	where_clause = f" WHERE {' AND '.join(clauses)}" if clauses else ""
	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		f"""SELECT sr.*, rr.name AS resource_name, rr.resource_type, rr.location,
				   owner.name AS owning_department, requester.name AS requesting_department,
				   u.full_name AS requester_name
			FROM sharing_requests sr
			LEFT JOIN resources rr ON rr.id = COALESCE(sr.matched_resource_id, sr.requested_resource_id)
			LEFT JOIN departments owner ON owner.id = sr.source_department_id
			JOIN departments requester ON requester.id = sr.requesting_department_id
			LEFT JOIN users u ON u.id = sr.requesting_user_id{where_clause}
			ORDER BY sr.request_date DESC, sr.id DESC""",
		parameters,
	)
	return cursor.fetchall()


def get_request_details(connection, request_id):
	rows = get_request_rows(connection)
	return next((row for row in rows if row["id"] == request_id), None)


def transition_request(connection, request_id, action):
	if action not in {"APPROVED", "REJECTED", "CANCELLED", "COMPLETED"}:
		raise ValidationError("Invalid sharing request action.")
	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		"""SELECT sr.id, sr.status, r.status AS resource_status
		   FROM sharing_requests sr LEFT JOIN resources r
			 ON r.id = COALESCE(sr.matched_resource_id, sr.requested_resource_id)
		   WHERE sr.id = %s""",
		(request_id,),
	)
	request_row = cursor.fetchone()
	if not request_row:
		raise ValidationError("Sharing request not found.")
	if action == "COMPLETED":
		if request_row["status"] != "APPROVED":
			raise ValidationError("Only approved sharing requests can be completed.")
		cursor = connection.cursor()
		cursor.execute("UPDATE sharing_requests SET status = 'COMPLETED' WHERE id = %s", (request_id,))
		connection.commit()
		return
	if request_row["status"] != "PENDING":
		raise ValidationError("Only pending sharing requests can be changed.")
	if action == "APPROVED" and request_row["resource_status"] == "RETIRED":
		raise ValidationError("The requested resource is no longer active.")
	if action == "APPROVED" and request_row["resource_status"] is None:
		raise ValidationError("The requested resource no longer exists.")
	cursor = connection.cursor()
	if action == "APPROVED":
		cursor.execute("UPDATE sharing_requests SET status = 'APPROVED', approved_at = CURRENT_TIMESTAMP WHERE id = %s", (request_id,))
	else:
		cursor.execute("UPDATE sharing_requests SET status = %s WHERE id = %s", (action, request_id))
	connection.commit()


def get_sharing_summary(connection):
	cursor = connection.cursor(dictionary=True)
	cursor.execute("SELECT COUNT(*) AS candidates FROM resources WHERE status = 'AVAILABLE'")
	summary = cursor.fetchone()
	cursor.execute("SELECT status, COUNT(*) AS count FROM sharing_requests GROUP BY status")
	summary.update({row["status"].lower(): row["count"] for row in cursor.fetchall()})
	for status in SHARING_STATUSES:
		summary.setdefault(status.lower(), 0)
	return summary
