"""Deterministic, evidence-based CRFOS recommendations.

Recommendations are advisory only. They never write to the database or trigger
procurement, booking, sharing, or maintenance actions.
"""

from analytics import get_unified_analytics


HIGH_UTILIZATION_THRESHOLD = 80


def _evidence(*items):
    return [item for item in items if item]


def _recommendation(rec_type, priority, profile, title, action, reason, evidence, module):
    return {
        "type": rec_type,
        "priority": priority,
        "resource_id": profile["resource"]["id"],
        "resource_name": profile["resource"]["name"],
        "title": title,
        "action": action,
        "reason": reason,
        "evidence": evidence,
        "related_module": module,
    }


def _similar_candidates(profile, profiles):
    resource = profile["resource"]
    return [
        candidate for candidate in profiles
        if candidate["resource"]["id"] != resource["id"]
        and candidate["resource"]["resource_type"] == resource["resource_type"]
        and candidate["resource"]["status"] == "AVAILABLE"
        and candidate["resource"].get("department_name") != resource.get("department_name")
        and candidate.get("utilization")
        and candidate["utilization"].get("underutilized")
    ]


def get_recommendations_from_analytics(analytics):
    """Generate current recommendations from an already-loaded analytics payload."""
    profiles = analytics.get("resource_overview", [])
    recommendations = []
    for profile in profiles:
        resource = profile["resource"]
        if resource["status"] == "RETIRED":
            continue
        utilization = profile.get("utilization")
        demand = profile.get("demand")
        maintenance = profile.get("maintenance")
        similar = _similar_candidates(profile, profiles)
        utilization_value = utilization.get("utilization") if utilization else None
        underutilized = utilization and utilization.get("underutilized")
        high_demand = demand and demand.get("classification") == "HIGH DEMAND"
        low_or_moderate_demand = demand and demand.get("classification") in ("LOW DEMAND", "MODERATE DEMAND")
        high_maintenance = maintenance and maintenance.get("attention_level") == "HIGH"
        under_maintenance = resource["status"] == "MAINTENANCE"

        if high_demand and utilization_value is not None and utilization_value >= HIGH_UTILIZATION_THRESHOLD:
            recommendations.append(_recommendation(
                "CAPACITY_PRESSURE", "HIGH", profile,
                "Review capacity pressure",
                "Monitor capacity and evaluate redistribution or additional capacity.",
                "Predicted demand is high while current utilization is also high.",
                _evidence(
                    f"Utilization: {utilization_value:.1f}%",
                    f"Predicted demand: {demand['predicted_demand']:.1f} booking-hours",
                    f"Demand trend: {demand['trend']}",
                ),
                "/prediction",
            ))
        elif utilization_value is not None and utilization_value >= HIGH_UTILIZATION_THRESHOLD and not demand:
            recommendations.append(_recommendation(
                "UTILIZATION_REVIEW", "LOW", profile,
                "Review scheduling and capacity utilization",
                "Review scheduling and capacity utilization.",
                "Utilization is very high, but no demand forecast is available.",
                _evidence(f"Utilization: {utilization_value:.1f}%", "Demand prediction: unavailable"),
                "/blackbox",
            ))

        if high_demand and (high_maintenance or under_maintenance):
            maintenance_reason = "The resource is currently under maintenance." if under_maintenance else "Maintenance attention is HIGH."
            recommendations.append(_recommendation(
                "MAINTENANCE_PRIORITY", "HIGH", profile,
                "Prioritize maintenance for high demand",
                "Prioritize maintenance because the resource is expected to experience high demand.",
                f"Predicted demand is high and {maintenance_reason.lower()}",
                _evidence(
                    f"Predicted demand: {demand['predicted_demand']:.1f} booking-hours",
                    f"Demand classification: {demand['classification']}",
                    f"Maintenance attention: {maintenance['attention_level'] if maintenance else 'HIGH'}",
                ),
                "/maintenance",
            ))
        elif high_maintenance:
            recommendations.append(_recommendation(
                "MAINTENANCE_REVIEW", "HIGH", profile,
                "Review maintenance condition",
                "Review maintenance condition and determine whether inspection or maintenance action is required.",
                "Maintenance attention is HIGH based on current maintenance and sensor evidence.",
                _evidence(*maintenance.get("reasons", [])),
                "/maintenance",
            ))

        if underutilized and resource["status"] in ("AVAILABLE", "UNAVAILABLE"):
            if similar:
                recommendations.append(_recommendation(
                    "CONSIDER_SHARING", "MEDIUM", profile,
                    "Consider sharing before procurement",
                    "Consider sharing or redistribution before purchasing additional capacity.",
                    "This resource is underutilized and a suitable active resource exists in another department.",
                    _evidence(
                        f"Utilization: {utilization_value:.1f}%" if utilization_value is not None else None,
                        f"Suitable underutilized resources in other departments: {len(similar)}",
                    ),
                    "/sharing",
                ))
                if analytics.get("cost", {}).get("purchase_count"):
                    recommendations.append(_recommendation(
                        "PROCUREMENT_REVIEW", "MEDIUM", profile,
                        "Review inventory before procurement",
                        "Review existing inventory, utilization, and sharing options before additional procurement.",
                        "Existing underutilized capacity and sharing candidates provide evidence for reviewing additional procurement.",
                        _evidence(
                            f"Utilization: {utilization_value:.1f}%" if utilization_value is not None else None,
                            f"Matching sharing candidates: {len(similar)}",
                            "Existing purchase history is available",
                        ),
                        "/cost",
                    ))
            elif low_or_moderate_demand:
                recommendations.append(_recommendation(
                    "REDISTRIBUTION_OPPORTUNITY", "LOW", profile,
                    "Investigate redistribution opportunity",
                    "Investigate whether this resource can be redistributed or shared.",
                    "The resource is operational, underutilized, and demand is not currently high.",
                    _evidence(
                        f"Utilization: {utilization_value:.1f}%" if utilization_value is not None else None,
                        f"Demand classification: {demand['classification']}",
                    ),
                    "/sharing",
                ))

    unique = {}
    for recommendation in recommendations:
        unique[(recommendation["resource_id"], recommendation["type"])] = recommendation
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return sorted(unique.values(), key=lambda item: (priority_order[item["priority"]], item["resource_name"], item["type"]))


def get_recommendations(connection, analytics=None):
    """Load analytics once and return deterministic recommendations."""
    return get_recommendations_from_analytics(analytics or get_unified_analytics(connection))


def get_resource_recommendations(connection, resource_id, analytics=None):
    return [item for item in get_recommendations(connection, analytics) if item["resource_id"] == resource_id]
