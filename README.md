# HereticSheets

Raw SQLite snapshot for HereticSheets builder research.

## Data

- `data/heretic_sheets.sqlite` - source SQLite snapshot.

## Projects

- `HereticBuilder/` - local viewer and minimal roster builder.

## Verify

```bash
python3 - <<'PY'
import sqlite3

with sqlite3.connect("data/heretic_sheets.sqlite") as conn:
    print(conn.execute("pragma integrity_check").fetchone()[0])
    print(conn.execute("select dataVersion from metadata").fetchone()[0])
PY
```
