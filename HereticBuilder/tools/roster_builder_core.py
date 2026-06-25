import sqlite3
from pathlib import Path
from urllib.parse import quote

from roster_builder_catalog import RosterCatalogMixin
from roster_builder_compositions import RosterCompositionMixin
from roster_builder_rosters import RosterMutationMixin
from roster_builder_rules import RosterRulesMixin
from roster_builder_search import RosterSearchMixin
from roster_builder_unit_options import RosterUnitOptionsMixin
from roster_builder_wargear import WargearValidationMixin


class HereticBuilder(
    RosterCatalogMixin,
    RosterMutationMixin,
    RosterUnitOptionsMixin,
    RosterCompositionMixin,
    RosterRulesMixin,
    RosterSearchMixin,
    WargearValidationMixin,
):
    def __init__(self, db_path):
        self.db_path = Path(db_path).resolve()

    def connect(self, readonly=False):
        if readonly:
            uri = f"file:{quote(str(self.db_path))}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        conn.execute("pragma busy_timeout = 3000")
        return conn
