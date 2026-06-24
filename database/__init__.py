# database/__init__.py
from .connection import get_connection
from .querie_ad import fetch_users_from_ad, process_with_dax_rules