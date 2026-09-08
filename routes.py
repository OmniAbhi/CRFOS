"""Stage 3 resource, booking, and actual-usage routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from mysql.connector import Error

from database import DatabaseConnectionError, get_db_connection
from services.blackbox import (
    USAGE_STATUSES,
    create_usage_record,
    get_analysis_data,
    get_forensic_reports,
    get_usage_form_data,
    summarize_reports,
)
from datetime import date, timedelta
from services.booking import BOOKING_STATUSES, ValidationError, create_booking, update_booking
from services.cost import (
    PURCHASE_STATUSES,
    create_purchase,
    get_cost_analysis,
    get_cost_summary,
    get_purchase_details,
    get_purchase_options,
    get_purchase_rows,
    procurement_check,
)
from services.resource import RESOURCE_STATUSES, save_resource
from services.sharing import (
    SHARING_STATUSES,
    create_sharing_request,
    get_request_details,
    get_request_rows,
    get_sharing_candidates,
    get_sharing_summary,
    transition_request,
)
from services.prediction import (
    get_prediction_data,
    get_resource_forecast,
    get_resource_options,
    get_type_forecast,
    store_prediction,
)
from services.maintenance import (
    MAINTENANCE_STATUSES,
    create_maintenance_record,
    create_sensor_reading,
    complete_maintenance_record,
    get_maintenance_analysis,
    get_maintenance_records,
    get_maintenance_summary,
    get_resource_maintenance_report,
    get_resource_options as get_maintenance_resource_options,
    get_sensor_readings,
)
from recommendations import get_recommendations, get_resource_recommendations
from services.ai_explanation import explain_recommendation

stage3 = Blueprint("stage3", __name__)

@stage3.route("/blackbox")
def blackbox_overview():
    try:
        connection = get_db_connection()
        start_date = request.args.get("start_date") or None
        end_date = request.args.get("end_date") or None
        resource_type = request.args.get("resource_type", "").strip()
        reports = get_forensic_reports(connection, start_date=start_date, end_date=end_date, resource_type=resource_type)
        resource_types = query_rows(connection, "SELECT DISTINCT resource_type FROM resources ORDER BY resource_type")
        return render_template(
            "blackbox/dashboard.html",
            reports=reports,
            summary=summarize_reports(reports),
            resource_types=resource_types,
            filters={"start_date": start_date or "", "end_date": end_date or "", "resource_type": resource_type},
        )
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/blackbox/resource/<int:resource_id>")
@stage3.route("/blackbox/resources/<int:resource_id>")
def blackbox_resource(resource_id):
    try:
        connection = get_db_connection()
        report = next(iter(get_forensic_reports(connection, resource_id=resource_id)), None)
        if report is None:
            flash("Resource analysis not found.", "error")
            return redirect(url_for("stage3.blackbox_overview"))
        return render_template("blackbox/resource.html", report=report)
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/blackbox/analysis")
def blackbox_analysis():
    try:
        connection = get_db_connection()
        reports = get_forensic_reports(
            connection,
            start_date=request.args.get("start_date") or None,
            end_date=request.args.get("end_date") or None,
            resource_type=request.args.get("resource_type", "").strip(),
        )
        return render_template("blackbox/analysis.html", reports=reports, analysis=get_analysis_data(reports))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/cost")
def cost_dashboard():
    try:
        connection = get_db_connection()
        summary = get_cost_summary(connection)
        resource_types = query_rows(connection, "SELECT DISTINCT resource_type FROM resources ORDER BY resource_type")
        procurement = None
        resource_type = request.args.get("resource_type", "").strip()
        quantity_value = request.args.get("requested_quantity", "1").strip()
        if resource_type:
            try:
                requested_quantity = int(quantity_value)
                if requested_quantity <= 0:
                    raise ValueError
                procurement = procurement_check(connection, resource_type, requested_quantity)
            except ValueError:
                flash("Requested quantity must be greater than zero.", "error")
        return render_template(
            "cost/dashboard.html",
            summary=summary,
            resource_types=resource_types,
            procurement=procurement,
            filters={"resource_type": resource_type, "requested_quantity": quantity_value},
        )
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/cost/purchases")
def cost_purchases():
    filters = {
        "date": request.args.get("date", "").strip(),
        "department_id": request.args.get("department_id", "").strip(),
        "supplier_id": request.args.get("supplier_id", "").strip(),
        "q": request.args.get("q", "").strip(),
    }
    try:
        connection = get_db_connection()
        purchases = get_purchase_rows(connection, filters)
        _, suppliers, departments = get_purchase_options(connection)
        return render_template("cost/purchases.html", purchases=purchases, suppliers=suppliers, departments=departments, filters=filters)
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/cost/purchases/create", methods=["GET", "POST"])
def create_purchase_route():
    try:
        connection = get_db_connection()
        if request.method == "POST":
            try:
                purchase_id = create_purchase(connection, request.form)
                flash("Purchase recorded.", "success")
                return redirect(url_for("stage3.purchase_details", purchase_id=purchase_id))
            except (ValidationError, ValueError) as error:
                flash(str(error), "error")
            except Error:
                connection.rollback()
                flash("The purchase could not be saved.", "error")
        resources, suppliers, departments = get_purchase_options(connection)
        return render_template(
            "cost/purchase_create.html",
            resources=resources,
            suppliers=suppliers,
            departments=departments,
            statuses=PURCHASE_STATUSES,
            form_data=request.form if request.method == "POST" else {},
        )
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/cost/purchases/<int:purchase_id>")
def purchase_details(purchase_id):
    try:
        connection = get_db_connection()
        purchase = get_purchase_details(connection, purchase_id)
        if purchase is None:
            flash("Purchase not found.", "error")
            return redirect(url_for("stage3.cost_purchases"))
        return render_template("cost/purchase_details.html", purchase=purchase)
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/cost/analysis")
def cost_analysis():
    try:
        connection = get_db_connection()
        return render_template("cost/analysis.html", analysis=get_cost_analysis(connection))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/sharing")
def sharing_dashboard():
    try:
        connection = get_db_connection()
        summary = get_sharing_summary(connection)
        candidates = get_sharing_candidates(connection)[:5]
        return render_template("sharing/dashboard.html", summary=summary, candidates=candidates)
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/sharing/resources")
def sharing_resources():
    filters = {
        "q": request.args.get("q", "").strip(),
        "resource_type": request.args.get("resource_type", "").strip(),
        "department_id": request.args.get("department_id", "").strip(),
        "capacity": request.args.get("capacity", "").strip(),
    }
    try:
        connection = get_db_connection()
        candidates = get_sharing_candidates(connection, filters)
        resource_types = query_rows(connection, "SELECT DISTINCT resource_type FROM resources ORDER BY resource_type")
        departments = query_rows(connection, "SELECT id, name FROM departments ORDER BY name")
        return render_template("sharing/resources.html", candidates=candidates, resource_types=resource_types, departments=departments, filters=filters)
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/sharing/requests")
def sharing_requests():
    status = request.args.get("status", "").strip().upper()
    try:
        connection = get_db_connection()
        requests = get_request_rows(connection, status)
        return render_template("sharing/requests.html", requests=requests, statuses=SHARING_STATUSES, selected_status=status)
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/sharing/requests/create", methods=["GET", "POST"])
def create_sharing_request_route():
    try:
        connection = get_db_connection()
        if request.method == "POST":
            try:
                request_id = create_sharing_request(connection, request.form)
                flash("Sharing request created and is pending review.", "success")
                return redirect(url_for("stage3.sharing_request_details", request_id=request_id))
            except (ValidationError, ValueError) as error:
                flash(str(error), "error")
            except Error:
                connection.rollback()
                flash("The sharing request could not be saved.", "error")
        departments = query_rows(connection, "SELECT id, name FROM departments ORDER BY name")
        users = query_rows(connection, "SELECT id, full_name, department_id FROM users WHERE is_active = TRUE ORDER BY full_name")
        candidates = get_sharing_candidates(connection)
        return render_template(
            "sharing/create.html",
            departments=departments,
            users=users,
            candidates=candidates,
            form_data=request.form if request.method == "POST" else {},
        )
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/sharing/requests/<int:request_id>")
def sharing_request_details(request_id):
    try:
        connection = get_db_connection()
        request_row = get_request_details(connection, request_id)
        if request_row is None:
            flash("Sharing request not found.", "error")
            return redirect(url_for("stage3.sharing_requests"))
        return render_template("sharing/details.html", request_row=request_row)
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


def _change_sharing_request(request_id, action):
    try:
        connection = get_db_connection()
        transition_request(connection, request_id, action)
        flash(f"Sharing request {action.lower()}.", "success")
    except (ValidationError, ValueError) as error:
        flash(str(error), "error")
    except DatabaseConnectionError as error:
        flash(str(error), "error")
    except Error:
        if "connection" in locals() and connection.is_connected():
            connection.rollback()
        flash("The sharing request could not be updated.", "error")
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()
    return redirect(url_for("stage3.sharing_request_details", request_id=request_id))


@stage3.route("/sharing/requests/<int:request_id>/approve", methods=["POST"])
def approve_sharing_request(request_id):
    return _change_sharing_request(request_id, "APPROVED")


@stage3.route("/sharing/requests/<int:request_id>/reject", methods=["POST"])
def reject_sharing_request(request_id):
    return _change_sharing_request(request_id, "REJECTED")


@stage3.route("/sharing/requests/<int:request_id>/cancel", methods=["POST"])
def cancel_sharing_request(request_id):
    return _change_sharing_request(request_id, "CANCELLED")


@stage3.route("/sharing/requests/<int:request_id>/complete", methods=["POST"])
def complete_sharing_request(request_id):
    return _change_sharing_request(request_id, "COMPLETED")


@stage3.route("/prediction")
def prediction_dashboard():
    try:
        connection = get_db_connection()
        data = get_prediction_data(connection)
        return render_template("prediction/dashboard.html", data=data)
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/prediction/forecast")
def prediction_forecast():
    try:
        connection = get_db_connection()
        resource_id_value = request.args.get("resource_id", "").strip()
        resource_type = request.args.get("resource_type", "").strip()
        forecast = None
        if resource_id_value:
            try:
                forecast = get_resource_forecast(connection, int(resource_id_value))
            except ValueError:
                flash("Select a valid resource.", "error")
        elif resource_type:
            forecast = get_type_forecast(connection, resource_type)
        if (resource_id_value or resource_type) and forecast is None:
            flash("No forecast is available for that selection.", "error")
        if forecast and forecast["sufficient"]:
            store_prediction(connection, forecast)
        return render_template(
            "prediction/forecast.html",
            forecast=forecast,
            resources=get_resource_options(connection),
            types=sorted({resource["resource_type"] for resource in get_resource_options(connection)}),
            selected_resource=resource_id_value,
            selected_type=resource_type,
        )
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    except Error:
        if "connection" in locals() and connection.is_connected():
            connection.rollback()
        flash("The forecast could not be stored.", "error")
        return redirect(url_for("stage3.prediction_forecast"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/prediction/resource/<int:resource_id>")
def prediction_resource(resource_id):
    try:
        connection = get_db_connection()
        forecast = get_resource_forecast(connection, resource_id)
        if forecast is None:
            flash("Resource forecast not found.", "error")
            return redirect(url_for("stage3.prediction_dashboard"))
        if forecast["sufficient"]:
            store_prediction(connection, forecast)
        return render_template("prediction/forecast.html", forecast=forecast, resources=get_resource_options(connection), types=[], selected_resource=str(resource_id), selected_type="")
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/recommendations", methods=["GET", "POST"])
def recommendations_page():
    priority = request.args.get("priority", "").strip().upper()
    recommendation_type = request.args.get("type", "").strip().upper()
    try:
        connection = get_db_connection()
        recommendations = get_recommendations(connection)
        ai_result = None
        if request.method == "POST":
            try:
                recommendation_id = int(request.form.get("resource_id", ""))
            except ValueError:
                recommendation_id = None
            requested_type = request.form.get("recommendation_type", "")
            target = next(
                (
                    item for item in recommendations
                    if item["resource_id"] == recommendation_id and item["type"] == requested_type
                ),
                None,
            )
            ai_result = explain_recommendation(target) if target else {
                "available": False,
                "message": "AI explanation unavailable for this recommendation.",
            }
        if priority in {"HIGH", "MEDIUM", "LOW"}:
            recommendations = [item for item in recommendations if item["priority"] == priority]
        if recommendation_type:
            recommendations = [item for item in recommendations if item["type"] == recommendation_type]
        types = sorted({item["type"] for item in recommendations})
        return render_template(
            "recommendations/index.html",
            recommendations=recommendations,
            types=types,
            selected_priority=priority,
            selected_type=recommendation_type,
            ai_result=ai_result,
        )
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    except Error:
        flash("Recommendations are temporarily unavailable.", "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/recommendations/<int:resource_id>")
def resource_recommendations(resource_id):
    try:
        connection = get_db_connection()
        resource = query_rows(connection, "SELECT id, name FROM resources WHERE id = %s", (resource_id,))
        if not resource:
            flash("Resource not found.", "error")
            return redirect(url_for("stage3.recommendations_page"))
        return render_template(
            "recommendations/resource.html",
            resource=resource[0],
            recommendations=get_resource_recommendations(connection, resource_id),
        )
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/maintenance")
def maintenance_dashboard():
    try:
        connection = get_db_connection()
        summary = get_maintenance_summary(connection)
        analysis = get_maintenance_analysis(connection)
        return render_template("maintenance/dashboard.html", summary=summary, analysis=analysis)
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/maintenance/records")
def maintenance_records():
    status = request.args.get("status", "").strip().upper()
    try:
        connection = get_db_connection()
        records = get_maintenance_records(connection, status=status)
        return render_template("maintenance/records.html", records=records, statuses=MAINTENANCE_STATUSES, selected_status=status)
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/maintenance/records/create", methods=["GET", "POST"])
def create_maintenance_route():
    try:
        connection = get_db_connection()
        if request.method == "POST":
            try:
                record_id = create_maintenance_record(connection, request.form)
                flash("Maintenance record created.", "success")
                return redirect(url_for("stage3.maintenance_record_details", record_id=record_id))
            except (ValidationError, ValueError) as error:
                flash(str(error), "error")
            except Error:
                connection.rollback()
                flash("The maintenance record could not be saved.", "error")
        resources = get_maintenance_resource_options(connection)
        users = query_rows(connection, "SELECT id, full_name FROM users WHERE is_active = TRUE ORDER BY full_name")
        return render_template("maintenance/create.html", resources=resources, users=users, statuses=MAINTENANCE_STATUSES, form_data=request.form if request.method == "POST" else {})
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/maintenance/records/<int:record_id>")
def maintenance_record_details(record_id):
    try:
        connection = get_db_connection()
        record = next((item for item in get_maintenance_records(connection) if item["id"] == record_id), None)
        if not record:
            flash("Maintenance record not found.", "error")
            return redirect(url_for("stage3.maintenance_records"))
        return render_template("maintenance/record_details.html", record=record)
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/maintenance/records/<int:record_id>/complete", methods=["POST"])
def complete_maintenance_route(record_id):
    try:
        connection = get_db_connection()
        complete_maintenance_record(connection, record_id)
        flash("Maintenance record completed.", "success")
    except (ValidationError, ValueError) as error:
        flash(str(error), "error")
    except DatabaseConnectionError as error:
        flash(str(error), "error")
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()
    return redirect(url_for("stage3.maintenance_record_details", record_id=record_id))


@stage3.route("/maintenance/resource/<int:resource_id>")
def maintenance_resource(resource_id):
    try:
        connection = get_db_connection()
        report = get_resource_maintenance_report(connection, resource_id)
        if report is None:
            flash("Resource maintenance history not found.", "error")
            return redirect(url_for("stage3.maintenance_dashboard"))
        return render_template("maintenance/equipment.html", report=report)
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/maintenance/sensors")
def maintenance_sensors():
    try:
        connection = get_db_connection()
        readings = get_sensor_readings(connection)
        return render_template("maintenance/sensors.html", readings=readings)
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/maintenance/sensors/create", methods=["GET", "POST"])
def create_sensor_route():
    try:
        connection = get_db_connection()
        if request.method == "POST":
            try:
                create_sensor_reading(connection, request.form)
                flash("Sensor reading recorded as demonstration data.", "success")
                return redirect(url_for("stage3.maintenance_sensors"))
            except (ValidationError, ValueError) as error:
                flash(str(error), "error")
        return render_template("maintenance/sensor_create.html", resources=get_maintenance_resource_options(connection), form_data=request.form if request.method == "POST" else {})
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/maintenance/analysis")
def maintenance_analysis():
    try:
        connection = get_db_connection()
        return render_template("maintenance/analysis.html", analysis=get_maintenance_analysis(connection))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


def query_rows(connection, query, parameters=()):
    cursor = connection.cursor(dictionary=True)
    cursor.execute(query, parameters)
    return cursor.fetchall()


def form_options(connection):
    return (
        query_rows(connection, """SELECT id, name, resource_type, location, capacity, status
                                FROM resources WHERE status = 'AVAILABLE' ORDER BY name"""),
        query_rows(connection, "SELECT id, full_name, department_id FROM users WHERE is_active = TRUE ORDER BY full_name"),
        query_rows(connection, "SELECT id, name FROM departments ORDER BY name"),
    )


@stage3.route("/resources")
def resources():
    search = request.args.get("q", "").strip()
    resource_type = request.args.get("resource_type", "").strip()
    status = request.args.get("status", "").strip().upper()
    try:
        connection = get_db_connection()
        filters = []
        parameters = []
        if search:
            filters.append("(r.name LIKE %s OR r.resource_type LIKE %s OR r.location LIKE %s)")
            search_value = f"%{search}%"
            parameters.extend((search_value, search_value, search_value))
        if resource_type:
            filters.append("r.resource_type = %s")
            parameters.append(resource_type)
        if status in RESOURCE_STATUSES:
            filters.append("r.status = %s")
            parameters.append(status)
        where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
        rows = query_rows(
            connection,
            f"""SELECT r.*, d.name AS department_name FROM resources r
                LEFT JOIN departments d ON d.id = r.department_id{where_clause}
                ORDER BY r.name""",
            parameters,
        )
        resource_types = query_rows(connection, "SELECT DISTINCT resource_type FROM resources ORDER BY resource_type")
        return render_template(
            "resources/index.html",
            resources=rows,
            resource_types=resource_types,
            statuses=RESOURCE_STATUSES,
            filters={"q": search, "resource_type": resource_type, "status": status},
        )
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/resources/create", methods=["GET", "POST"])
def create_resource():
    try:
        connection = get_db_connection()
        if request.method == "POST":
            try:
                resource_id = save_resource(connection, request.form)
                flash("Resource created.", "success")
                return redirect(url_for("stage3.resource_details", resource_id=resource_id))
            except (ValidationError, ValueError) as error:
                flash(str(error), "error")
        departments = query_rows(connection, "SELECT id, name FROM departments ORDER BY name")
        form_data = request.form if request.method == "POST" else {}
        return render_template(
            "resources/create.html",
            departments=departments,
            statuses=RESOURCE_STATUSES,
            form_data=form_data,
        )
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/resources/<int:resource_id>")
def resource_details(resource_id):
    try:
        connection = get_db_connection()
        resource = query_rows(
            connection,
            """SELECT r.*, d.name AS department_name FROM resources r
               LEFT JOIN departments d ON d.id = r.department_id
               WHERE r.id = %s""",
            (resource_id,),
        )
        if not resource:
            flash("Resource not found.", "error")
            return redirect(url_for("stage3.resources"))
        return render_template(
            "resources/details.html",
            resource=resource[0],
            recommendations=get_resource_recommendations(connection, resource_id),
        )
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/resources/<int:resource_id>/edit", methods=["GET", "POST"])
def edit_resource(resource_id):
    try:
        connection = get_db_connection()
        resource_rows = query_rows(connection, "SELECT * FROM resources WHERE id = %s", (resource_id,))
        if not resource_rows:
            flash("Resource not found.", "error")
            return redirect(url_for("stage3.resources"))
        resource = resource_rows[0]
        if request.method == "POST":
            try:
                save_resource(connection, request.form, resource_id)
                flash("Resource updated.", "success")
                return redirect(url_for("stage3.resource_details", resource_id=resource_id))
            except (ValidationError, ValueError) as error:
                flash(str(error), "error")
        departments = query_rows(connection, "SELECT id, name FROM departments ORDER BY name")
        return render_template(
            "resources/edit.html",
            resource=resource,
            departments=departments,
            statuses=RESOURCE_STATUSES,
            form_data=request.form if request.method == "POST" else {},
        )
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/resources/<int:resource_id>/deactivate", methods=["POST"])
def deactivate_resource(resource_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("UPDATE resources SET status = 'RETIRED' WHERE id = %s", (resource_id,))
        connection.commit()
        if cursor.rowcount == 0:
            flash("Resource not found.", "error")
        else:
            flash("Resource deactivated.", "success")
        return redirect(url_for("stage3.resource_details", resource_id=resource_id))
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/bookings")
def bookings():
    resource_id = request.args.get("resource_id", "").strip()
    status = request.args.get("status", "").strip().upper()
    booking_date = request.args.get("date", "").strip()
    try:
        connection = get_db_connection()
        filters = []
        parameters = []
        if resource_id.isdigit():
            filters.append("b.resource_id = %s")
            parameters.append(int(resource_id))
        if status in BOOKING_STATUSES:
            filters.append("b.status = %s")
            parameters.append(status)
        if booking_date:
            filters.append("DATE(b.start_time) = %s")
            parameters.append(booking_date)
        where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
        rows = query_rows(
            connection,
            f"""SELECT b.*, r.name AS resource_name, r.resource_type, r.location,
                       u.full_name AS user_name
                FROM bookings b JOIN resources r ON r.id = b.resource_id
                JOIN users u ON u.id = b.user_id{where_clause}
                ORDER BY b.start_time DESC""",
            parameters,
        )
        resources = query_rows(connection, "SELECT id, name FROM resources ORDER BY name")
        return render_template(
            "booking/index.html",
            bookings=rows,
            resources=resources,
            statuses=BOOKING_STATUSES,
            filters={"resource_id": resource_id, "status": status, "date": booking_date},
        )
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/bookings/create", methods=["GET", "POST"])
def create_booking_route():
    try:
        connection = get_db_connection()
        if request.method == "POST":
            try:
                booking_id = create_booking(connection, request.form)
                flash("Planned usage booking created.", "success")
                return redirect(url_for("stage3.booking_details", booking_id=booking_id))
            except (ValidationError, ValueError) as error:
                flash(str(error), "error")
        resources, users, departments = form_options(connection)
        form_data = request.form if request.method == "POST" else request.args
        return render_template(
            "booking/create.html",
            resources=resources,
            users=users,
            departments=departments,
            form_data=form_data,
        )
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/bookings/<int:booking_id>")
def booking_details(booking_id):
    try:
        connection = get_db_connection()
        rows = query_rows(connection, """SELECT b.*, r.name AS resource_name, r.resource_type, r.location,
                                        u.full_name AS user_name, d.name AS department_name
                                 FROM bookings b JOIN resources r ON r.id = b.resource_id
                                 JOIN users u ON u.id = b.user_id LEFT JOIN departments d ON d.id = b.department_id
                                 WHERE b.id = %s""", (booking_id,))
        if not rows:
            flash("Booking not found.", "error")
            return redirect(url_for("stage3.bookings"))
        return render_template("booking/details.html", booking=rows[0])
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/bookings/<int:booking_id>/edit", methods=["GET", "POST"])
def edit_booking(booking_id):
    connection = get_db_connection()
    if request.method == "POST":
        try:
            update_booking(connection, booking_id, request.form)
            flash("Booking updated.", "success")
            return redirect(url_for("stage3.booking_details", booking_id=booking_id))
        except (ValidationError, ValueError) as error:
            flash(str(error), "error")
    rows = query_rows(connection, "SELECT * FROM bookings WHERE id=%s", (booking_id,))
    if not rows:
        connection.close()
        flash("Booking not found.", "error")
        return redirect(url_for("stage3.bookings"))
    resources, users, departments = form_options(connection)
    connection.close()
    return render_template("booking/edit.html", booking=rows[0], resources=resources, users=users, departments=departments)


@stage3.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
def cancel_booking(booking_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("UPDATE bookings SET status='CANCELLED' WHERE id=%s AND status IN ('PENDING','APPROVED')", (booking_id,))
        connection.commit()
        if cursor.rowcount:
            flash("Booking cancelled.", "success")
        else:
            flash("Only pending or approved bookings can be cancelled.", "error")
        return redirect(url_for("stage3.booking_details", booking_id=booking_id))
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("stage3.bookings"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()


@stage3.route("/usage")
def usage_records():
    connection = get_db_connection()
    rows = query_rows(connection, """SELECT ur.*, r.name AS resource_name, b.start_time, b.end_time
                                    FROM usage_records ur JOIN resources r ON r.id=ur.resource_id
                                    LEFT JOIN bookings b ON b.id=ur.booking_id ORDER BY ur.recorded_at DESC""")
    connection.close()
    return render_template("usage/index.html", usage_records=rows)


@stage3.route("/blackbox/usage/create", methods=["GET", "POST"])
@stage3.route("/usage/create", methods=["GET", "POST"])
def create_usage():
    try:
        connection = get_db_connection()
        if request.method == "POST":
            try:
                create_usage_record(connection, request.form)
                flash("Actual usage recorded.", "success")
                return redirect(url_for("stage3.usage_records"))
            except (ValidationError, ValueError) as error:
                flash(str(error), "error")
            except Error:
                connection.rollback()
                flash("The actual usage record could not be saved.", "error")
        bookings = get_usage_form_data(connection)
        return render_template("blackbox/usage_create.html", bookings=bookings, form_data=request.form if request.method == "POST" else {})
    except DatabaseConnectionError as error:
        flash(str(error), "error")
        return redirect(url_for("home"))
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()
