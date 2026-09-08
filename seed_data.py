"""Seed CRFOS with synthetic RSET-modeled demonstration data.

Operational records created here are synthetic demonstration data. They are not
official Rajagiri School of Engineering & Technology institutional records.
Run with: python seed_data.py
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from database import get_db_connection
from services.prediction import get_prediction_data, store_prediction


DEMO_PREFIX = "[CRFOS DEMO RSET]"
DEMO_SOURCE = "RSET_DEMO"
DEMO_DEPARTMENT_PREFIX = "RSET_"
DEMO_EMAIL_PREFIX = "rset.demo."
DEMO_CODE_PREFIX = "RSET_"

DEPARTMENTS = [
    ("Computer Science and Engineering", "RSET_CSE"),
    ("Electronics and Communication Engineering", "RSET_ECE"),
    ("Electrical and Electronics Engineering", "RSET_EEE"),
    ("Applied Electronics and Instrumentation Engineering", "RSET_AEI"),
    ("Information Technology", "RSET_IT"),
    ("Artificial Intelligence and Data Science", "RSET_AD"),
    ("Computer Science and Business Systems", "RSET_CSBS"),
    ("Mechanical Engineering", "RSET_ME"),
    ("Civil Engineering", "RSET_CE"),
    ("Basic Sciences and Humanities", "RSET_BSH"),
]

USERS = [
    ("Arjun Nair", "CSE", "STUDENT"), ("Ananya Menon", "CSE", "FACULTY"),
    ("Rahul Thomas", "CSE", "DEPARTMENT_ADMIN"), ("Neha Joseph", "ECE", "STUDENT"),
    ("Aditya Mathew", "ECE", "FACULTY"), ("Vishnu Raj", "EEE", "STUDENT"),
    ("Meera Krishnan", "EEE", "FACULTY"), ("Ishita George", "AEI", "STUDENT"),
    ("Nikhil Varghese", "AEI", "FACULTY"), ("Akhil Babu", "IT", "STUDENT"),
    ("Diya Suresh", "IT", "FACULTY"), ("Fahad Ali", "AD", "STUDENT"),
    ("Aparna Das", "AD", "FACULTY"), ("Joel Mathew", "CSBS", "STUDENT"),
    ("Riya Paul", "CSBS", "FACULTY"), ("Sanjay Kumar", "ME", "STUDENT"),
    ("Greeshma Ravi", "ME", "FACULTY"), ("Thomas Kurian", "CE", "STUDENT"),
    ("Lakshmi Hari", "CE", "FACULTY"), ("Maya Joseph", "BSH", "ADMIN"),
]

RESOURCES = [
    ("CSE", "Heisenberg Lab", "COMPUTER_LAB", "Academic Block", 36, "High-use computing laboratory; synthetic demo inventory."),
    ("CSE", "Central Computing Facility", "COMPUTER_LAB", "Academic Block", 80, "Shared campus computing facility; synthetic demo inventory."),
    ("CSE", "Zuse Lab", "COMPUTER_LAB", "Academic Block", 30, "Computing laboratory modeled after a publicly documented RSET facility name."),
    ("CSE", "Codd Lab", "COMPUTER_LAB", "Academic Block", 30, "Database and systems laboratory; synthetic demo inventory."),
    ("CSE", "SUNYA HPC Lab", "COMPUTER_LAB", "Academic Block", 24, "HPC demonstration resource; synthetic demo inventory."),
    ("ECE", "Signal Processing Lab", "LAB", "Engineering Block", 28, "Signal processing teaching laboratory; synthetic demo inventory."),
    ("ECE", "Signals and Systems Lab", "LAB", "Engineering Block", 28, "Signals and systems teaching laboratory; synthetic demo inventory."),
    ("ECE", "Logic Design Lab", "LAB", "Engineering Block", 28, "Logic design laboratory; synthetic demo inventory."),
    ("ECE", "Basic Electronics Lab", "LAB", "Engineering Block", 28, "Basic electronics laboratory; synthetic demo inventory."),
    ("ECE", "Communication Lab", "LAB", "Engineering Block", 24, "Communication systems laboratory; synthetic demo inventory."),
    ("ECE", "Embedded Systems Lab", "LAB", "Engineering Block", 24, "Embedded systems laboratory; synthetic demo inventory."),
    ("ECE", "Shannon Lab", "LAB", "Engineering Block", 24, "Communications research-style laboratory; synthetic demo inventory."),
    ("EEE", "Circuits and Measurements Lab", "LAB", "Electrical Block", 28, "Circuits and measurement laboratory; synthetic demo inventory."),
    ("EEE", "Electrical Machines Lab", "LAB", "Electrical Block", 24, "Electrical machines laboratory; synthetic demo inventory."),
    ("EEE", "Power Electronics Lab", "LAB", "Electrical Block", 24, "Power electronics laboratory; synthetic demo inventory."),
    ("AEI", "Measurements Lab", "LAB", "Instrumentation Block", 24, "Instrumentation measurements laboratory; synthetic demo inventory."),
    ("AEI", "Microprocessor Lab", "LAB", "Instrumentation Block", 24, "Microprocessor laboratory; synthetic demo inventory."),
    ("AEI", "Process Control Lab", "LAB", "Instrumentation Block", 24, "Process control laboratory; synthetic demo inventory."),
    ("IT", "Quantum Database and Project Lab", "COMPUTER_LAB", "IT Block", 36, "Database and project computing lab; synthetic demo inventory."),
    ("IT", "Ulysses Advanced Computing Lab", "COMPUTER_LAB", "IT Block", 36, "Advanced computing laboratory; synthetic demo inventory."),
    ("IT", "Quantum Lab", "COMPUTER_LAB", "IT Block", 30, "Information technology laboratory; synthetic demo inventory."),
    ("AD", "Sycamore Lab", "COMPUTER_LAB", "Innovation Block", 40, "High-use AI and data science laboratory; synthetic demo inventory."),
    ("AD", "KleinRock Lab", "COMPUTER_LAB", "Innovation Block", 32, "AI and data science project laboratory; synthetic demo inventory."),
    ("AD", "Data Science Project Lab", "COMPUTER_LAB", "Innovation Block", 32, "Data science project resource; synthetic demo inventory."),
    ("CSBS", "Sycamore Shared Computing Lab", "COMPUTER_LAB", "Innovation Block", 32, "Shared computing resource; synthetic demo inventory."),
    ("ME", "CAD Lab", "COMPUTER_LAB", "Mechanical Block", 30, "Computer-aided design laboratory; synthetic demo inventory."),
    ("ME", "Machine Tool Lab", "WORKSHOP", "Mechanical Block", 24, "Machine tools teaching facility; synthetic demo inventory."),
    ("ME", "Heat Engines Lab", "LAB", "Mechanical Block", 24, "Heat engines laboratory; synthetic demo inventory."),
    ("ME", "Project Laboratory", "LAB", "Mechanical Block", 20, "Mechanical project laboratory; synthetic demo inventory."),
    ("CE", "Surveying Laboratory", "LAB", "Civil Block", 24, "Civil surveying laboratory; synthetic demo inventory."),
    ("CE", "Material Testing Laboratory", "LAB", "Civil Block", 24, "Civil materials testing laboratory; synthetic demo inventory."),
    ("BSH", "Engineering Chemistry Lab", "LAB", "Science Block", 32, "Engineering chemistry laboratory; synthetic demo inventory."),
    ("BSH", "Engineering Physics Lab", "LAB", "Science Block", 32, "Engineering physics laboratory; synthetic demo inventory."),
    ("BSH", "Language Lab", "FACILITY", "Academic Block", 30, "Language learning facility; synthetic demo inventory."),
    ("BSH", "Chavara Hall", "AUDITORIUM", "Main Campus", 220, "Institutional hall name modeled from public RSET information; capacity is synthetic."),
    ("BSH", "Conference Room", "MEETING_ROOM", "Main Campus", 18, "Meeting facility; synthetic demonstration capacity."),
]

SUPPLIERS = [
    ("Campus Systems Supply", "demo-campus-systems@example.invalid"),
    ("Laboratory Instruments Supply", "demo-lab-instruments@example.invalid"),
    ("Network Equipment Supply", "demo-network@example.invalid"),
    ("Workshop Equipment Supply", "demo-workshop@example.invalid"),
    ("Campus Sensor Supply", "demo-sensors@example.invalid"),
    ("Computing Equipment Supply", "demo-computing@example.invalid"),
]

HIGH_RESOURCES = {"Heisenberg Lab", "Central Computing Facility", "Sycamore Lab"}
LOW_RESOURCES = {"Zuse Lab", "Codd Lab", "Project Laboratory", "Machine Tool Lab"}
MAINTENANCE_RESOURCE_NAMES = {"Central Computing Facility", "Signal Processing Lab", "Machine Tool Lab", "Sycamore Lab"}


def execute(connection, query, parameters=()):
    cursor = connection.cursor()
    cursor.execute(query, parameters)
    return cursor


def reset_demo_data(connection):
    """Delete only records marked by this script, in foreign-key order."""
    execute(connection, "DELETE FROM predictions WHERE resource_id IN (SELECT id FROM resources WHERE description LIKE %s)", (f"{DEMO_PREFIX}%",))
    execute(connection, "DELETE FROM sharing_requests WHERE reason LIKE %s", (f"{DEMO_PREFIX}%",))
    execute(connection, "DELETE FROM sensor_readings WHERE resource_id IN (SELECT id FROM resources WHERE description LIKE %s)", (f"{DEMO_PREFIX}%",))
    execute(connection, "DELETE FROM maintenance_records WHERE notes LIKE %s", (f"{DEMO_PREFIX}%",))
    execute(connection, "DELETE FROM usage_records WHERE source = %s", (DEMO_SOURCE,))
    execute(connection, "DELETE FROM bookings WHERE purpose LIKE %s", (f"{DEMO_PREFIX}%",))
    execute(connection, "DELETE FROM purchases WHERE procurement_notes LIKE %s", (f"{DEMO_PREFIX}%",))
    execute(connection, "DELETE FROM resources WHERE description LIKE %s", (f"{DEMO_PREFIX}%",))
    execute(connection, "DELETE FROM users WHERE email LIKE %s", (f"{DEMO_EMAIL_PREFIX}%",))
    execute(connection, "DELETE FROM suppliers WHERE email LIKE %s", ("demo-%@example.invalid",))
    execute(connection, "DELETE FROM departments WHERE code LIKE %s", (f"{DEMO_CODE_PREFIX}%",))


def seed_departments(connection):
    result = {}
    for name, code in DEPARTMENTS:
        cursor = execute(connection, "INSERT INTO departments (name, code) VALUES (%s, %s)", (name, f"{DEMO_DEPARTMENT_PREFIX}{code.removeprefix('RSET_')}"))
        result[code.replace("RSET_", "")] = cursor.lastrowid
    return result


def seed_users(connection, departments):
    result = []
    for index, (name, department_code, role) in enumerate(USERS, start=1):
        email = f"{DEMO_EMAIL_PREFIX}{index}@example.invalid"
        cursor = execute(connection, "INSERT INTO users (department_id, full_name, email, role) VALUES (%s, %s, %s, %s)", (departments[department_code], name, email, role))
        result.append(cursor.lastrowid)
    return result


def seed_resources(connection, departments):
    result = {}
    for department_code, name, resource_type, location, capacity, description in RESOURCES:
        cursor = execute(connection, """INSERT INTO resources
            (department_id, name, resource_type, location, capacity, status, description)
            VALUES (%s, %s, %s, %s, %s, 'AVAILABLE', %s)""", (departments[department_code], name, resource_type, location, capacity, f"{DEMO_PREFIX} {description}"))
        result[name] = {"id": cursor.lastrowid, "department_id": departments[department_code], "resource_type": resource_type, "capacity": capacity}
    return result


def seed_bookings_and_usage(connection, resources, users, departments):
    booking_ids = []
    usage_count = 0
    booking_counter = 0
    start_week = date.today() - timedelta(weeks=7)
    resource_items = list(resources.items())[:31]
    for week in range(7):
        for resource_index, (resource_name, resource) in enumerate(resource_items):
            booking_counter += 1
            day = start_week + timedelta(weeks=week, days=resource_index % 5)
            start = datetime.combine(day, time(8 + (resource_index % 4) * 2, 30))
            if resource_name in HIGH_RESOURCES:
                duration = 2.0 + week * 0.25
            elif resource_name in LOW_RESOURCES:
                duration = max(0.5, 2.5 - week * 0.3)
            else:
                duration = 1.5 + (resource_index % 3) * 0.25
            end = start + timedelta(hours=duration)
            status = "COMPLETED"
            if week == 6 and resource_index % 11 == 0:
                status = "PENDING"
            elif week == 6 and resource_index % 13 == 0:
                status = "APPROVED"
            elif booking_counter % 19 == 0:
                status = "CANCELLED"
            elif booking_counter % 17 == 0:
                status = "NO_SHOW"
            purpose = f"{DEMO_PREFIX} {resource_name} academic demonstration"
            cursor = execute(connection, """INSERT INTO bookings
                (resource_id, user_id, department_id, start_time, end_time, purpose, status, expected_occupancy)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", (resource["id"], users[resource_index % len(users)], resource["department_id"], start, end, purpose, status, max(1, int(resource["capacity"] * 0.55))))
            booking_id = cursor.lastrowid
            booking_ids.append((booking_id, resource_name, resource, start, end, status, duration))
            if status in ("CANCELLED", "NO_SHOW", "PENDING") or booking_counter % 17 == 0:
                continue
            if resource_name in HIGH_RESOURCES:
                actual_minutes = int(duration * 60 * 0.92)
            elif resource_name in LOW_RESOURCES:
                actual_minutes = int(duration * 60 * 0.32)
            else:
                actual_minutes = int(duration * 60 * 0.68)
            actual_start = start + timedelta(minutes=5)
            actual_end = actual_start + timedelta(minutes=max(10, actual_minutes))
            planned_minutes = int(duration * 60)
            actual_minutes = int((actual_end - actual_start).total_seconds() / 60)
            execute(connection, """INSERT INTO usage_records
                (booking_id, resource_id, planned_start_time, planned_end_time,
                 actual_start_time, actual_end_time, planned_duration_minutes,
                 actual_duration_minutes, actual_occupancy, capacity_at_usage,
                 idle_time_minutes, is_phantom_booking, usage_status, source, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, 'COMPLETED', %s, %s)""", (booking_id, resource["id"], start, end, actual_start, actual_end, planned_minutes, actual_minutes, max(1, int(resource["capacity"] * 0.45)), resource["capacity"], max(0, planned_minutes - actual_minutes), DEMO_SOURCE, f"{DEMO_PREFIX} synthetic actual usage"))
            usage_count += 1
    # Three recent, easy-to-find demonstration bookings.
    visible = [("Central Computing Facility", "Data Structures Lab", 9), ("Signal Processing Lab", "Digital Signal Processing Practical", 10), ("Sycamore Lab", "Machine Learning Lab", 14)]
    for index, (name, purpose, hour) in enumerate(visible):
        resource = resources[name]
        start = datetime.combine(date.today() + timedelta(days=index + 1), time(hour, 0))
        end = start + timedelta(hours=2)
        cursor = execute(connection, """INSERT INTO bookings
            (resource_id, user_id, department_id, start_time, end_time, purpose, status, expected_occupancy)
            VALUES (%s, %s, %s, %s, %s, %s, 'APPROVED', %s)""", (resource["id"], users[index], resource["department_id"], start, end, f"{DEMO_PREFIX} {purpose}", 20))
        booking_id = cursor.lastrowid
        execute(connection, """INSERT INTO usage_records
            (booking_id, resource_id, planned_start_time, planned_end_time, actual_start_time,
             actual_end_time, planned_duration_minutes, actual_duration_minutes, actual_occupancy,
             capacity_at_usage, idle_time_minutes, usage_status, source, notes)
            VALUES (%s, %s, %s, %s, %s, %s, 120, 105, 18, %s, 15, 'COMPLETED', %s, %s)""", (booking_id, resource["id"], start, end, start + timedelta(minutes=5), start + timedelta(minutes=110), resource["capacity"], DEMO_SOURCE, f"{DEMO_PREFIX} visible demonstration usage"))
        usage_count += 1
    return len(booking_ids) + len(visible), usage_count


def seed_suppliers(connection):
    result = []
    for name, email in SUPPLIERS:
        cursor = execute(connection, "INSERT INTO suppliers (name, email) VALUES (%s, %s)", (f"{DEMO_PREFIX} {name}", email))
        result.append(cursor.lastrowid)
    return result


def seed_purchases(connection, resources, departments, suppliers):
    items = [
        ("Desktop Computers", 12, 68000), ("Monitors", 18, 14500), ("Projectors", 5, 52000),
        ("Networking Equipment", 8, 28500), ("Oscilloscopes", 4, 78000), ("Function Generators", 5, 31000),
        ("Electronics Trainer Kits", 12, 18000), ("Laboratory Equipment", 6, 42000),
        ("Workshop Equipment", 4, 95000), ("Sensors", 25, 3600), ("Storage Devices", 20, 7200),
    ]
    department_codes = list(departments)
    resource_values = list(resources.values())
    for index in range(25):
        item, base_quantity, unit_cost = items[index % len(items)]
        quantity = max(1, base_quantity - index % 4)
        department_id = departments[department_codes[index % len(department_codes)]]
        resource = resource_values[index % len(resource_values)]
        status = "CANCELLED" if index in (8, 21) else "RECEIVED"
        purchase_date = date.today() - timedelta(days=15 * (index + 1))
        execute(connection, """INSERT INTO purchases
            (resource_id, supplier_id, department_id, item_name, quantity, unit_cost,
             total_cost, purchase_date, purchase_order_number, procurement_notes, purpose, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (resource["id"], suppliers[index % len(suppliers)], department_id, f"{DEMO_PREFIX} {item}", quantity, unit_cost, quantity * unit_cost, purchase_date, None, f"{DEMO_PREFIX} synthetic procurement", "Demonstration procurement analysis", status))
    return 25


def seed_sharing(connection, resources, departments, users):
    resource_list = list(resources.items())
    statuses = ["PENDING", "APPROVED", "REJECTED", "CANCELLED", "COMPLETED"]
    for index in range(20):
        source_name, source = resource_list[index % len(resource_list)]
        requester_department = list(departments.values())[(index + 3) % len(departments)]
        status = statuses[index % len(statuses)]
        approved_by = users[0] if status in ("APPROVED", "COMPLETED") else None
        execute(connection, """INSERT INTO sharing_requests
            (requesting_department_id, requesting_user_id, source_department_id,
             requested_resource_id, requested_resource_type, matched_resource_id,
             requested_quantity, reason, status, approved_by_user_id, approved_at)
            VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s, %s)""", (requester_department, users[(index + 2) % len(users)], source["department_id"], source["id"], source["resource_type"], source["id"], f"{DEMO_PREFIX} cross-department sharing request {index + 1}", status, approved_by, datetime.now() if approved_by else None))
    return 20


def seed_predictions(connection):
    data = get_prediction_data(connection)
    count = 0
    for forecast in data["resources"] + data["types"]:
        if forecast["sufficient"]:
            if store_prediction(connection, forecast):
                count += 1
    return count


def seed_maintenance_and_sensors(connection, resources, users):
    resource_list = list(resources.items())
    maintenance_count = 0
    for index in range(25):
        name, resource = resource_list[index % len(resource_list)]
        status = "IN_PROGRESS" if name in MAINTENANCE_RESOURCE_NAMES and index % 3 == 0 else ("SCHEDULED" if index % 5 == 0 else "COMPLETED")
        reported = datetime.now() - timedelta(days=index + 2)
        completed = None if status in ("IN_PROGRESS", "SCHEDULED") else reported + timedelta(hours=3)
        execute(connection, """INSERT INTO maintenance_records
            (resource_id, technician_user_id, maintenance_type, description, status,
             reported_date, scheduled_date, completed_date, downtime_minutes, cost, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (resource["id"], users[0], "Inspection" if index % 2 else "Repair", f"{DEMO_PREFIX} synthetic maintenance case {index + 1}", status, reported, reported + timedelta(days=1), completed, 45 + index * 5, Decimal("1200.00") + index * 50, f"{DEMO_PREFIX} synthetic maintenance"))
        maintenance_count += 1
        if status in ("IN_PROGRESS", "SCHEDULED"):
            execute(connection, "UPDATE resources SET status = 'MAINTENANCE' WHERE id = %s AND status <> 'RETIRED'", (resource["id"],))
    sensor_count = 0
    for index, (name, resource) in enumerate(resource_list):
        values = [
            ("TEMPERATURE", 65 if name == "Central Computing Facility" else 24 + index % 8, "C"),
            ("VIBRATION", 12 if name == "Machine Tool Lab" else 2 + index % 3, "mm/s"),
            ("BATTERY", 12 if index % 9 == 0 else 80, "%"),
        ]
        for sensor_type, value, unit in values:
            execute(connection, """INSERT INTO sensor_readings
                (resource_id, recorded_at, sensor_type, reading_value, unit)
                VALUES (%s, %s, %s, %s, %s)""", (resource["id"], datetime.now() - timedelta(hours=sensor_count), sensor_type, value, unit))
            sensor_count += 1
    return maintenance_count, sensor_count


def counts(connection):
    tables = ("departments", "users", "resources", "bookings", "usage_records", "suppliers", "purchases", "sharing_requests", "predictions", "maintenance_records", "sensor_readings")
    filters = {
        "departments": ("code LIKE 'RSET_%'", ()),
        "users": ("email LIKE 'rset.demo.%'", ()),
        "resources": ("description LIKE %s", (f"{DEMO_PREFIX}%",)),
        "bookings": ("purpose LIKE %s", (f"{DEMO_PREFIX}%",)),
        "usage_records": ("source = %s", (DEMO_SOURCE,)),
        "suppliers": ("email LIKE 'demo-%@example.invalid'", ()),
        "purchases": ("procurement_notes LIKE %s", (f"{DEMO_PREFIX}%",)),
        "sharing_requests": ("reason LIKE %s", (f"{DEMO_PREFIX}%",)),
        "predictions": ("resource_id IN (SELECT id FROM resources WHERE description LIKE %s)", (f"{DEMO_PREFIX}%",)),
        "maintenance_records": ("notes LIKE %s", (f"{DEMO_PREFIX}%",)),
        "sensor_readings": ("resource_id IN (SELECT id FROM resources WHERE description LIKE %s)", (f"{DEMO_PREFIX}%",)),
    }
    result = {}
    for table in tables:
        where, parameters = filters[table]
        cursor = execute(connection, f"SELECT COUNT(*) FROM {table} WHERE {where}", parameters)
        result[table] = cursor.fetchone()[0]
    return result


def main():
    connection = get_db_connection()
    try:
        connection.start_transaction()
        reset_demo_data(connection)
        departments = seed_departments(connection)
        users = seed_users(connection, departments)
        resources = seed_resources(connection, departments)
        suppliers = seed_suppliers(connection)
        booking_count, usage_count = seed_bookings_and_usage(connection, resources, users, departments)
        purchase_count = seed_purchases(connection, resources, departments, suppliers)
        sharing_count = seed_sharing(connection, resources, departments, users)
        maintenance_count, sensor_count = seed_maintenance_and_sensors(connection, resources, users)
        connection.commit()
        prediction_count = seed_predictions(connection)
        connection.commit()
        summary = counts(connection)
        print("Synthetic RSET-modeled CRFOS demo data seeded successfully.")
        print("Operational bookings, usage, procurement, sharing, maintenance, sensor, and prediction records are synthetic demonstration data and are not official RSET institutional records.")
        print(f"Departments: {summary['departments']}")
        print(f"Users: {summary['users']}")
        print(f"Resources: {summary['resources']}")
        print(f"Bookings: {booking_count}")
        print(f"Usage records: {usage_count}")
        print(f"Suppliers: {summary['suppliers']}")
        print(f"Purchases: {purchase_count}")
        print(f"Sharing requests: {sharing_count}")
        print(f"Predictions stored: {prediction_count}")
        print(f"Maintenance records: {maintenance_count}")
        print(f"Sensor readings: {sensor_count}")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
