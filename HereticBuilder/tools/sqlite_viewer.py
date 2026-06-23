#!/usr/bin/env python3
import argparse
import html
import json
import sqlite3
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "heretic_sheets.sqlite"
MAX_LIMIT = 500


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SQLite Viewer</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f8;
      --panel: #ffffff;
      --text: #16191d;
      --muted: #69717c;
      --line: #d9dee5;
      --line-strong: #bcc5cf;
      --accent: #1d6f5f;
      --accent-soft: #d9eee9;
      --danger: #9c2b2b;
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: var(--sans);
      font-size: 14px;
      letter-spacing: 0;
    }

    button, input, select, textarea {
      font: inherit;
    }

    button {
      border: 1px solid var(--line-strong);
      background: #fff;
      color: var(--text);
      min-height: 34px;
      padding: 0 10px;
      border-radius: 6px;
      cursor: pointer;
    }

    button:hover { border-color: #8f9aa7; }
    button:disabled { opacity: .45; cursor: default; }

    input, select, textarea {
      border: 1px solid var(--line-strong);
      background: #fff;
      color: var(--text);
      border-radius: 6px;
      min-height: 34px;
      padding: 7px 9px;
      outline: none;
    }

    input:focus, select:focus, textarea:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 2px rgba(29, 111, 95, .14);
    }

    .app {
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
      height: 100vh;
      min-height: 640px;
    }

    .sidebar {
      display: flex;
      flex-direction: column;
      min-width: 0;
      border-right: 1px solid var(--line);
      background: var(--panel);
    }

    .brand {
      padding: 16px;
      border-bottom: 1px solid var(--line);
    }

    .brand h1 {
      margin: 0 0 5px;
      font-size: 17px;
      font-weight: 700;
      line-height: 1.2;
    }

    .brand .meta {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
      word-break: break-word;
    }

    .table-filter {
      padding: 12px;
      border-bottom: 1px solid var(--line);
    }

    .table-filter input {
      width: 100%;
    }

    .tables {
      overflow: auto;
      padding: 8px;
    }

    .table-item {
      width: 100%;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
      gap: 10px;
      border: 0;
      background: transparent;
      padding: 8px;
      min-height: 36px;
      text-align: left;
      border-radius: 6px;
    }

    .table-item:hover { background: #eef1f3; }
    .table-item.active { background: var(--accent-soft); color: #0c453b; }

    .table-name {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-family: var(--mono);
      font-size: 12px;
    }

    .table-count {
      color: var(--muted);
      font-size: 12px;
      font-variant-numeric: tabular-nums;
    }

    .main {
      min-width: 0;
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr);
      height: 100vh;
    }

    .topbar {
      min-width: 0;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }

    .title {
      min-width: 0;
    }

    .title h2 {
      margin: 0 0 4px;
      font-size: 18px;
      line-height: 1.25;
      font-family: var(--mono);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .title .meta {
      color: var(--muted);
      font-size: 12px;
    }

    .tabs {
      display: flex;
      gap: 4px;
      padding: 8px 16px 0;
      background: var(--panel);
    }

    .tab {
      border: 0;
      border-bottom: 2px solid transparent;
      border-radius: 0;
      background: transparent;
      min-height: 36px;
      padding: 0 12px;
      color: var(--muted);
    }

    .tab.active {
      color: var(--text);
      border-bottom-color: var(--accent);
    }

    .pane {
      min-width: 0;
      min-height: 0;
      display: none;
      padding: 12px 16px 16px;
      overflow: hidden;
    }

    .pane.active {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      gap: 10px;
    }

    .toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-width: 0;
    }

    .toolbar-left, .toolbar-right {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }

    .toolbar input[type="search"] {
      width: min(440px, 42vw);
    }

    .toolbar .status {
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }

    .grid-wrap {
      min-width: 0;
      min-height: 0;
      overflow: auto;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: auto;
      font-size: 12px;
    }

    th, td {
      border-bottom: 1px solid var(--line);
      border-right: 1px solid var(--line);
      padding: 7px 9px;
      max-width: 420px;
      vertical-align: top;
      text-align: left;
    }

    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #eef1f3;
      color: #313942;
      font-weight: 650;
      white-space: nowrap;
    }

    td {
      font-family: var(--mono);
      overflow-wrap: anywhere;
      line-height: 1.35;
    }

    tr:hover td { background: #fafbfc; }
    td.null { color: #9aa3ad; font-style: italic; }

    .schema-grid {
      min-height: 0;
      overflow: auto;
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr);
      gap: 12px;
    }

    .sql-panel {
      display: grid;
      grid-template-rows: minmax(110px, auto) auto minmax(0, 1fr);
      gap: 10px;
      min-height: 0;
    }

    textarea {
      width: 100%;
      min-height: 140px;
      resize: vertical;
      font-family: var(--mono);
      line-height: 1.45;
    }

    pre {
      margin: 0;
      padding: 12px;
      background: #11161a;
      color: #e7ecef;
      border-radius: 8px;
      overflow: auto;
      font-family: var(--mono);
      font-size: 12px;
      line-height: 1.45;
    }

    .empty, .error {
      padding: 18px;
      color: var(--muted);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }

    .error {
      color: var(--danger);
      border-color: #e6b4b4;
      background: #fff5f5;
    }

    @media (max-width: 820px) {
      .app {
        grid-template-columns: 1fr;
        grid-template-rows: 270px minmax(0, 1fr);
      }

      .sidebar {
        border-right: 0;
        border-bottom: 1px solid var(--line);
        min-height: 0;
      }

      .main {
        height: auto;
        min-height: 0;
      }

      .toolbar {
        align-items: stretch;
        flex-direction: column;
      }

      .toolbar-left, .toolbar-right {
        width: 100%;
      }

      .toolbar input[type="search"] {
        width: 100%;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">
        <h1>SQLite Viewer</h1>
        <div class="meta" id="dbMeta">Loading...</div>
      </div>
      <div class="table-filter">
        <input id="tableFilter" type="search" placeholder="Filter tables">
      </div>
      <div id="tableList" class="tables"></div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div class="title">
          <h2 id="tableTitle">No table selected</h2>
          <div id="tableMeta" class="meta"></div>
        </div>
      </header>

      <nav class="tabs">
        <button class="tab active" data-tab="data">Data</button>
        <button class="tab" data-tab="schema">Schema</button>
        <button class="tab" data-tab="sql">SQL</button>
      </nav>

      <section id="dataPane" class="pane active">
        <div class="toolbar">
          <div class="toolbar-left">
            <input id="rowSearch" type="search" placeholder="Search current table">
            <select id="limitSelect">
              <option value="50">50 rows</option>
              <option value="100" selected>100 rows</option>
              <option value="250">250 rows</option>
              <option value="500">500 rows</option>
            </select>
          </div>
          <div class="toolbar-right">
            <span id="pageStatus" class="status"></span>
            <button id="prevPage">Prev</button>
            <button id="nextPage">Next</button>
          </div>
        </div>
        <div id="dataGrid" class="grid-wrap"></div>
      </section>

      <section id="schemaPane" class="pane">
        <div></div>
        <div id="schemaGrid" class="schema-grid"></div>
      </section>

      <section id="sqlPane" class="pane">
        <div class="sql-panel">
          <textarea id="sqlInput" spellcheck="false">select name from sqlite_schema where type = 'table' order by name limit 100;</textarea>
          <div class="toolbar">
            <div class="toolbar-left">
              <button id="runSql">Run</button>
              <select id="sqlLimit">
                <option value="50">50 rows</option>
                <option value="100" selected>100 rows</option>
                <option value="250">250 rows</option>
                <option value="500">500 rows</option>
              </select>
            </div>
            <div id="sqlStatus" class="status"></div>
          </div>
          <div id="sqlGrid" class="grid-wrap"></div>
        </div>
      </section>
    </main>
  </div>

  <script>
    const state = {
      tables: [],
      currentTable: null,
      offset: 0,
      limit: 100,
      search: "",
      tab: "data",
    };

    const els = {
      dbMeta: document.getElementById("dbMeta"),
      tableFilter: document.getElementById("tableFilter"),
      tableList: document.getElementById("tableList"),
      tableTitle: document.getElementById("tableTitle"),
      tableMeta: document.getElementById("tableMeta"),
      rowSearch: document.getElementById("rowSearch"),
      limitSelect: document.getElementById("limitSelect"),
      prevPage: document.getElementById("prevPage"),
      nextPage: document.getElementById("nextPage"),
      pageStatus: document.getElementById("pageStatus"),
      dataGrid: document.getElementById("dataGrid"),
      schemaGrid: document.getElementById("schemaGrid"),
      sqlInput: document.getElementById("sqlInput"),
      sqlLimit: document.getElementById("sqlLimit"),
      runSql: document.getElementById("runSql"),
      sqlStatus: document.getElementById("sqlStatus"),
      sqlGrid: document.getElementById("sqlGrid"),
    };

    async function request(path, options) {
      const response = await fetch(path, options);
      const payload = await response.json();
      if (!response.ok || payload.error) {
        throw new Error(payload.error || response.statusText);
      }
      return payload;
    }

    function escapeText(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function formatCell(value) {
      if (value === null || value === undefined) {
        return { html: "NULL", cls: "null" };
      }
      if (typeof value === "object") {
        return { html: escapeText(JSON.stringify(value)), cls: "" };
      }
      return { html: escapeText(value), cls: "" };
    }

    function renderTable(target, columns, rows) {
      if (!columns.length) {
        target.innerHTML = '<div class="empty">No columns.</div>';
        return;
      }
      const head = columns.map(col => `<th>${escapeText(col)}</th>`).join("");
      const body = rows.map(row => {
        const cells = columns.map(col => {
          const cell = formatCell(row[col]);
          return `<td class="${cell.cls}">${cell.html}</td>`;
        }).join("");
        return `<tr>${cells}</tr>`;
      }).join("");
      target.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
    }

    function renderError(target, error) {
      target.innerHTML = `<div class="error">${escapeText(error.message || error)}</div>`;
    }

    function renderTableList() {
      const filter = els.tableFilter.value.trim().toLowerCase();
      const tables = state.tables.filter(item => item.name.toLowerCase().includes(filter));
      els.tableList.innerHTML = tables.map(item => {
        const active = item.name === state.currentTable ? " active" : "";
        const count = item.row_count === null ? "" : item.row_count.toLocaleString();
        return `<button class="table-item${active}" data-table="${escapeText(item.name)}">
          <span class="table-name">${escapeText(item.name)}</span>
          <span class="table-count">${count}</span>
        </button>`;
      }).join("");
    }

    async function selectTable(name) {
      state.currentTable = name;
      state.offset = 0;
      state.search = "";
      els.rowSearch.value = "";
      renderTableList();
      await Promise.all([loadTable(), loadSchema()]);
    }

    async function loadMeta() {
      const meta = await request("/api/meta");
      state.tables = meta.tables;
      els.dbMeta.textContent = `${meta.database} | ${meta.tables.length} tables`;
      renderTableList();
      if (state.tables.length) {
        await selectTable(state.tables[0].name);
      }
    }

    async function loadTable() {
      if (!state.currentTable) return;
      els.tableTitle.textContent = state.currentTable;
      els.dataGrid.innerHTML = '<div class="empty">Loading...</div>';
      const params = new URLSearchParams({
        name: state.currentTable,
        limit: state.limit,
        offset: state.offset,
        q: state.search,
      });
      try {
        const data = await request(`/api/table?${params}`);
        els.tableMeta.textContent = `${data.total.toLocaleString()} rows`;
        renderTable(els.dataGrid, data.columns, data.rows);
        const start = data.total ? data.offset + 1 : 0;
        const end = Math.min(data.offset + data.rows.length, data.total);
        els.pageStatus.textContent = `${start}-${end} / ${data.total.toLocaleString()}`;
        els.prevPage.disabled = data.offset <= 0;
        els.nextPage.disabled = data.offset + data.limit >= data.total;
      } catch (error) {
        renderError(els.dataGrid, error);
      }
    }

    async function loadSchema() {
      if (!state.currentTable) return;
      els.schemaGrid.innerHTML = '<div class="empty">Loading...</div>';
      const params = new URLSearchParams({ name: state.currentTable });
      try {
        const schema = await request(`/api/schema?${params}`);
        const columnRows = schema.columns.map(col => ({
          cid: col.cid,
          name: col.name,
          type: col.type,
          notnull: col.notnull,
          default: col.dflt_value,
          pk: col.pk,
        }));
        const indexRows = schema.indexes.map(idx => ({
          name: idx.name,
          unique: idx.unique,
          origin: idx.origin,
          partial: idx.partial,
        }));
        els.schemaGrid.innerHTML = `
          <div class="grid-wrap" id="columnsGrid"></div>
          <div class="grid-wrap" id="indexesGrid"></div>
          <pre>${escapeText(schema.sql || "")}</pre>
        `;
        renderTable(document.getElementById("columnsGrid"), ["cid", "name", "type", "notnull", "default", "pk"], columnRows);
        renderTable(document.getElementById("indexesGrid"), ["name", "unique", "origin", "partial"], indexRows);
      } catch (error) {
        renderError(els.schemaGrid, error);
      }
    }

    async function runSql() {
      els.sqlStatus.textContent = "Running...";
      els.sqlGrid.innerHTML = '<div class="empty">Loading...</div>';
      try {
        const data = await request("/api/sql", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sql: els.sqlInput.value,
            limit: Number(els.sqlLimit.value),
          }),
        });
        renderTable(els.sqlGrid, data.columns, data.rows);
        els.sqlStatus.textContent = `${data.rows.length.toLocaleString()} rows`;
      } catch (error) {
        els.sqlStatus.textContent = "";
        renderError(els.sqlGrid, error);
      }
    }

    document.addEventListener("click", event => {
      const tableButton = event.target.closest("[data-table]");
      if (tableButton) {
        selectTable(tableButton.dataset.table);
        return;
      }
      const tabButton = event.target.closest("[data-tab]");
      if (tabButton) {
        state.tab = tabButton.dataset.tab;
        document.querySelectorAll(".tab").forEach(tab => tab.classList.toggle("active", tab.dataset.tab === state.tab));
        document.querySelectorAll(".pane").forEach(pane => pane.classList.remove("active"));
        document.getElementById(`${state.tab}Pane`).classList.add("active");
      }
    });

    els.tableFilter.addEventListener("input", renderTableList);
    els.rowSearch.addEventListener("input", () => {
      state.search = els.rowSearch.value;
      state.offset = 0;
      window.clearTimeout(window.__rowSearchTimer);
      window.__rowSearchTimer = window.setTimeout(loadTable, 180);
    });
    els.limitSelect.addEventListener("change", () => {
      state.limit = Number(els.limitSelect.value);
      state.offset = 0;
      loadTable();
    });
    els.prevPage.addEventListener("click", () => {
      state.offset = Math.max(0, state.offset - state.limit);
      loadTable();
    });
    els.nextPage.addEventListener("click", () => {
      state.offset += state.limit;
      loadTable();
    });
    els.runSql.addEventListener("click", runSql);
    els.sqlInput.addEventListener("keydown", event => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        runSql();
      }
    });

    loadMeta().catch(error => {
      els.dbMeta.textContent = "Failed to load";
      renderError(els.tableList, error);
    });
  </script>
</body>
</html>
"""


def quote_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def json_value(value):
    if isinstance(value, bytes):
        preview = value[:256].hex()
        suffix = "..." if len(value) > 256 else ""
        return f"0x{preview}{suffix}"
    return value


def rows_to_dicts(cursor, rows):
    columns = [column[0] for column in cursor.description or []]
    return columns, [dict(zip(columns, [json_value(value) for value in row])) for row in rows]


class Viewer:
    def __init__(self, db_path):
        self.db_path = Path(db_path).resolve()

    def connect(self):
        uri = f"file:{urllib.parse.quote(str(self.db_path))}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma query_only = on")
        return conn

    def table_names(self, conn):
        rows = conn.execute(
            """
            select name, type
            from sqlite_schema
            where type in ('table', 'view')
              and name not like 'sqlite_%'
            order by lower(name)
            """
        ).fetchall()
        return [(row["name"], row["type"]) for row in rows]

    def ensure_table(self, conn, table_name):
        names = {name for name, _ in self.table_names(conn)}
        if table_name not in names:
            raise ValueError(f"Unknown table: {table_name}")

    def meta(self):
        with self.connect() as conn:
            tables = []
            for name, table_type in self.table_names(conn):
                count = None
                if table_type == "table":
                    count = conn.execute(f"select count(*) from {quote_identifier(name)}").fetchone()[0]
                tables.append({"name": name, "type": table_type, "row_count": count})
            return {"database": self.db_path.name, "tables": tables}

    def table(self, table_name, limit, offset, search):
        limit = max(1, min(MAX_LIMIT, int(limit)))
        offset = max(0, int(offset))
        with self.connect() as conn:
            self.ensure_table(conn, table_name)
            quoted = quote_identifier(table_name)
            column_rows = conn.execute(f"pragma table_info({quoted})").fetchall()
            columns = [row["name"] for row in column_rows]
            where = ""
            params = []
            if search and columns:
                clauses = [f"cast({quote_identifier(column)} as text) like ?" for column in columns]
                where = " where " + " or ".join(clauses)
                params = [f"%{search}%"] * len(columns)
            total = conn.execute(f"select count(*) from {quoted}{where}", params).fetchone()[0]
            cursor = conn.execute(
                f"select * from {quoted}{where} limit ? offset ?",
                [*params, limit, offset],
            )
            row_columns, rows = rows_to_dicts(cursor, cursor.fetchall())
            return {
                "columns": row_columns,
                "rows": rows,
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    def schema(self, table_name):
        with self.connect() as conn:
            self.ensure_table(conn, table_name)
            quoted = quote_identifier(table_name)
            columns = [dict(row) for row in conn.execute(f"pragma table_info({quoted})").fetchall()]
            indexes = [dict(row) for row in conn.execute(f"pragma index_list({quoted})").fetchall()]
            row = conn.execute(
                "select sql from sqlite_schema where name = ? and type in ('table', 'view')",
                [table_name],
            ).fetchone()
            return {"columns": columns, "indexes": indexes, "sql": row["sql"] if row else ""}

    def run_sql(self, sql, limit):
        sql = sql.strip()
        if not sql:
            raise ValueError("SQL is empty")
        first = sql.split(None, 1)[0].lower()
        if first not in {"select", "with", "pragma", "explain"}:
            raise ValueError("Only read-only SELECT, WITH, PRAGMA, and EXPLAIN statements are allowed")
        limit = max(1, min(MAX_LIMIT, int(limit)))
        with self.connect() as conn:
            cursor = conn.execute(sql)
            rows = cursor.fetchmany(limit)
            columns, records = rows_to_dicts(cursor, rows)
            return {"columns": columns, "rows": records}


class Handler(BaseHTTPRequestHandler):
    viewer = None

    def log_message(self, fmt, *args):
        return

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def handle_error(self, error):
        self.send_json({"error": str(error)}, status=400)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path == "/":
                body = HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/api/meta":
                self.send_json(self.viewer.meta())
            elif parsed.path == "/api/table":
                self.send_json(
                    self.viewer.table(
                        params.get("name", [""])[0],
                        params.get("limit", ["100"])[0],
                        params.get("offset", ["0"])[0],
                        params.get("q", [""])[0],
                    )
                )
            elif parsed.path == "/api/schema":
                self.send_json(self.viewer.schema(params.get("name", [""])[0]))
            else:
                self.send_json({"error": "Not found"}, status=404)
        except Exception as error:
            self.handle_error(error)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            if parsed.path == "/api/sql":
                payload = self.read_json()
                self.send_json(self.viewer.run_sql(payload.get("sql", ""), payload.get("limit", 100)))
            else:
                self.send_json({"error": "Not found"}, status=404)
        except Exception as error:
            self.handle_error(error)


def find_port(host, start_port):
    for port in range(start_port, start_port + 50):
        try:
            server = ThreadingHTTPServer((host, port), Handler)
            return server, port
        except OSError:
            continue
    raise OSError(f"No free port found from {start_port} to {start_port + 49}")


def main():
    parser = argparse.ArgumentParser(description="Read-only SQLite browser")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=4174, help="Preferred port")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        raise SystemExit(f"Database does not exist: {db_path}")

    Handler.viewer = Viewer(db_path)
    server, port = find_port(args.host, args.port)
    print(f"SQLite viewer: http://{args.host}:{port}", flush=True)
    print(f"Database: {html.escape(str(db_path))}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
