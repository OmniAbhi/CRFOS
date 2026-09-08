"""Cost optimization service placeholder for incremental implementation."""
"""Purchase tracking and deterministic procurement evidence for RCOS."""

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from services.blackbox import get_forensic_reports
from services.booking import ValidationError


PURCHASE_STATUSES = ("PLANNED", "ORDERED", "RECEIVED", "CANCELLED")
MONEY_PLACES = Decimal("0.01")


def _existing_id(connection, table, value):
	cursor = connection.cursor()
	cursor.execute(f"SELECT id FROM {table} WHERE id = %s", (value,))
	return cursor.fetchone() is not None


def validate_purchase(connection, data):
	item_name = data.get("item_name", "").strip()
	if not item_name:
		raise ValidationError("Item or resource name is required.")
	try:
		quantity = int(data.get("quantity", ""))
	except (TypeError, ValueError) as error:
		raise ValidationError("Quantity must be a whole number.") from error
	if quantity <= 0:
		raise ValidationError("Quantity must be greater than zero.")
	try:
		unit_cost = Decimal(data.get("unit_cost", "")).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
	except (InvalidOperation, TypeError, ValueError) as error:
		raise ValidationError("Unit cost must be a valid amount.") from error
	if unit_cost < 0:
		raise ValidationError("Unit cost cannot be negative.")
	try:
		purchase_date = date.fromisoformat(data.get("purchase_date", ""))
	except (TypeError, ValueError) as error:
		raise ValidationError("Purchase date must be valid.") from error

	resource_id = data.get("resource_id", "").strip() or None
	supplier_id = data.get("supplier_id", "").strip() or None
	department_id = data.get("department_id", "").strip() or None
	for field_name, value, table_name in (
		("resource", resource_id, "resources"),
		("supplier", supplier_id, "suppliers"),
		("department", department_id, "departments"),
	):
		if value is not None:
			try:
				numeric_value = int(value)
			except ValueError as error:
				raise ValidationError(f"Select a valid {field_name}.") from error
			if not _existing_id(connection, table_name, numeric_value):
				raise ValidationError(f"Select an existing {field_name}.")
			if field_name == "resource":
				resource_id = numeric_value
			elif field_name == "supplier":
				supplier_id = numeric_value
			else:
				department_id = numeric_value

	status = data.get("status", "PLANNED").upper()
	if status not in PURCHASE_STATUSES:
		raise ValidationError("Select a valid purchase status.")
	total_cost = (unit_cost * quantity).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
	return (
		resource_id,
		supplier_id,
		department_id,
		item_name,
		quantity,
		unit_cost,
		total_cost,
		purchase_date,
		data.get("purchase_order_number", "").strip() or None,
		data.get("procurement_notes", "").strip() or None,
		data.get("purpose", "").strip() or None,
		status,
	)


def create_purchase(connection, data):
	values = validate_purchase(connection, data)
	cursor = connection.cursor()
	cursor.execute(
		"""INSERT INTO purchases
		   (resource_id, supplier_id, department_id, item_name, quantity,
			unit_cost, total_cost, purchase_date, purchase_order_number,
			procurement_notes, purpose, status)
		   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
		values,
	)
	connection.commit()
	return cursor.lastrowid


def get_purchase_options(connection):
	cursor = connection.cursor(dictionary=True)
	cursor.execute("SELECT id, name, resource_type FROM resources WHERE status <> 'RETIRED' ORDER BY name")
	resources = cursor.fetchall()
	cursor.execute("SELECT id, name FROM suppliers ORDER BY name")
	suppliers = cursor.fetchall()
	cursor.execute("SELECT id, name FROM departments ORDER BY name")
	departments = cursor.fetchall()
	return resources, suppliers, departments


def get_cost_summary(connection):
	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		"""SELECT COUNT(*) AS purchase_count,
				  COALESCE(SUM(CASE WHEN status <> 'CANCELLED' THEN total_cost ELSE 0 END), 0) AS total_expenditure,
				  COALESCE(AVG(CASE WHEN status <> 'CANCELLED' THEN unit_cost END), 0) AS average_unit_cost,
				  COALESCE(SUM(CASE WHEN status <> 'CANCELLED' AND YEAR(purchase_date) = YEAR(CURDATE())
									AND MONTH(purchase_date) = MONTH(CURDATE()) THEN total_cost ELSE 0 END), 0) AS current_expenditure
		   FROM purchases"""
	)
	summary = cursor.fetchone()
	cursor.execute(
		"""SELECT COUNT(DISTINCT COALESCE(NULLIF(r.resource_type, ''), p.item_name)) AS category_count
		   FROM purchases p LEFT JOIN resources r ON r.id = p.resource_id
		   WHERE p.status <> 'CANCELLED'"""
	)
	summary["category_count"] = cursor.fetchone()["category_count"]
	return summary


def get_purchase_rows(connection, filters):
	clauses = []
	parameters = []
	if filters.get("date"):
		clauses.append("p.purchase_date = %s")
		parameters.append(filters["date"])
	if filters.get("department_id", "").isdigit():
		clauses.append("p.department_id = %s")
		parameters.append(int(filters["department_id"]))
	if filters.get("supplier_id", "").isdigit():
		clauses.append("p.supplier_id = %s")
		parameters.append(int(filters["supplier_id"]))
	if filters.get("q"):
		clauses.append("(p.item_name LIKE %s OR r.name LIKE %s OR r.resource_type LIKE %s)")
		value = f"%{filters['q']}%"
		parameters.extend((value, value, value))
	where_clause = f" WHERE {' AND '.join(clauses)}" if clauses else ""
	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		f"""SELECT p.*, r.name AS resource_name, r.resource_type,
				   s.name AS supplier_name, d.name AS department_name
			FROM purchases p LEFT JOIN resources r ON r.id = p.resource_id
			LEFT JOIN suppliers s ON s.id = p.supplier_id
			LEFT JOIN departments d ON d.id = p.department_id{where_clause}
			ORDER BY p.purchase_date DESC, p.id DESC""",
		parameters,
	)
	return cursor.fetchall()


def get_purchase_details(connection, purchase_id):
	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		"""SELECT p.*, r.name AS resource_name, r.resource_type,
				  s.name AS supplier_name, d.name AS department_name
		   FROM purchases p LEFT JOIN resources r ON r.id = p.resource_id
		   LEFT JOIN suppliers s ON s.id = p.supplier_id
		   LEFT JOIN departments d ON d.id = p.department_id
		   WHERE p.id = %s""",
		(purchase_id,),
	)
	return cursor.fetchone()


def get_cost_analysis(connection):
	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		"""SELECT COALESCE(d.name, 'Unassigned') AS department_name,
				  COALESCE(SUM(p.total_cost), 0) AS total_cost
		   FROM purchases p LEFT JOIN departments d ON d.id = p.department_id
		   WHERE p.status <> 'CANCELLED'
		   GROUP BY p.department_id, d.name ORDER BY total_cost DESC"""
	)
	by_department = cursor.fetchall()
	cursor.execute(
		"""SELECT p.item_name, COALESCE(r.resource_type, 'Item') AS resource_type,
				  SUM(p.quantity) AS quantity, SUM(p.total_cost) AS total_cost
		   FROM purchases p LEFT JOIN resources r ON r.id = p.resource_id
		   WHERE p.status <> 'CANCELLED'
		   GROUP BY p.item_name, r.resource_type ORDER BY total_cost DESC"""
	)
	by_item = cursor.fetchall()
	cursor.execute(
		"""SELECT DATE_FORMAT(purchase_date, '%Y-%m') AS month,
				  SUM(total_cost) AS total_cost
		   FROM purchases WHERE status <> 'CANCELLED'
		   GROUP BY month ORDER BY month"""
	)
	by_month = cursor.fetchall()
	return {"by_department": by_department, "by_item": by_item, "by_month": by_month}


def procurement_check(connection, resource_type, requested_quantity):
	reports = get_forensic_reports(connection, resource_type=resource_type)
	cursor = connection.cursor(dictionary=True)
	cursor.execute(
		"""SELECT COUNT(*) AS registered,
				  COALESCE(SUM(status = 'AVAILABLE'), 0) AS available,
				  COALESCE(SUM(status = 'RETIRED'), 0) AS retired
		   FROM resources WHERE LOWER(resource_type) = LOWER(%s)""",
		(resource_type,),
	)
	inventory = cursor.fetchone()
	cursor.execute(
		"""SELECT COUNT(CASE WHEN p.status <> 'CANCELLED' THEN 1 END) AS purchase_count,
				  COALESCE(SUM(p.quantity), 0) AS purchased_quantity,
			  AVG(CASE WHEN p.status <> 'CANCELLED' THEN p.unit_cost END) AS reference_unit_cost,
			  COALESCE(SUM(CASE WHEN p.status <> 'CANCELLED' THEN p.total_cost ELSE 0 END), 0) AS recent_expenditure
		   FROM purchases p LEFT JOIN resources r ON r.id = p.resource_id
		   WHERE p.item_name = %s OR r.resource_type = %s""",
		(resource_type, resource_type),
	)
	purchase_history = cursor.fetchone()
	total = inventory["registered"]
	available = inventory["available"]
	retired = inventory["retired"]
	underutilized = sum(report["metrics"]["underutilized"] for report in reports)
	reference_cost = purchase_history["reference_unit_cost"]
	evidence_quantity = int(requested_quantity)
	if available >= evidence_quantity and underutilized >= evidence_quantity:
		conclusion = "Existing resources may be sufficient"
	elif total and available == 0:
		conclusion = "Existing inventory appears heavily utilized"
	elif total:
		conclusion = "Existing resource information is available"
	else:
		conclusion = "Insufficient existing resource information"
	estimate = None
	if available >= evidence_quantity and reference_cost is not None:
		estimate = (reference_cost * evidence_quantity).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
	return {
		"resource_type": resource_type,
		"requested_quantity": evidence_quantity,
		"registered": total,
		"available": available,
		"retired": retired,
		"underutilized": underutilized,
		"purchase_history": purchase_history,
		"conclusion": conclusion,
		"potential_avoided_purchase": estimate,
	}
