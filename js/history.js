// ==========================================================================
// history.js — Historical Data view: 12-month price history per material
// ==========================================================================
import { AppState } from "./state.js";
import { cssVar, fmtUSD } from "./utils.js";

const instances = {};
const PALETTE = ["#005BAC", "#00A3FF", "#16A34A", "#F59E0B", "#DC2626", "#7C3AED"];

function destroy(id) {
  if (instances[id]) {
    instances[id].destroy();
    delete instances[id];
  }
}

function ctx(id) {
  if (typeof Chart === "undefined") return null;
  const el = document.getElementById(id);
  return el ? el.getContext("2d") : null;
}

function gradientFill(chartCtx, hex, alphaTop = 0.32, alphaBottom = 0.02) {
  try {
    const { chartArea } = chartCtx.chart;
    if (!chartArea) return hex + "22";
    const g = chartCtx.chart.ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
    g.addColorStop(0, hexToRgba(hex, alphaTop));
    g.addColorStop(1, hexToRgba(hex, alphaBottom));
    return g;
  } catch {
    return hex + "22";
  }
}

function hexToRgba(hex, alpha) {
  const v = hex.replace("#", "");
  const r = parseInt(v.substring(0, 2), 16), g = parseInt(v.substring(2, 4), 16), b = parseInt(v.substring(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function baseGrid() {
  return { color: cssVar("--ink-200"), drawBorder: false };
}
function baseTicks() {
  return { color: cssVar("--ink-500"), font: { size: 11 } };
}

// ---------------------------------------------------------------------------
// Material selector (populated once from the full product list)
// ---------------------------------------------------------------------------
export function initHistorySelect(selectId, onChange) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  const list = AppState.raw.products.products;
  sel.innerHTML = list
    .map((p) => `<option value="${p.id}">${p.product}</option>`)
    .join("");
  sel.addEventListener("change", () => onChange(sel.value));
}

// ---------------------------------------------------------------------------
// 12-month price trend for a single (selectable) material
// ---------------------------------------------------------------------------
export function renderHistoryChart(canvasId, materialId) {
  const c = ctx(canvasId);
  if (!c) return;
  destroy(canvasId);

  const { months, series } = AppState.raw.history;
  const products = AppState.raw.products.products;
  const p = products.find((x) => x.id === materialId) || products[0];
  if (!p) return;

  const data = series[p.id] || [];
  const vals = data.map((v) => v); // preserve nulls for gaps

  instances[canvasId] = new Chart(c, {
    type: "line",
    data: {
      labels: months,
      datasets: [{
        label: p.product,
        data: vals,
        borderColor: PALETTE[0],
        backgroundColor: (context) => gradientFill(context, PALETTE[0], 0.3, 0.02),
        borderWidth: 3,
        fill: true,
        tension: 0.4,
        spanGaps: true,
        pointRadius: 4,
        pointBackgroundColor: PALETTE[0],
        pointBorderColor: "#fff",
        pointBorderWidth: 1.5,
        pointHoverRadius: 6,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: true, position: "bottom", labels: { boxWidth: 8, boxHeight: 8, usePointStyle: true, padding: 12, font: { size: 11 } } },
        tooltip: { callbacks: { label: (t) => ` ${fmtUSD(t.parsed.y)}/MT` } },
      },
      scales: {
        x: { grid: { display: false }, ticks: baseTicks() },
        y: { grid: baseGrid(), ticks: { ...baseTicks(), callback: (v) => "$" + v } },
      },
    },
  });
}

// ---------------------------------------------------------------------------
// Portfolio monthly average (12-month history across all filtered materials)
// ---------------------------------------------------------------------------
export function renderHistoryAvg(canvasId) {
  const c = ctx(canvasId);
  if (!c) return;
  destroy(canvasId);

  const { months, series } = AppState.raw.history;
  const list = AppState.filtered;
  const avgSeries = months.map((_, i) => {
    const vals = list.map((p) => (series[p.id] || [])[i]).filter((v) => v != null);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  });

  instances[canvasId] = new Chart(c, {
    type: "line",
    data: {
      labels: months,
      datasets: [{
        label: "Portfolio Avg",
        data: avgSeries,
        borderColor: "#005BAC",
        backgroundColor: (context) => gradientFill(context, "#005BAC", 0.32, 0.02),
        borderWidth: 3,
        fill: true,
        tension: 0.4,
        spanGaps: true,
        pointRadius: 3,
        pointBackgroundColor: "#005BAC",
        pointHoverRadius: 6,
        pointHoverBorderColor: "#fff",
        pointHoverBorderWidth: 2,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (t) => ` ${fmtUSD(t.parsed.y)}/MT avg` } } },
      scales: {
        x: { grid: { display: false }, ticks: { ...baseTicks(), maxRotation: 45, minRotation: 45 } },
        y: { grid: baseGrid(), ticks: { ...baseTicks(), callback: (v) => "$" + v } },
      },
    },
  });
}

// ---------------------------------------------------------------------------
// Month-by-month historical data table (material × 12 months)
// ---------------------------------------------------------------------------
export function renderHistoryTable(tableId, query = "") {
  const table = document.getElementById(tableId);
  if (!table) return;
  const { months, series } = AppState.raw.history;

  let list = AppState.filtered;
  if (query) {
    const q = query.toLowerCase();
    list = list.filter((p) =>
      (p.product || "").toLowerCase().includes(q) || String(p.hsCode || "").includes(q)
    );
  }

  const body = list
    .map((p) => {
      const vals = series[p.id] || [];
      const cells = months
        .map((_, i) => {
          const v = vals[i];
          return `<td class="hist-num">${v != null ? fmtUSD(v, 0) : "—"}</td>`;
        })
        .join("");
      return `<tr><td class="cell-strong">${p.product}</td>${cells}</tr>`;
    })
    .join("");

  const head = `<thead><tr><th>Material</th>${months.map((m) => `<th class="hist-num">${m}</th>`).join("")}</tr></thead>`;
  table.innerHTML = `${head}<tbody>${body}</tbody>`;
}
