"""Deterministic Stage 4 forensic analysis over Stage 3 source records."""

from dataclasses import asdict, dataclass
from datetime import datetime

THRESHOLDS = {"minimum_bookings": 3, "partial_temporal_utilization": .5,
              "low_capacity_utilization": .4, "low_temporal_utilization": .5,
              "high_no_show_rate": .2}

@dataclass
class Finding:
    finding_type: str
    status: str
    severity: str
    evidence: dict
    explanation: str

def _minutes(start, end):
    if not start or not end or end < start: return None
    return (end - start).total_seconds() / 60

def _time(value):
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)

def analyze_resources(resources, bookings, usage_records, start_date=None, end_date=None):
    """Produce traceable reports; no conclusions are made with weak evidence."""
    by_booking = {u.get("booking_id"): u for u in usage_records if u.get("booking_id")}
    reports = []
    for resource in resources:
        rows = [b for b in bookings if b["resource_id"] == resource["id"] and b.get("status") != "CANCELLED" and (not start_date or _time(b["start_time"]).date() >= start_date) and (not end_date or _time(b["start_time"]).date() <= end_date)]
        planned = actual = unused = 0; no_shows = partials = completed = 0; occupancy = []
        for booking in rows:
            usage = by_booking.get(booking["id"])
            if booking.get("status") == "NO_SHOW" or usage and usage.get("usage_status") == "NO_SHOW": no_shows += 1; continue
            if not usage: continue
            pm = _minutes(_time(booking["start_time"]), _time(booking["end_time"])); am = _minutes(usage.get("actual_start_time"), usage.get("actual_end_time"))
            if pm is None or am is None: continue
            planned += pm; actual += am; unused += max(0, pm-am); completed += 1
            partials += am / pm < THRESHOLDS["partial_temporal_utilization"]
            if usage.get("actual_occupancy") is not None: occupancy.append(usage["actual_occupancy"])
        count = len(rows); temporal = actual/planned if planned else None; average = sum(occupancy)/len(occupancy) if occupancy else None
        capacity_utilization = average/resource["capacity"] if resource.get("capacity") and average is not None else None
        metrics = {"booking_count":count,"completed_usage_count":completed,"no_show_count":no_shows,"planned_minutes":planned,"actual_minutes":actual,"unused_minutes":unused,"temporal_utilization":temporal,"average_occupancy":average,"capacity_utilization":capacity_utilization,"no_show_rate":no_shows/count if count else None}
        findings=[]
        if count < THRESHOLDS["minimum_bookings"] or not completed:
            findings.append(Finding("INSUFFICIENT_DATA","INSUFFICIENT_DATA","LOW",{"booking_count":count,"usage_records":completed},"Insufficient completed usage observations for a reliable conclusion."))
        else:
            if metrics["no_show_rate"] >= THRESHOLDS["high_no_show_rate"]: findings.append(Finding("NO_SHOW_RATE","OBSERVED","HIGH",{"bookings":count,"no_shows":no_shows,"rate":metrics["no_show_rate"]},"No-shows exceed the configured evidence threshold."))
            if partials >= THRESHOLDS["minimum_bookings"]: findings.append(Finding("PARTIAL_USAGE","RECURRING","HIGH",{"partial_events":partials,"bookings":count},"Repeated bookings used substantially less time than planned."))
            if capacity_utilization is not None and capacity_utilization < THRESHOLDS["low_capacity_utilization"]: findings.append(Finding("LOW_CAPACITY_UTILIZATION","OBSERVED","MEDIUM",{"capacity":resource["capacity"],"average_occupancy":average,"utilization":capacity_utilization},"Average occupancy is substantially below capacity."))
            if temporal is not None and temporal < THRESHOLDS["low_temporal_utilization"]: findings.append(Finding("REPEATED_UNDERUTILIZATION","OBSERVED","HIGH",{"temporal_utilization":temporal,"unused_minutes":unused,"bookings":count},"Repeated evidence shows a high share of booked time was unused."))
        reports.append({"resource":resource,"metrics":metrics,"findings":[asdict(f) for f in findings]})
    return reports


# Unified analytics foundation for the future Stage 10 dashboard and decision support.
def get_resource_metrics(connection):
    """Return inventory counts from the existing resources and departments tables."""
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """SELECT COUNT(*) AS total_resources,
                  SUM(status <> 'RETIRED') AS active_resources,
                  SUM(status = 'RETIRED') AS retired_resources,
                  SUM(status = 'MAINTENANCE') AS maintenance_resources,
                  COUNT(DISTINCT resource_type) AS resource_types,
                  COUNT(DISTINCT department_id) AS represented_departments
           FROM resources"""
    )
    row = cursor.fetchone()
    return {key: int(value or 0) for key, value in row.items()}


def get_utilization_metrics(connection):
    """Aggregate the established Black Box planned-versus-actual metrics."""
    from services.blackbox import get_forensic_reports

    reports = get_forensic_reports(connection)
    planned = sum(report["metrics"]["planned_minutes"] for report in reports)
    actual = sum(report["metrics"]["actual_minutes"] for report in reports)
    utilization_values = [
        report["metrics"]["utilization"]
        for report in reports
        if report["metrics"]["utilization"] is not None
    ]
    return {
        "resources_with_usage": sum(report["metrics"]["usage_count"] > 0 for report in reports),
        "average_utilization": sum(utilization_values) / len(utilization_values) if utilization_values else None,
        "underutilized_resources": sum(report["metrics"]["underutilized"] for report in reports),
        "highly_utilized_resources": sum(
            report["metrics"]["utilization"] is not None and report["metrics"]["utilization"] >= 80
            for report in reports
        ),
        "total_planned_hours": planned / 60,
        "total_actual_hours": actual / 60,
        "total_idle_hours": sum(report["metrics"]["idle_minutes"] for report in reports) / 60,
    }


def get_booking_metrics(connection):
    """Return booking counts and hours, with phantom counts from Black Box reports."""
    from services.blackbox import get_forensic_reports

    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """SELECT status, COUNT(*) AS count,
                  COALESCE(SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time)), 0) AS minutes
           FROM bookings GROUP BY status"""
    )
    by_status = {row["status"]: row for row in cursor.fetchall()}
    reports = get_forensic_reports(connection)
    status_counts = {status: int(by_status.get(status, {}).get("count", 0)) for status in (
        "PENDING", "APPROVED", "CANCELLED", "COMPLETED", "NO_SHOW"
    )}
    return {
        "total_bookings": sum(status_counts.values()),
        "pending_bookings": status_counts["PENDING"],
        "approved_bookings": status_counts["APPROVED"],
        "cancelled_bookings": status_counts["CANCELLED"],
        "no_show_bookings": status_counts["NO_SHOW"],
        "phantom_bookings": sum(report["metrics"]["phantom_count"] for report in reports),
        "booking_hours": sum(row.get("minutes", 0) or 0 for row in by_status.values()) / 60,
    }


def get_cost_metrics(connection):
    """Reuse RCOS summary and expenditure grouping results."""
    from services.cost import get_cost_analysis, get_cost_summary

    summary = get_cost_summary(connection)
    analysis = get_cost_analysis(connection)
    return {
        "total_expenditure": summary["total_expenditure"],
        "current_expenditure": summary["current_expenditure"],
        "purchase_count": summary["purchase_count"],
        "average_unit_cost": summary["average_unit_cost"],
        "expenditure_by_department": analysis["by_department"],
        "expenditure_by_item": analysis["by_item"],
    }


def get_sharing_metrics(connection):
    """Reuse the existing sharing status summary and candidate filter."""
    from services.sharing import get_sharing_candidates, get_sharing_summary

    summary = get_sharing_summary(connection)
    return {
        "total_requests": sum(summary.get(status.lower(), 0) for status in (
            "PENDING", "APPROVED", "REJECTED", "CANCELLED", "COMPLETED"
        )),
        "pending_requests": summary["pending"],
        "approved_requests": summary["approved"],
        "rejected_requests": summary["rejected"],
        "cancelled_requests": summary["cancelled"],
        "completed_requests": summary["completed"],
        "available_sharing_candidates": len(get_sharing_candidates(connection)),
    }


def get_demand_metrics(connection):
    """Reuse prediction classifications and trends without recalculating them."""
    from services.prediction import get_prediction_data

    data = get_prediction_data(connection)
    resources = data["resources"]
    return {
        "resources_with_predictions": sum(forecast["sufficient"] for forecast in resources),
        "high_demand_resources": sum(forecast["classification"] == "HIGH DEMAND" for forecast in resources),
        "moderate_demand_resources": sum(forecast["classification"] == "MODERATE DEMAND" for forecast in resources),
        "low_demand_resources": sum(forecast["classification"] == "LOW DEMAND" for forecast in resources),
        "insufficient_prediction_resources": sum(not forecast["sufficient"] for forecast in resources),
        "increasing_demand_resources": sum(forecast["trend"] == "Increasing" for forecast in resources),
        "decreasing_demand_resources": sum(forecast["trend"] == "Decreasing" for forecast in resources),
        "stable_demand_resources": sum(forecast["trend"] == "Stable" for forecast in resources),
    }


def get_maintenance_metrics(connection):
    """Reuse maintenance attention and sensor classification helpers."""
    from services.maintenance import get_maintenance_analysis, get_maintenance_summary

    summary = get_maintenance_summary(connection)
    analysis = get_maintenance_analysis(connection)
    return {
        "total_maintenance_records": int(summary["total"] or 0),
        "open_maintenance_cases": int(summary["open_cases"] or 0),
        "completed_maintenance_cases": int(summary["completed"] or 0),
        "resources_under_maintenance": int(summary["under_maintenance"] or 0),
        "resources_requiring_attention": len(analysis["attention"]),
        "high_attention_resources": sum(report["attention_level"] == "HIGH" for report in analysis["attention"]),
        "recent_abnormal_sensor_readings": len(analysis["alerts"]),
        "repeated_maintenance_resources": len(analysis["repeated"]),
    }


def get_resource_profile(connection, resource_id):
    """Build one cross-module, evidence-only profile for a resource."""
    from services.blackbox import get_forensic_reports
    from services.cost import get_purchase_rows
    from services.maintenance import get_resource_maintenance_report
    from services.prediction import get_resource_forecast

    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """SELECT r.id, r.name, r.resource_type, r.location, r.status,
                  r.capacity, d.name AS department_name
           FROM resources r LEFT JOIN departments d ON d.id = r.department_id
           WHERE r.id = %s""",
        (resource_id,),
    )
    resource = cursor.fetchone()
    if not resource:
        return None

    reports = get_forensic_reports(connection, resource_id=resource_id)
    report = reports[0] if reports else None
    cursor.execute(
        """SELECT status, COUNT(*) AS count,
                  COALESCE(SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time)), 0) AS minutes
           FROM bookings WHERE resource_id = %s GROUP BY status""",
        (resource_id,),
    )
    booking_rows = cursor.fetchall()
    bookings = {row["status"]: row for row in booking_rows}
    purchases = get_purchase_rows(connection, {"q": resource["name"]})
    cursor.execute(
        """SELECT sr.status, COUNT(*) AS count FROM sharing_requests sr
           WHERE sr.requested_resource_id = %s OR sr.matched_resource_id = %s
           GROUP BY sr.status""",
        (resource_id, resource_id),
    )
    sharing = {row["status"]: row["count"] for row in cursor.fetchall()}
    forecast = get_resource_forecast(connection, resource_id)
    maintenance = get_resource_maintenance_report(connection, resource_id)
    flags = []
    if report and report["metrics"]["underutilized"]:
        flags.append("UNDERUTILIZED")
    if report and report["metrics"]["utilization"] is not None and report["metrics"]["utilization"] >= 80:
        flags.append("HIGH_UTILIZATION")
    if forecast and forecast["classification"] == "HIGH DEMAND":
        flags.append("HIGH_DEMAND")
    if forecast and forecast["classification"] == "LOW DEMAND":
        flags.append("LOW_DEMAND")
    if maintenance and maintenance["attention_level"] != "NORMAL":
        flags.append("MAINTENANCE_ATTENTION")
    if resource["status"] == "MAINTENANCE":
        flags.append("UNDER_MAINTENANCE")
    if resource["status"] == "AVAILABLE" and report and report["metrics"]["underutilized"]:
        flags.append("SHARING_OPPORTUNITY")
    utilization_summary = None
    if report:
        utilization_summary = {
            "planned_hours": report["metrics"]["planned_minutes"] / 60,
            "actual_hours": report["metrics"]["actual_minutes"] / 60,
            "idle_hours": report["metrics"]["idle_minutes"] / 60,
            "utilization": report["metrics"]["utilization"],
            "underutilized": report["metrics"]["underutilized"],
        }
    return {
        "resource": resource,
        "utilization": utilization_summary,
        "booking": {
            "booking_count": sum(row["count"] for row in booking_rows),
            "booking_hours": sum(row["minutes"] for row in booking_rows) / 60,
            "cancellations": bookings.get("CANCELLED", {}).get("count", 0),
            "phantom_count": report["metrics"]["phantom_count"] if report else 0,
        },
        "cost": {"purchase_count": len(purchases), "total_expenditure": sum((purchase["total_cost"] for purchase in purchases), 0)},
        "sharing": sharing,
        "demand": forecast,
        "maintenance": maintenance,
        "flags": flags,
    }


def get_system_attention_items(connection):
    """Return structured evidence items for a future dashboard, not recommendations."""
    from services.blackbox import get_forensic_reports
    from services.maintenance import get_maintenance_analysis
    from services.prediction import get_prediction_data

    items = []
    for report in get_forensic_reports(connection):
        resource = report["resource"]
        metrics = report["metrics"]
        if metrics["underutilized"]:
            items.append({"type": "UNDERUTILIZED", "resource_id": resource["id"], "resource_name": resource["name"], "severity": "MEDIUM", "reason": f"Utilization is {metrics['utilization']:.1f}%"})
        if metrics["utilization"] is not None and metrics["utilization"] >= 80:
            items.append({"type": "HIGH_UTILIZATION", "resource_id": resource["id"], "resource_name": resource["name"], "severity": "MEDIUM", "reason": f"Utilization is {metrics['utilization']:.1f}%"})
    for report in get_maintenance_analysis(connection)["attention"]:
        items.append({"type": "MAINTENANCE_ATTENTION", "resource_id": report["resource"]["id"], "resource_name": report["resource"]["name"], "severity": report["attention_level"], "reason": " ".join(report["reasons"])})
    for forecast in get_prediction_data(connection)["resources"]:
        if forecast["classification"] == "HIGH DEMAND":
            items.append({"type": "HIGH_DEMAND", "resource_id": forecast["resource"]["id"], "resource_name": forecast["resource"]["name"], "severity": "MEDIUM", "reason": f"Predicted demand is {forecast['predicted_demand']:.1f} booking-hours"})
    return items


def get_resource_overview(connection, limit=20):
    """Return a bounded list of cross-module resource profiles for the dashboard."""
    cursor = connection.cursor()
    cursor.execute("SELECT id FROM resources ORDER BY name LIMIT %s", (int(limit),))
    return [profile for row in cursor.fetchall() if (profile := get_resource_profile(connection, row[0]))]


def get_unified_analytics(connection):
    """Return all read-only metric groups for future Stage 10 consumers."""
    return {
        "resources": get_resource_metrics(connection),
        "utilization": get_utilization_metrics(connection),
        "bookings": get_booking_metrics(connection),
        "cost": get_cost_metrics(connection),
        "sharing": get_sharing_metrics(connection),
        "demand": get_demand_metrics(connection),
        "maintenance": get_maintenance_metrics(connection),
        "attention_items": get_system_attention_items(connection),
        "resource_overview": get_resource_overview(connection),
    }
