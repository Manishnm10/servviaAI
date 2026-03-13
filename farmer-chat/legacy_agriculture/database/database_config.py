import os, sys
from pathlib import Path
from peewee import PostgresqlDatabase
from playhouse.pool import PooledPostgresqlExtDatabase

# Project root is two levels up from legacy_agriculture/database/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
from django_core.config import Config

# normal DB connection
db_conn = PostgresqlDatabase(
    Config.DB_NAME, user=Config.DB_USER, password=Config.DB_PASSWORD, host=Config.DB_HOST, port=Config.DB_PORT
)

# Pooled DB connection
pooled_db_conn = PooledPostgresqlExtDatabase(
    Config.DB_NAME, user=Config.DB_USER, password=Config.DB_PASSWORD, host=Config.DB_HOST, port=Config.DB_PORT
)
