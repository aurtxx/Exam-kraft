from config.settings import *
from pathlib import Path

DATABASES["default"]["NAME"] = Path(__file__).with_name("zen-audit.sqlite3")
