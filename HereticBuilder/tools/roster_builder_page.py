PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HereticBuilder</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f5f4;
      --panel: #ffffff;
      --ink: #15181b;
      --muted: #68717b;
      --line: #d9dee3;
      --line-strong: #b7c0ca;
      --accent: #1c6b5b;
      --accent-soft: #dceee8;
      --warn: #8a5b00;
      --bad: #9b2b2b;
      --bad-soft: #fff1f1;
      --good: #266b36;
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: var(--sans);
      font-size: 14px;
      letter-spacing: 0;
    }

    button, input, select {
      font: inherit;
    }

    button {
      border: 1px solid var(--line-strong);
      background: #fff;
      color: var(--ink);
      min-height: 34px;
      padding: 0 10px;
      border-radius: 6px;
      cursor: pointer;
      white-space: nowrap;
    }

    button:hover { border-color: #87929e; }
    button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
    button.ghost { border-color: transparent; background: transparent; color: var(--muted); }
    button.danger { color: var(--bad); }
    button.active { background: var(--accent-soft); border-color: var(--accent); color: #10483d; }
    button:disabled { opacity: .45; cursor: default; }

    input, select {
      border: 1px solid var(--line-strong);
      background: #fff;
      color: var(--ink);
      border-radius: 6px;
      min-height: 34px;
      padding: 7px 9px;
      outline: none;
      min-width: 0;
    }

    input:focus, select:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 2px rgba(28, 107, 91, .14);
    }

    .app {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      height: 100vh;
      min-height: 700px;
    }

    .top {
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      padding: 12px 16px;
      display: grid;
      grid-template-columns: minmax(220px, 320px) minmax(0, 1fr);
      gap: 12px;
      align-items: center;
    }

    .brand {
      min-width: 0;
    }

    .brand h1 {
      margin: 0 0 3px;
      font-size: 18px;
      line-height: 1.2;
    }

    .brand .meta {
      color: var(--muted);
      font-size: 12px;
    }

    .create {
      display: grid;
      grid-template-columns: minmax(130px, 1.1fr) minmax(140px, 1fr) minmax(150px, 1.2fr) minmax(160px, 1.4fr) auto;
      gap: 8px;
      align-items: center;
      min-width: 0;
    }

    .layout {
      min-height: 0;
      display: grid;
      grid-template-columns: 330px minmax(320px, .85fr) minmax(420px, 1.15fr);
    }

    .pane {
      min-width: 0;
      min-height: 0;
      overflow: hidden;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      border-right: 1px solid var(--line);
      background: var(--panel);
    }

    .pane:last-child { border-right: 0; }

    .pane-head {
      padding: 12px;
      border-bottom: 1px solid var(--line);
      display: grid;
      gap: 8px;
    }

    .pane-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-width: 0;
    }

    .roster-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      min-width: 0;
      flex: 1;
    }

    .roster-actions select {
      width: min(190px, 100%);
    }

    .pane-title h2 {
      margin: 0;
      font-size: 15px;
      line-height: 1.2;
    }

    .scroll {
      min-height: 0;
      overflow: auto;
      padding: 8px;
    }

    .summary {
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }

    .meter {
      height: 9px;
      border-radius: 999px;
      background: #e5e8eb;
      overflow: hidden;
      border: 1px solid #d4d9df;
    }

    .meter span {
      display: block;
      width: 0;
      height: 100%;
      background: var(--accent);
    }

    .meter.over span { background: var(--bad); }

    .row {
      width: 100%;
      min-height: 42px;
      border: 1px solid transparent;
      border-radius: 7px;
      background: transparent;
      padding: 8px;
      display: grid;
      gap: 4px;
      text-align: left;
    }

    .row:hover { background: #f0f2f3; }
    .row.active { border-color: var(--accent); background: var(--accent-soft); }

    .row-main {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 10px;
      min-width: 0;
    }

    .name {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 650;
    }

    .points {
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      font-size: 12px;
      white-space: nowrap;
    }

    .sub {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.3;
      overflow-wrap: anywhere;
    }

    .unit-row {
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
      column-gap: 8px;
    }

    .unit-row .row-body {
      min-width: 0;
      display: grid;
      gap: 3px;
    }

    .filters {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
    }

    .empty {
      color: var(--muted);
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fafafa;
    }

    .messages {
      display: grid;
      gap: 6px;
    }

    .message {
      padding: 8px;
      border-radius: 7px;
      border: 1px solid var(--line);
      font-size: 12px;
      line-height: 1.35;
    }

    .message.error {
      color: var(--bad);
      background: var(--bad-soft);
      border-color: #edc7c7;
    }

    .message.warning {
      color: var(--warn);
      background: #fff8e9;
      border-color: #ecd6a3;
    }

    .message.ok {
      color: var(--good);
      background: #f0fbf2;
      border-color: #b9d9c0;
    }

    .detail {
      display: grid;
      gap: 12px;
    }

    .section {
      display: grid;
      gap: 8px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--line);
    }

    .section:last-child { border-bottom: 0; }

    .section h3 {
      margin: 0;
      font-size: 13px;
      text-transform: uppercase;
      color: #47515b;
      letter-spacing: 0;
    }

    .choice-list {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
    }

    .model {
      display: grid;
      gap: 8px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fafafa;
    }

    .model-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }

    .model-actions {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .stats {
      display: grid;
      grid-template-columns: repeat(6, minmax(44px, 1fr));
      gap: 4px;
      font-family: var(--mono);
      font-size: 11px;
      color: #333b43;
    }

    .stat {
      padding: 5px;
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 5px;
      text-align: center;
    }

    .gear-group {
      display: grid;
      gap: 6px;
      padding-top: 8px;
      border-top: 1px solid var(--line);
    }

    .gear-title {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }

    .gear-options {
      display: grid;
      gap: 4px;
    }

    .gear-option {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) auto;
      align-items: center;
      gap: 8px;
      min-height: 32px;
      padding: 4px 6px;
      border-radius: 6px;
      background: #fff;
      border: 1px solid #eef0f2;
    }

    .gear-option input[type="checkbox"] {
      width: 16px;
      height: 16px;
      min-height: 16px;
      padding: 0;
    }

    .gear-option input[type="number"] {
      width: 68px;
      min-height: 28px;
      padding: 4px 6px;
      font-family: var(--mono);
    }

    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 2px 7px;
      border-radius: 999px;
      background: #eef1f3;
      color: #4a545e;
      font-size: 12px;
      white-space: nowrap;
    }

    @media (max-width: 1180px) {
      .top {
        grid-template-columns: 1fr;
      }

      .create {
        grid-template-columns: repeat(2, minmax(0, 1fr)) auto;
      }

      .layout {
        grid-template-columns: 300px minmax(0, 1fr);
        grid-template-rows: minmax(330px, .85fr) minmax(360px, 1fr);
      }

      .pane.detail-pane {
        grid-column: 1 / -1;
        border-top: 1px solid var(--line);
      }
    }

    @media (max-width: 760px) {
      .app { height: auto; min-height: 100vh; }
      .create { grid-template-columns: 1fr; }
      .layout { grid-template-columns: 1fr; grid-template-rows: auto auto auto; }
      .pane { min-height: 360px; border-right: 0; border-bottom: 1px solid var(--line); }
      .pane.detail-pane { grid-column: auto; }
    }
  </style>
</head>
<body>
  <div class="app">
    <header class="top">
      <div class="brand">
        <h1>HereticBuilder</h1>
        <div class="meta" id="dbMeta">Loading data...</div>
      </div>
      <div class="create">
        <input id="rosterName" placeholder="Roster name" value="New Roster">
        <select id="battleSize"></select>
        <select id="faction"></select>
        <select id="detachment"></select>
        <button class="primary" id="createRoster">Create</button>
      </div>
    </header>

    <main class="layout">
      <section class="pane">
        <div class="pane-head">
          <div class="pane-title">
            <h2>Roster</h2>
            <div class="roster-actions">
              <select id="rosterSelect"></select>
              <button class="danger" id="deleteRoster">Delete</button>
            </div>
          </div>
          <div class="summary" id="rosterSummary"></div>
          <div class="messages" id="messages"></div>
        </div>
        <div class="scroll" id="rosterUnits"></div>
      </section>

      <section class="pane">
        <div class="pane-head">
          <div class="pane-title">
            <h2>Add Units</h2>
            <span class="pill" id="availableCount">0</span>
          </div>
          <div class="filters">
            <input id="unitSearch" type="search" placeholder="Search datasheets">
            <button id="refreshUnits">Refresh</button>
          </div>
        </div>
        <div class="scroll" id="availableUnits"></div>
      </section>

      <section class="pane detail-pane">
        <div class="pane-head">
          <div class="pane-title">
            <h2>Unit</h2>
            <span class="pill" id="unitPoints">No unit</span>
          </div>
        </div>
        <div class="scroll">
          <div class="detail" id="unitDetail"></div>
        </div>
      </section>
    </main>
  </div>

  <script>
    const state = {
      bootstrap: null,
      roster: null,
      rosterId: null,
      unitId: null,
      availableUnits: [],
    };

    const els = {
      dbMeta: document.getElementById("dbMeta"),
      rosterName: document.getElementById("rosterName"),
      battleSize: document.getElementById("battleSize"),
      faction: document.getElementById("faction"),
      detachment: document.getElementById("detachment"),
      createRoster: document.getElementById("createRoster"),
      deleteRoster: document.getElementById("deleteRoster"),
      rosterSelect: document.getElementById("rosterSelect"),
      rosterSummary: document.getElementById("rosterSummary"),
      messages: document.getElementById("messages"),
      rosterUnits: document.getElementById("rosterUnits"),
      unitSearch: document.getElementById("unitSearch"),
      refreshUnits: document.getElementById("refreshUnits"),
      availableCount: document.getElementById("availableCount"),
      availableUnits: document.getElementById("availableUnits"),
      unitPoints: document.getElementById("unitPoints"),
      unitDetail: document.getElementById("unitDetail"),
    };

    async function api(path, options = {}) {
      const response = await fetch(path, options);
      const payload = await response.json();
      if (!response.ok || payload.error) {
        throw new Error(payload.error || response.statusText);
      }
      return payload;
    }

    function esc(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function optionList(items, selectedId) {
      return items.map(item => `<option value="${esc(item.id)}" ${item.id === selectedId ? "selected" : ""}>${esc(item.name)}</option>`).join("");
    }

    function post(path, data) {
      return api(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
    }

    async function loadBootstrap() {
      state.bootstrap = await api("/api/bootstrap");
      els.dbMeta.textContent = `${state.bootstrap.database} | ${state.bootstrap.rosters.length} rosters`;
      els.battleSize.innerHTML = optionList(state.bootstrap.battleSizes, state.bootstrap.defaultBattleSizeId);
      els.faction.innerHTML = optionList(state.bootstrap.factions, state.bootstrap.defaultFactionId);
      renderRosterSelect();
      await loadDetachments();
      const firstRoster = state.bootstrap.rosters[0];
      if (firstRoster) {
        await selectRoster(firstRoster.id);
      } else {
        renderNoRoster();
      }
    }

    function renderRosterSelect() {
      const rosters = state.bootstrap.rosters;
      els.rosterSelect.innerHTML = rosters.length
        ? rosters.map(r => `<option value="${esc(r.id)}">${esc(r.name)} - ${esc(r.factionName)}</option>`).join("")
        : '<option value="">No rosters</option>';
      els.rosterSelect.value = state.rosterId || (rosters[0] && rosters[0].id) || "";
      els.deleteRoster.disabled = !rosters.length;
    }

    async function refreshRosters() {
      const current = state.rosterId;
      state.bootstrap = await api("/api/bootstrap");
      renderRosterSelect();
      if (current && state.bootstrap.rosters.some(r => r.id === current)) {
        els.rosterSelect.value = current;
      }
    }

    async function loadDetachments() {
      const factionId = els.faction.value;
      const data = await api(`/api/detachments?factionId=${encodeURIComponent(factionId)}`);
      els.detachment.innerHTML = optionList(data.detachments, data.detachments[0] && data.detachments[0].id);
    }

    async function selectRoster(rosterId) {
      if (!rosterId) {
        renderNoRoster();
        return;
      }
      state.rosterId = rosterId;
      els.rosterSelect.value = rosterId;
      state.roster = await api(`/api/roster?id=${encodeURIComponent(rosterId)}`);
      renderRoster();
      await loadAvailableUnits();
    }

    function renderNoRoster() {
      state.roster = null;
      state.rosterId = null;
      els.rosterSummary.innerHTML = '<div class="empty">Create a roster to start.</div>';
      els.messages.innerHTML = "";
      els.rosterUnits.innerHTML = "";
      els.availableUnits.innerHTML = "";
      els.unitDetail.innerHTML = "";
      els.unitPoints.textContent = "No unit";
      els.deleteRoster.disabled = true;
    }

    function renderRoster() {
      const roster = state.roster.roster;
      const points = state.roster.points;
      const pct = points.limit ? Math.min(100, Math.round(points.total / points.limit * 100)) : 0;
      const over = points.total > points.limit;
      els.rosterSummary.innerHTML = `
        <div><strong>${esc(roster.name)}</strong></div>
        <div>${esc(roster.factionName)} | ${esc(roster.battleSizeName || "No battle size")}</div>
        <div>${esc(state.roster.detachments.map(d => d.name).join(", ") || "No detachment")}</div>
        <div class="meter ${over ? "over" : ""}"><span style="width:${pct}%"></span></div>
        <div>${points.total} / ${points.limit || 0} pts</div>
      `;
      renderMessages();
      renderRosterUnits();
    }

    function renderMessages() {
      const messages = state.roster.validation.messages;
      if (!messages.length) {
        els.messages.innerHTML = '<div class="message ok">Roster validation passed.</div>';
        return;
      }
      els.messages.innerHTML = messages.map(m => `<div class="message ${esc(m.level)}">${esc(m.text)}</div>`).join("");
    }

    function renderRosterUnits() {
      const units = state.roster.units;
      if (!units.length) {
        els.rosterUnits.innerHTML = '<div class="empty">No units yet.</div>';
        return;
      }
      els.rosterUnits.innerHTML = units.map(unit => `
        <div class="row unit-row ${unit.id === state.unitId ? "active" : ""}" data-unit-id="${esc(unit.id)}">
          <button class="row row-body ${unit.id === state.unitId ? "active" : ""}" data-open-unit="${esc(unit.id)}">
            <div class="row-main">
              <span class="name">${esc(unit.name)}</span>
              <span class="points">${unit.points} pts</span>
            </div>
            <div class="sub">${esc(unit.compositionLabel || "No composition")} | ${unit.modelCount} models</div>
          </button>
          <button class="ghost danger" title="Remove unit" data-remove-unit="${esc(unit.id)}">x</button>
        </div>
      `).join("");
    }

    async function loadAvailableUnits() {
      if (!state.roster) return;
      const roster = state.roster.roster;
      const detachment = state.roster.detachments[0];
      const params = new URLSearchParams({
        factionId: roster.factionKeywordId,
        detachmentId: detachment ? detachment.id : "",
        q: els.unitSearch.value,
      });
      const data = await api(`/api/datasheets?${params}`);
      state.availableUnits = data.datasheets;
      els.availableCount.textContent = data.datasheets.length;
      renderAvailableUnits();
    }

    function renderAvailableUnits() {
      const units = state.availableUnits;
      if (!units.length) {
        els.availableUnits.innerHTML = '<div class="empty">No matching datasheets.</div>';
        return;
      }
      els.availableUnits.innerHTML = units.map(unit => `
        <div class="row unit-row">
          <div class="row-body">
            <div class="row-main">
              <span class="name">${esc(unit.name)}</span>
              <span class="points">${unit.points} pts</span>
            </div>
            <div class="sub">${esc(unit.baseSize || "")}${unit.baseSize ? " | " : ""}${esc(unit.unitComposition || "")}</div>
          </div>
          <button data-add-unit="${esc(unit.id)}">Add</button>
        </div>
      `).join("");
    }

    async function loadUnit(unitId) {
      state.unitId = unitId;
      const detail = await api(`/api/unit?id=${encodeURIComponent(unitId)}`);
      renderRosterUnits();
      renderUnitDetail(detail);
    }

    function renderUnitDetail(detail) {
      els.unitPoints.textContent = `${detail.summary.points} pts`;
      const compositions = detail.compositions.map(comp => `
        <button class="${comp.id === detail.summary.selectedCompositionId ? "active" : ""}" data-composition="${esc(comp.id)}">
          ${esc(comp.label)} | ${comp.points} pts
        </button>
      `).join("");
      const unitWargear = renderWargearGroups({
        id: detail.summary.id,
        groups: detail.unitWargearGroups || [],
        targetType: "unit",
      });

      const models = detail.miniatures.map(model => `
        <div class="model">
          <div class="model-head">
            <strong>${esc(model.count)} x ${esc(model.name)}</strong>
            <div class="model-actions">
              <span class="pill">${esc(model.miniatureSlots)} slot</span>
              <button class="${model.isWarlord ? "active" : ""}" ${model.canBeWarlord ? "" : "disabled"} data-warlord-model="${esc(model.id)}" data-warlord-enabled="${model.isWarlord ? "1" : "0"}">Warlord</button>
            </div>
          </div>
          <div class="stats">
            <div class="stat">M ${esc(model.movement)}</div>
            <div class="stat">T ${esc(model.toughness)}</div>
            <div class="stat">SV ${esc(model.save)}</div>
            <div class="stat">W ${esc(model.wounds)}</div>
            <div class="stat">LD ${esc(model.leadership)}</div>
            <div class="stat">OC ${esc(model.objectiveControl)}</div>
          </div>
          ${renderWargearGroups(model)}
        </div>
      `).join("");

      els.unitDetail.innerHTML = `
        <section class="section">
          <h3>${esc(detail.summary.name)}</h3>
          <div class="sub">${esc(detail.summary.compositionLabel || "No composition")} | ${detail.summary.modelCount} models</div>
        </section>
        <section class="section">
          <h3>Composition</h3>
          <div class="choice-list">${compositions || '<div class="empty">No composition choices.</div>'}</div>
        </section>
        <section class="section">
          <h3>Models & Wargear</h3>
          ${unitWargear ? `<div class="model"><div class="model-head"><strong>Unit Wargear</strong></div>${unitWargear}</div>` : ""}
          ${models || '<div class="empty">No models.</div>'}
        </section>
      `;
    }

    function renderWargearGroups(target) {
      if (!target.groups.length) {
        return target.targetType === "unit" ? "" : '<div class="sub">No wargear options.</div>';
      }
      return target.groups.map(group => `
        <div class="gear-group">
          <div class="gear-title">${esc(group.instructionText)}</div>
          <div class="gear-options">
            ${group.options.map(option => renderWargearOption(target, option)).join("")}
          </div>
        </div>
      `).join("");
    }

    function renderWargearOption(target, option) {
      const price = option.points ? `${option.points} pts` : "";
      const control = option.inputType === "stepper"
        ? `<input type="number" min="0" max="30" value="${option.selectedCount}" data-gear="${esc(option.id)}" data-target-type="${esc(target.targetType || "model")}" data-target-id="${esc(target.id)}">`
        : `<input type="checkbox" ${option.selectedCount > 0 ? "checked" : ""} data-gear="${esc(option.id)}" data-target-type="${esc(target.targetType || "model")}" data-target-id="${esc(target.id)}">`;
      return `
        <label class="gear-option">
          ${control}
          <span>${esc(option.name)}</span>
          <span class="points">${esc(price)}</span>
        </label>
      `;
    }

    els.faction.addEventListener("change", loadDetachments);
    els.rosterSelect.addEventListener("change", () => selectRoster(els.rosterSelect.value));
    els.refreshUnits.addEventListener("click", loadAvailableUnits);
    els.unitSearch.addEventListener("input", () => {
      clearTimeout(window.__searchTimer);
      window.__searchTimer = setTimeout(loadAvailableUnits, 180);
    });
    els.createRoster.addEventListener("click", async () => {
      const result = await post("/api/roster/create", {
        name: els.rosterName.value.trim() || "New Roster",
        battleSizeId: els.battleSize.value,
        factionKeywordId: els.faction.value,
        detachmentId: els.detachment.value,
      });
      await refreshRosters();
      await selectRoster(result.id);
    });
    els.deleteRoster.addEventListener("click", async () => {
      if (!state.rosterId || !state.roster) return;
      const rosterName = state.roster.roster.name;
      if (!window.confirm(`Delete roster "${rosterName}"?`)) return;
      await post("/api/roster/delete", { id: state.rosterId });
      state.rosterId = null;
      state.unitId = null;
      await refreshRosters();
      const nextRoster = state.bootstrap.rosters[0];
      if (nextRoster) {
        await selectRoster(nextRoster.id);
      } else {
        renderNoRoster();
      }
    });

    document.addEventListener("click", async event => {
      const add = event.target.closest("[data-add-unit]");
      if (add) {
        const result = await post("/api/unit/add", { rosterId: state.rosterId, datasheetId: add.dataset.addUnit });
        state.unitId = result.id;
        await selectRoster(state.rosterId);
        await loadUnit(result.id);
        return;
      }

      const remove = event.target.closest("[data-remove-unit]");
      if (remove) {
        await post("/api/unit/delete", { id: remove.dataset.removeUnit });
        if (state.unitId === remove.dataset.removeUnit) {
          state.unitId = null;
          els.unitDetail.innerHTML = "";
          els.unitPoints.textContent = "No unit";
        }
        await selectRoster(state.rosterId);
        return;
      }

      const open = event.target.closest("[data-open-unit]");
      if (open) {
        await loadUnit(open.dataset.openUnit);
        return;
      }

      const composition = event.target.closest("[data-composition]");
      if (composition && state.unitId) {
        await post("/api/unit/composition", { rosterUnitId: state.unitId, compositionId: composition.dataset.composition });
        await selectRoster(state.rosterId);
        await loadUnit(state.unitId);
        return;
      }

      const warlord = event.target.closest("[data-warlord-model]");
      if (warlord && state.unitId) {
        await post("/api/warlord", {
          rosterUnitMiniatureId: warlord.dataset.warlordModel,
          enabled: warlord.dataset.warlordEnabled !== "1",
        });
        await selectRoster(state.rosterId);
        await loadUnit(state.unitId);
      }
    });

    document.addEventListener("change", async event => {
      const gear = event.target.closest("[data-gear]");
      if (!gear) return;
      const count = gear.type === "checkbox" ? (gear.checked ? 1 : 0) : Number(gear.value || 0);
      if (gear.dataset.targetType === "unit") {
        await post("/api/unit-wargear", {
          rosterUnitId: gear.dataset.targetId,
          wargearOptionId: gear.dataset.gear,
          count,
        });
      } else {
        await post("/api/wargear", {
          rosterUnitMiniatureId: gear.dataset.targetId,
          wargearOptionId: gear.dataset.gear,
          count,
        });
      }
      await selectRoster(state.rosterId);
      await loadUnit(state.unitId);
    });

    loadBootstrap().catch(error => {
      els.dbMeta.textContent = error.message;
    });
  </script>
</body>
</html>
"""
