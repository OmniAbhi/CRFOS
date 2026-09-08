"""Environment-backed configuration for the CRFOS application."""

import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    """Expose configuration without storing secrets in source control."""

    # A local random fallback keeps non-database pages usable before .env is configured.
    # Deployments should always provide a stable SECRET_KEY through the environment.
    SECRET_KEY = os.getenv("SECRET_KEY") or os.urandom(32)
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME")
