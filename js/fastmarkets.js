// ==========================================================================
// fastmarkets.js — Live Market Prices view (Fastmarkets Feed_Rawmat workspace)
// ==========================================================================
import { AppState } from "./state.js";
import { fmtPct } from "./utils.js";

function fmtPrice(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

function toneClass(changePct) {
  if (changePct == null) return "";
  if (changePct > 0.005) return "pos";
  if (changePct < -0.005) return "neg";
  return "flat";
}

export function renderFastmarketsKpis(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const data = AppState.raw.fastmarkets;
  const items = data.items;
  const mids = items.filter((i) => i.mid != null);
  const changes = items.filter((i) => i.changePct != null);
  const avgChange = changes.length
    ? changes.reduce((a, b) => a + b.changePct, 0) / changes.length
    : null;
  const up = changes.filter((i) => i.changePct > 0).length;
  const down = changes.filter((i) => i.changePct < 0).length;
  const cheapest = mids.length ? mids.reduce((a, b) => (a.mid < b.mid ? a : b)) : null;
  const mostExpensive = mids.length ? mids.reduce((a, b) => (a.mid > b.mid ? a : b)) : null;

  el.innerHTML = `
    <div class="kpi-card"><div class="kpi-value">${items.length}</div><div class="kpi-label">Live price assessments</div></div>
    <div class="kpi-card"><div class="kpi-value">${up}</div><div class="kpi-label">Rising (WoW)</div></div>
    <div class="kpi-card"><div class="kpi-value">${down}</div><div class="kpi-label">Falling (WoW)</div></div>
    <div class="kpi-card"><div class="kpi-value">${avgChange != null ? fmtPct(avgChange) : "—"}</div><div class="kpi-label">Avg weekly change</div></div>
    <div class="kpi-card"><div class="kpi-value">${cheapest ? fmtPrice(cheapest.mid) : "—"}</div><div class="kpi-label">Cheapest — ${cheapest ? cheapest.description : ""}</div></div>
    <div class="kpi-card"><div class="kpi-value">${mostExpensive ? fmtPrice(mostExpensive.mid) : "—"}</div><div class="kpi-label">Priciest — ${mostExpensive ? mostExpensive.description : ""}</div></div>`;
}

export function renderFastmarketsTable(tableId, query = "") {
  const table = document.getElementById(tableId);
  if (!table) return;
  const data = AppState.raw.fastmarkets;
  let items = data.items;

  if (query) {
    const q = query.toLowerCase();
    items = items.filter((i) =>
      [i.description, i.commodity, i.location, i.incoterm, i.symbol, i.source]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(q)
    );
  }

  const rows = items
    .map((i) => {
      const cls = toneClass(i.changePct);
      const chg = i.changePct != null
        ? `<span class="${cls}">${fmtPct(i.changePct)}</span>`
        : "—";
      return `<tr>
        <td class="cell-strong">${i.commodity || "—"}</td>
        <td>${i.description || "—"}</td>
        <td>${i.location || "—"}</td>
        <td>${i.incoterm || "—"}</td>
        <td class="hist-num">${fmtPrice(i.mid)}</td>
        <td class="hist-num">${fmtPrice(i.low)}</td>
        <td class="hist-num">${fmtPrice(i.high)}</td>
        <td class="hist-num">${chg}</td>
        <td>${i.date || "—"}</td>
        <td style="color:var(--ink-500);font-size:11px;">${i.symbol || "—"}</td>
      </tr>`;
    })
    .join("");

  table.innerHTML = `
    <thead><tr>
      <th>Commodity</th><th>Assessment</th><th>Location</th><th>Incoterm</th>
      <th class="hist-num">Mid</th><th class="hist-num">Low</th><th class="hist-num">High</th>
      <th class="hist-num">WoW Δ</th><th>Date</th><th>Symbol</th>
    </tr></thead>
    <tbody>${rows}</tbody>`;
}
