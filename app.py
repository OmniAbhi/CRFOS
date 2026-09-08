from flask import Flask, render_template
from mysql.connector import Error

from config import Config
from analytics import get_unified_analytics
from database import DatabaseConnectionError, get_db_connection
from recommendations import get_recommendations_from_analytics
from routes import stage3


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.register_blueprint(stage3)

    @app.route("/")
    def home():
        unified_analytics = None
        recommendations = []
        try:
            connection = get_db_connection()
            unified_analytics = get_unified_analytics(connection)
            recommendations = get_recommendations_from_analytics(unified_analytics)
            connection.close()
        except (DatabaseConnectionError, Error):
            pass
        return render_template("dashboard.html", analytics=unified_analytics, recommendations=recommendations)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
