#!/usr/bin/env python3
import argparse
import html
import json
import sqlite3
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "heretic_sheets.sqlite"


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
        els.messages.innerHTML = '<div class="message ok">Simple validation passed.</div>';
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

      const models = detail.miniatures.map(model => `
        <div class="model">
          <div class="model-head">
            <strong>${esc(model.count)} x ${esc(model.name)}</strong>
            <span class="pill">${esc(model.miniatureSlots)} slot</span>
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
          ${models || '<div class="empty">No models.</div>'}
        </section>
      `;
    }

    function renderWargearGroups(model) {
      if (!model.groups.length) {
        return '<div class="sub">No wargear options.</div>';
      }
      return model.groups.map(group => `
        <div class="gear-group">
          <div class="gear-title">${esc(group.instructionText)}</div>
          <div class="gear-options">
            ${group.options.map(option => renderWargearOption(model, option)).join("")}
          </div>
        </div>
      `).join("");
    }

    function renderWargearOption(model, option) {
      const price = option.points ? `${option.points} pts` : "";
      const control = option.inputType === "stepper"
        ? `<input type="number" min="0" max="30" value="${option.selectedCount}" data-gear="${esc(option.id)}" data-model="${esc(model.id)}">`
        : `<input type="checkbox" ${option.selectedCount > 0 ? "checked" : ""} data-gear="${esc(option.id)}" data-model="${esc(model.id)}">`;
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
      }
    });

    document.addEventListener("change", async event => {
      const gear = event.target.closest("[data-gear]");
      if (!gear) return;
      const count = gear.type === "checkbox" ? (gear.checked ? 1 : 0) : Number(gear.value || 0);
      await post("/api/wargear", {
        rosterUnitMiniatureId: gear.dataset.model,
        wargearOptionId: gear.dataset.gear,
        count,
      });
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


def new_id():
    return str(uuid.uuid4()).upper()


def dict_row(row):
    return {key: row[key] for key in row.keys()}


def find_port(host, start):
    for port in range(start, start + 50):
        try:
            return ThreadingHTTPServer((host, port), Handler), port
        except OSError:
            continue
    raise OSError(f"No free port found from {start} to {start + 49}")


class HereticBuilder:
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

    def bootstrap(self):
        with self.connect(readonly=True) as conn:
            factions = [dict_row(row) for row in conn.execute(
                """
                select id, name
                from faction_keyword
                where excludedFromArmyBuilder = 0
                order by lower(name)
                """
            )]
            battle_sizes = [dict_row(row) for row in conn.execute(
                "select id, name, pointsLimit from battle_size order by pointsLimit"
            )]
            rosters = [dict_row(row) for row in conn.execute(
                """
                select r.id, r.name, r.modifiedAt, r.factionKeywordId, r.battleSizeId,
                       fk.name as factionName, bs.name as battleSizeName
                from roster r
                join faction_keyword fk on fk.id = r.factionKeywordId
                left join battle_size bs on bs.id = r.battleSizeId
                order by r.modifiedAt desc, r.name
                """
            )]
        default_faction = next((item["id"] for item in factions if item["name"] == "Heretic Astartes"), factions[0]["id"] if factions else "")
        default_size = next((item["id"] for item in battle_sizes if item["name"] == "Strike Force"), battle_sizes[0]["id"] if battle_sizes else "")
        return {
            "database": self.db_path.name,
            "factions": factions,
            "battleSizes": battle_sizes,
            "rosters": rosters,
            "defaultFactionId": default_faction,
            "defaultBattleSizeId": default_size,
        }

    def detachments(self, faction_id):
        with self.connect(readonly=True) as conn:
            rows = conn.execute(
                """
                select d.id, d.name, d.detachmentPointsCost, d.isCombatPatrol
                from detachment d
                join detachment_faction_keyword dfk on dfk.detachmentId = d.id
                where dfk.factionKeywordId = ?
                order by d.isCombatPatrol, d.displayOrder, lower(d.name)
                """,
                [faction_id],
            ).fetchall()
        return {"detachments": [dict_row(row) for row in rows]}

    def datasheets(self, faction_id, detachment_id, query):
        params = [faction_id]
        excluded = ""
        if detachment_id:
            excluded = """
              and not exists (
                select 1 from detachment_excluded_datasheet ded
                where ded.detachmentId = ? and ded.datasheetId = d.id
              )
            """
            params.append(detachment_id)
        search = ""
        if query:
            search = "and d.name like ?"
            params.append(f"%{query}%")
        sql = f"""
            select d.id, d.name, d.baseSize, d.unitComposition,
                   coalesce((
                     select uc.points
                     from unit_composition uc
                     where uc.datasheetId = d.id
                     order by uc.isDefault desc, uc.displayOrder
                     limit 1
                   ), 0) as points
            from datasheet d
            join datasheet_faction_keyword dfk on dfk.datasheetId = d.id
            where dfk.factionKeywordId = ?
              {excluded}
              {search}
            order by dfk.displayOrder, lower(d.name)
            limit 250
        """
        with self.connect(readonly=True) as conn:
            rows = conn.execute(sql, params).fetchall()
        data = []
        for row in rows:
            item = dict_row(row)
            item["unitComposition"] = plain_text(item["unitComposition"])[:220]
            data.append(item)
        return {"datasheets": data}

    def create_roster(self, payload):
        roster_id = new_id()
        name = payload.get("name") or "New Roster"
        faction_id = payload["factionKeywordId"]
        battle_size_id = payload["battleSizeId"]
        detachment_id = payload.get("detachmentId")
        with self.connect() as conn:
            conn.execute(
                """
                insert into roster (id, name, factionKeywordId, battleSizeId, rosterType)
                values (?, ?, ?, ?, 'Warhammer40k')
                """,
                [roster_id, name, faction_id, battle_size_id],
            )
            if detachment_id:
                conn.execute(
                    "insert into roster_detachment (rosterId, detachmentId) values (?, ?)",
                    [roster_id, detachment_id],
                )
            conn.execute(
                "insert or replace into roster_validation_state (id, rosterId, validationState) values (?, ?, 'valid')",
                [roster_id, roster_id],
            )
        return {"id": roster_id}

    def delete_roster(self, roster_id):
        with self.connect() as conn:
            exists = conn.execute("select 1 from roster where id = ?", [roster_id]).fetchone()
            if not exists:
                raise ValueError("Roster not found")
            conn.execute("delete from roster_validation_state where rosterId = ?", [roster_id])
            conn.execute("delete from roster where id = ?", [roster_id])
        return {"ok": True}

    def roster(self, roster_id):
        with self.connect(readonly=True) as conn:
            roster = conn.execute(
                """
                select r.*, fk.name as factionName, bs.name as battleSizeName,
                       bs.pointsLimit, bs.detachmentPointsLimit, bs.duplicateUnitLimit
                from roster r
                join faction_keyword fk on fk.id = r.factionKeywordId
                left join battle_size bs on bs.id = r.battleSizeId
                where r.id = ?
                """,
                [roster_id],
            ).fetchone()
            if not roster:
                raise ValueError("Roster not found")
            detachments = [dict_row(row) for row in conn.execute(
                """
                select d.*
                from roster_detachment rd
                join detachment d on d.id = rd.detachmentId
                where rd.rosterId = ?
                order by d.displayOrder, d.name
                """,
                [roster_id],
            )]
            unit_rows = conn.execute(
                """
                select ru.id, ru.datasheetId, ru.allyType, d.name
                from roster_unit ru
                join datasheet d on d.id = ru.datasheetId
                where ru.rosterId = ?
                order by d.name, ru.id
                """,
                [roster_id],
            ).fetchall()
            units = [self.unit_summary(conn, dict_row(row)) for row in unit_rows]
            total = sum(unit["points"] for unit in units)
            roster_dict = dict_row(roster)
            validation = self.validate(conn, roster_dict, detachments, units, total)
        return {
            "roster": roster_dict,
            "detachments": detachments,
            "units": units,
            "points": {"total": total, "limit": roster_dict.get("pointsLimit") or 0},
            "validation": validation,
        }

    def add_unit(self, roster_id, datasheet_id):
        roster_unit_id = new_id()
        with self.connect() as conn:
            conn.execute(
                "insert into roster_unit (id, datasheetId, rosterId, allyType) values (?, ?, ?, 'native')",
                [roster_unit_id, datasheet_id, roster_id],
            )
            composition = self.default_composition(conn, datasheet_id)
            if composition:
                self.apply_composition(conn, roster_unit_id, composition["id"])
        return {"id": roster_unit_id}

    def delete_unit(self, roster_unit_id):
        with self.connect() as conn:
            conn.execute("delete from roster_unit where id = ?", [roster_unit_id])
        return {"ok": True}

    def set_composition(self, roster_unit_id, composition_id):
        with self.connect() as conn:
            self.apply_composition(conn, roster_unit_id, composition_id)
        return {"ok": True}

    def set_wargear(self, roster_unit_miniature_id, wargear_option_id, count):
        count = max(0, int(count or 0))
        with self.connect() as conn:
            if count:
                conn.execute(
                    """
                    insert into roster_unit_miniature_wargear_option
                      (rosterUnitMiniatureId, wargearOptionId, count)
                    values (?, ?, ?)
                    on conflict(rosterUnitMiniatureId, wargearOptionId) do update set count = excluded.count
                    """,
                    [roster_unit_miniature_id, wargear_option_id, count],
                )
            else:
                conn.execute(
                    """
                    delete from roster_unit_miniature_wargear_option
                    where rosterUnitMiniatureId = ? and wargearOptionId = ?
                    """,
                    [roster_unit_miniature_id, wargear_option_id],
                )
        return {"ok": True}

    def unit_detail(self, roster_unit_id):
        with self.connect(readonly=True) as conn:
            row = conn.execute(
                """
                select ru.id, ru.datasheetId, ru.allyType, d.name
                from roster_unit ru
                join datasheet d on d.id = ru.datasheetId
                where ru.id = ?
                """,
                [roster_unit_id],
            ).fetchone()
            if not row:
                raise ValueError("Unit not found")
            summary = self.unit_summary(conn, dict_row(row))
            compositions = self.compositions(conn, row["datasheetId"])
            miniature_rows = conn.execute(
                """
                select rum.id, rum.count, rum.isWarlord,
                       m.id as miniatureId, m.name, m.movement, m.toughness, m.save,
                       m.wounds, m.leadership, m.objectiveControl, m.statlineHidden,
                       m.isSupremeCommander, m.cannotBeWarlord,
                       m.excludedFromEnhancements, m.datasheetId, m.displayOrder,
                       m.isIndividualModels, m.canBeNonCharacterWarlord,
                       m.miniatureSlots
                from roster_unit_miniature rum
                join miniature m on m.id = rum.miniatureId
                where rum.rosterUnitId = ?
                order by m.displayOrder, m.name
                """,
                [roster_unit_id],
            ).fetchall()
            miniatures = []
            for miniature in miniature_rows:
                item = dict_row(miniature)
                item["groups"] = self.wargear_groups(conn, row["datasheetId"], item["id"], item["miniatureId"])
                miniatures.append(item)
        return {
            "summary": summary,
            "compositions": compositions,
            "miniatures": miniatures,
        }

    def wargear_groups(self, conn, datasheet_id, roster_miniature_id, miniature_id):
        rows = conn.execute(
            """
            select wog.id as groupId, wog.instructionText, wog.displayOrder as groupOrder,
                   wo.id, wo.inputType, wo.defaultValue, wo.points, wo.displayOrder,
                   wi.name,
                   coalesce(rumwo.count, 0) as selectedCount
            from wargear_option_group wog
            join wargear_option wo on wo.wargearOptionGroupId = wog.id
            join wargear_item wi on wi.id = wo.wargearItemId
            left join roster_unit_miniature_wargear_option rumwo
              on rumwo.wargearOptionId = wo.id and rumwo.rosterUnitMiniatureId = ?
            where wog.datasheetId = ?
              and (wog.miniatureId is null or wog.miniatureId = ?)
            order by wog.displayOrder, wo.displayOrder, wi.name
            """,
            [roster_miniature_id, datasheet_id, miniature_id],
        ).fetchall()
        groups = []
        by_id = {}
        for row in rows:
            group_id = row["groupId"]
            if group_id not in by_id:
                group = {
                    "id": group_id,
                    "instructionText": row["instructionText"],
                    "options": [],
                }
                by_id[group_id] = group
                groups.append(group)
            by_id[group_id]["options"].append({
                "id": row["id"],
                "name": row["name"],
                "inputType": row["inputType"],
                "defaultValue": row["defaultValue"],
                "points": row["points"],
                "selectedCount": row["selectedCount"],
            })
        return groups

    def default_composition(self, conn, datasheet_id):
        row = conn.execute(
            """
            select *
            from unit_composition
            where datasheetId = ?
            order by isDefault desc, displayOrder
            limit 1
            """,
            [datasheet_id],
        ).fetchone()
        return dict_row(row) if row else None

    def compositions(self, conn, datasheet_id):
        rows = conn.execute(
            """
            select *
            from unit_composition
            where datasheetId = ?
            order by isDefault desc, displayOrder
            """,
            [datasheet_id],
        ).fetchall()
        result = []
        for row in rows:
            comp = dict_row(row)
            models = [dict_row(model) for model in conn.execute(
                """
                select ucm.*, m.name
                from unit_composition_miniature ucm
                join miniature m on m.id = ucm.miniatureId
                where ucm.unitCompositionId = ?
                order by m.displayOrder, m.name
                """,
                [comp["id"]],
            )]
            comp["models"] = models
            comp["label"] = composition_label(models)
            result.append(comp)
        return result

    def apply_composition(self, conn, roster_unit_id, composition_id):
        unit = conn.execute("select datasheetId from roster_unit where id = ?", [roster_unit_id]).fetchone()
        if not unit:
            raise ValueError("Unit not found")
        models = conn.execute(
            """
            select ucm.*, m.name
            from unit_composition_miniature ucm
            join miniature m on m.id = ucm.miniatureId
            where ucm.unitCompositionId = ?
            order by m.displayOrder, m.name
            """,
            [composition_id],
        ).fetchall()
        if not models:
            raise ValueError("Composition has no models")
        conn.execute("delete from roster_unit_miniature where rosterUnitId = ?", [roster_unit_id])
        for model in models:
            roster_miniature_id = new_id()
            conn.execute(
                """
                insert into roster_unit_miniature
                  (id, count, miniatureId, rosterUnitId, isWarlord)
                values (?, ?, ?, ?, 0)
                """,
                [roster_miniature_id, model["min"], model["miniatureId"], roster_unit_id],
            )
            self.apply_base_loadout(conn, roster_miniature_id, unit["datasheetId"], model["miniatureId"])

    def apply_base_loadout(self, conn, roster_miniature_id, datasheet_id, miniature_id):
        loadout = conn.execute(
            """
            select id
            from base_miniature_loadout
            where miniatureId = ?
            order by case when datasheetId = ? then 0 else 1 end
            limit 1
            """,
            [miniature_id, datasheet_id],
        ).fetchone()
        if not loadout:
            loadout = conn.execute(
                """
                select id
                from base_miniature_loadout
                where datasheetId = ? and miniatureId is null
                limit 1
                """,
                [datasheet_id],
            ).fetchone()
        if not loadout:
            return
        options = conn.execute(
            """
            select wargearOptionId, count
            from base_miniature_loadout_wargear_option
            where baseMiniatureLoadoutId = ?
            """,
            [loadout["id"]],
        ).fetchall()
        for option in options:
            conn.execute(
                """
                insert or replace into roster_unit_miniature_wargear_option
                  (rosterUnitMiniatureId, wargearOptionId, count)
                values (?, ?, ?)
                """,
                [roster_miniature_id, option["wargearOptionId"], option["count"]],
            )

    def unit_summary(self, conn, unit):
        miniatures = [dict_row(row) for row in conn.execute(
            """
            select rum.miniatureId, rum.count, m.name
            from roster_unit_miniature rum
            join miniature m on m.id = rum.miniatureId
            where rum.rosterUnitId = ?
            order by m.displayOrder, m.name
            """,
            [unit["id"]],
        )]
        compositions = self.compositions(conn, unit["datasheetId"])
        selected = select_matching_composition(compositions, miniatures)
        composition_points = selected["points"] if selected else (compositions[0]["points"] if compositions else 0)
        wargear_points = conn.execute(
            """
            select coalesce(sum(rumwo.count * wo.points), 0)
            from roster_unit_miniature_wargear_option rumwo
            join roster_unit_miniature rum on rum.id = rumwo.rosterUnitMiniatureId
            join wargear_option wo on wo.id = rumwo.wargearOptionId
            where rum.rosterUnitId = ?
            """,
            [unit["id"]],
        ).fetchone()[0] or 0
        model_count = sum(item["count"] for item in miniatures)
        return {
            "id": unit["id"],
            "datasheetId": unit["datasheetId"],
            "name": unit["name"],
            "allyType": unit.get("allyType", "native"),
            "points": composition_points + wargear_points,
            "modelCount": model_count,
            "selectedCompositionId": selected["id"] if selected else None,
            "compositionLabel": selected["label"] if selected else composition_label_from_current(miniatures),
        }

    def validate(self, conn, roster, detachments, units, total_points):
        messages = []
        limit = roster.get("pointsLimit") or 0
        if limit and total_points > limit:
            messages.append({"level": "error", "text": f"Roster is {total_points - limit} points over the {limit} point limit."})
        if not detachments:
            messages.append({"level": "error", "text": "Pick a detachment."})
        if detachments and roster.get("detachmentPointsLimit") and len(detachments) > roster["detachmentPointsLimit"]:
            messages.append({"level": "error", "text": "Too many detachments for this battle size."})
        for detachment in detachments:
            allowed = conn.execute(
                """
                select 1
                from detachment_faction_keyword
                where detachmentId = ? and factionKeywordId = ?
                """,
                [detachment["id"], roster["factionKeywordId"]],
            ).fetchone()
            if not allowed:
                messages.append({"level": "error", "text": f"{detachment['name']} is not available to {roster['factionName']}."})
        duplicate_limit = roster.get("duplicateUnitLimit") or 3
        counts = {}
        for unit in units:
            counts[unit["datasheetId"]] = counts.get(unit["datasheetId"], 0) + 1
            if not unit["selectedCompositionId"]:
                messages.append({"level": "warning", "text": f"{unit['name']} does not match a known composition."})
            allowed = conn.execute(
                """
                select 1
                from datasheet_faction_keyword
                where datasheetId = ? and factionKeywordId = ?
                """,
                [unit["datasheetId"], roster["factionKeywordId"]],
            ).fetchone()
            if not allowed:
                messages.append({"level": "error", "text": f"{unit['name']} is not native to {roster['factionName']}."})
        for unit in units:
            if counts[unit["datasheetId"]] > duplicate_limit:
                messages.append({"level": "error", "text": f"{unit['name']} exceeds duplicate limit {duplicate_limit}."})
                counts[unit["datasheetId"]] = -999
        if not units:
            messages.append({"level": "warning", "text": "Roster has no units."})
        state = "invalid" if any(item["level"] == "error" for item in messages) else "valid"
        return {"state": state, "messages": messages}


def select_matching_composition(compositions, miniatures):
    current = {item["miniatureId"]: item["count"] for item in miniatures}
    for comp in compositions:
        models = comp["models"]
        model_ids = {item["miniatureId"] for item in models}
        if set(current) != model_ids:
            continue
        ok = True
        for model in models:
            count = current.get(model["miniatureId"], 0)
            if count < model["min"] or count > model["max"]:
                ok = False
                break
        if ok:
            return comp
    return None


def composition_label(models):
    pieces = []
    for model in models:
        count = str(model["min"]) if model["min"] == model["max"] else f"{model['min']}-{model['max']}"
        pieces.append(f"{count} {model['name']}")
    return " + ".join(pieces)


def composition_label_from_current(models):
    return " + ".join(f"{model['count']} {model['name']}" for model in models)


def plain_text(value):
    if not value:
        return ""
    text = str(value)
    text = text.replace("**", "").replace("■", "").replace("\n", " ")
    return " ".join(text.split())


class Handler(BaseHTTPRequestHandler):
    heretic_builder = None

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
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def fail(self, error):
        self.send_json({"error": str(error)}, status=400)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        try:
            if parsed.path == "/":
                body = PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/api/bootstrap":
                self.send_json(self.heretic_builder.bootstrap())
            elif parsed.path == "/api/detachments":
                self.send_json(self.heretic_builder.detachments(params.get("factionId", [""])[0]))
            elif parsed.path == "/api/datasheets":
                self.send_json(self.heretic_builder.datasheets(
                    params.get("factionId", [""])[0],
                    params.get("detachmentId", [""])[0],
                    params.get("q", [""])[0],
                ))
            elif parsed.path == "/api/roster":
                self.send_json(self.heretic_builder.roster(params.get("id", [""])[0]))
            elif parsed.path == "/api/unit":
                self.send_json(self.heretic_builder.unit_detail(params.get("id", [""])[0]))
            else:
                self.send_json({"error": "Not found"}, status=404)
        except Exception as error:
            self.fail(error)

    def do_POST(self):
        try:
            payload = self.read_json()
            if self.path == "/api/roster/create":
                self.send_json(self.heretic_builder.create_roster(payload))
            elif self.path == "/api/roster/delete":
                self.send_json(self.heretic_builder.delete_roster(payload["id"]))
            elif self.path == "/api/unit/add":
                self.send_json(self.heretic_builder.add_unit(payload["rosterId"], payload["datasheetId"]))
            elif self.path == "/api/unit/delete":
                self.send_json(self.heretic_builder.delete_unit(payload["id"]))
            elif self.path == "/api/unit/composition":
                self.send_json(self.heretic_builder.set_composition(payload["rosterUnitId"], payload["compositionId"]))
            elif self.path == "/api/wargear":
                self.send_json(self.heretic_builder.set_wargear(
                    payload["rosterUnitMiniatureId"],
                    payload["wargearOptionId"],
                    payload.get("count", 0),
                ))
            else:
                self.send_json({"error": "Not found"}, status=404)
        except Exception as error:
            self.fail(error)


def main():
    parser = argparse.ArgumentParser(description="Minimal read/write HereticBuilder")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=4175, help="Preferred port")
    args = parser.parse_args()
    db_path = Path(args.db).resolve()
    if not db_path.exists():
        raise SystemExit(f"Database does not exist: {db_path}")
    Handler.heretic_builder = HereticBuilder(db_path)
    server, port = find_port(args.host, args.port)
    print(f"HereticBuilder: http://{args.host}:{port}", flush=True)
    print(f"Database: {html.escape(str(db_path))}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
