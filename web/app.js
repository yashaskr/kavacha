const TOTAL = "Total Crimes Against Women";

const MATRIX_CATS = [
  "Assault",
  "Domestic Violence",
  "Dowry Related",
  "Sexual Assault",
  "Kidnapping",
  "Trafficking",
  "Eve Teasing",
  "Harassment",
  "Cyber Crime",
];

const CAT_COLORS = {
  Assault: "#0f4c5c",
  "Domestic Violence": "#1f6b4a",
  "Dowry Related": "#8a6a12",
  "Sexual Assault": "#8a3b2a",
  Kidnapping: "#3a5f8a",
  Trafficking: "#5c3d6e",
  "Eve Teasing": "#c97816",
  Harassment: "#0a7a6a",
  "Cyber Crime": "#456070",
  Other: "#6a7578",
};

let mapCrimeCardEl = null;
let mapLegendEl = null;
let latestSnapshots = [];
/** @type {null | ((selected: object) => void)} */
let applyMapYear = null;
/** @type {"city" | "station"} */
let mapMode = "city";
/** @type {Map<string, Map<number, number>>} stationKey -> year -> total cases */
let psCrimeByStation = new Map();
let psCrimeLoaded = false;
let psCrimeHasRows = false;

function splitCsvLine(line) {
  const out = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === "," && !inQuotes) {
      out.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out;
}

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) return [];
  const headers = splitCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const cells = splitCsvLine(line);
    const row = {};
    headers.forEach((h, i) => {
      row[h] = cells[i] ?? "";
    });
    return row;
  });
}

function formatCount(n) {
  return new Intl.NumberFormat("en-IN").format(Math.round(n));
}

function tierLabel(tier) {
  if (tier === "A") return "Tier A · high-trust official";
  if (tier === "B") return "Tier B · solid open aggregate";
  if (tier === "C") return "Tier C · thin / total only";
  return "Category detail only";
}

function buildSnapshots(rows) {
  const years = [...new Set(rows.map((r) => Number(r.year)))].sort((a, b) => a - b);
  return years.map((year) => {
    const yr = rows.filter((r) => Number(r.year) === year);
    const totalRow = yr.find((r) => r.crime_category_normalized === TOTAL) || null;
    const categories = yr
      .filter((r) => r.crime_category_normalized !== TOTAL)
      .map((r) => ({
        name: r.crime_category_normalized,
        value: Number(r.value),
        tier: r.quality_tier,
      }))
      .sort((a, b) => b.value - a.value);
    const categorySum = categories.reduce((s, c) => s + c.value, 0);
    return {
      year,
      total: totalRow ? Number(totalRow.value) : null,
      categorySum,
      totalTier: totalRow?.quality_tier ?? (categories.length ? categories[0].tier : null),
      completeness:
        totalRow?.completeness ?? (categories.length ? "category_detail" : null),
      userNote:
        totalRow?.user_note ||
        (categories.length
          ? "Official city total not published; figures below are published crime heads only."
          : null),
      categories,
    };
  });
}

function totalsSeries(snapshots) {
  const min = Math.min(...snapshots.map((s) => s.year));
  const max = Math.max(...snapshots.map((s) => s.year));
  const byYear = new Map(snapshots.map((s) => [s.year, s.total]));
  const out = [];
  for (let y = min; y <= max; y++) {
    out.push({ year: y, value: byYear.has(y) ? byYear.get(y) : null });
  }
  return out;
}

function prevTotalSnapshot(snapshots, year) {
  const earlier = snapshots
    .filter((s) => s.year < year && s.total != null)
    .sort((a, b) => b.year - a.year);
  return earlier[0] || null;
}

function renderChart(root, points, selectedYear, onSelect) {
  const width = 920;
  const height = 280;
  const pad = { top: 28, right: 24, bottom: 40, left: 56 };
  const known = points.filter((p) => p.value != null);
  const maxV = Math.max(...known.map((p) => p.value), 1);
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const xAt = (i) => pad.left + (i / Math.max(points.length - 1, 1)) * innerW;
  const yAt = (v) => pad.top + innerH - (v / maxV) * innerH;

  let path = "";
  let drawing = false;
  points.forEach((p, i) => {
    if (p.value == null) {
      drawing = false;
      return;
    }
    path += `${drawing ? "L" : "M"} ${xAt(i)} ${yAt(p.value)} `;
    drawing = true;
  });

  const areas = [];
  let run = [];
  const flush = () => {
    if (run.length < 2) {
      run = [];
      return;
    }
    let d = `M ${xAt(run[0].i)} ${yAt(run[0].v)}`;
    for (let k = 1; k < run.length; k++) d += ` L ${xAt(run[k].i)} ${yAt(run[k].v)}`;
    d += ` L ${xAt(run[run.length - 1].i)} ${pad.top + innerH} L ${xAt(run[0].i)} ${pad.top + innerH} Z`;
    areas.push(d);
    run = [];
  };
  points.forEach((p, i) => {
    if (p.value == null) flush();
    else run.push({ i, v: p.value });
  });
  flush();

  const ticks = [0, 1, 2, 3, 4].map((i) => Math.round((maxV / 4) * i));
  const grid = ticks
    .map((t) => {
      const y = yAt(t);
      return `<g>
        <line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${y}" y2="${y}"></line>
        <text class="axis-label" x="${pad.left - 10}" y="${y + 4}" text-anchor="end">${formatCount(t)}</text>
      </g>`;
    })
    .join("");

  const dots = points
    .map((p, i) => {
      const x = xAt(i);
      if (p.value == null) {
        return `<g>
          <line class="gap-mark" x1="${x}" x2="${x}" y1="${pad.top + 8}" y2="${height - pad.bottom - 8}"></line>
          <text class="axis-label gap-year" x="${x}" y="${height - 12}" text-anchor="middle">${p.year}</text>
        </g>`;
      }
      const y = yAt(p.value);
      const active = p.year === selectedYear;
      return `<g>
        <circle class="chart-dot ${active ? "is-active" : ""}" data-year="${p.year}" cx="${x}" cy="${y}" r="${active ? 7 : 5}"></circle>
        <text class="axis-label" x="${x}" y="${height - 12}" text-anchor="middle">${p.year}</text>
        ${active ? `<text class="chart-value" x="${x}" y="${y - 14}" text-anchor="middle">${formatCount(p.value)}</text>` : ""}
      </g>`;
    })
    .join("");

  root.innerHTML = `
    <svg class="totals-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Bengaluru City annual total crimes against women">
      ${grid}
      ${areas.map((d) => `<path class="chart-area" d="${d}"></path>`).join("")}
      <path class="chart-line" d="${path.trim()}"></path>
      ${dots}
    </svg>
    <p class="chart-caption">Official city totals where published. Dashed marks = years without a published city total (category detail may still exist below).</p>
  `;

  root.querySelectorAll(".chart-dot").forEach((el) => {
    el.addEventListener("click", () => onSelect(Number(el.getAttribute("data-year"))));
    el.setAttribute("tabindex", "0");
    el.setAttribute("role", "button");
  });
}

function renderPulse(snapshots, selected) {
  const root = document.getElementById("pulse-grid");
  const headline =
    selected.total != null ? selected.total : selected.categorySum > 0 ? selected.categorySum : null;
  const headlineKind =
    selected.total != null
      ? "Official city total"
      : selected.categorySum > 0
        ? "Sum of published heads (not an official total)"
        : "No figures";

  const perDay =
    headline != null ? (headline / 365).toFixed(1) : null;
  const prev = selected.total != null ? prevTotalSnapshot(snapshots, selected.year) : null;
  let changeHtml = `<span class="pulse-muted">No prior official total to compare</span>`;
  if (prev && selected.total != null) {
    const delta = selected.total - prev.total;
    const pct = ((delta / prev.total) * 100).toFixed(0);
    const cls = delta > 0 ? "up" : delta < 0 ? "down" : "flat";
    const sign = delta > 0 ? "+" : "";
    changeHtml = `<span class="delta delta--${cls}">${sign}${formatCount(delta)} (${sign}${pct}%)</span>
      <span class="pulse-muted">vs ${prev.year}</span>`;
  }

  const top = selected.categories[0];
  const topShare =
    top && headline
      ? `${Math.round((top.value / (selected.total ?? selected.categorySum)) * 100)}% of ${selected.total != null ? "total" : "published heads"}`
      : "—";

  root.innerHTML = `
    <article class="pulse-card pulse-card--lead">
      <p class="pulse-label">${selected.year}</p>
      <p class="pulse-num">${headline != null ? formatCount(headline) : "—"}</p>
      <p class="pulse-desc">${headlineKind}</p>
      <p class="pulse-meta">${tierLabel(selected.totalTier)}</p>
    </article>
    <article class="pulse-card">
      <p class="pulse-label">Pace</p>
      <p class="pulse-num pulse-num--sm">${perDay != null ? perDay : "—"}</p>
      <p class="pulse-desc">${perDay != null ? "reported cases per day (city-wide)" : "Need a yearly figure"}</p>
    </article>
    <article class="pulse-card">
      <p class="pulse-label">Change</p>
      <p class="pulse-num pulse-num--sm">${prev && selected.total != null ? formatCount(Math.abs(selected.total - prev.total)) : "—"}</p>
      <p class="pulse-desc">${changeHtml}</p>
    </article>
    <article class="pulse-card">
      <p class="pulse-label">Largest head</p>
      <p class="pulse-num pulse-num--sm">${top ? top.name : "—"}</p>
      <p class="pulse-desc">${top ? `${formatCount(top.value)} · ${topShare}` : "Total-only year"}</p>
    </article>
  `;
}

function renderComposition(selected) {
  const root = document.getElementById("composition-root");
  if (!selected.categories.length) {
    root.innerHTML = `
      <div class="empty-detail">
        <p><strong>${selected.year}</strong> has an official city total only.</p>
        <p>Category mix was not published for this year — so we show the total on the chart above, not a fake breakdown.</p>
      </div>`;
    return;
  }

  const denom = selected.total ?? selected.categorySum;
  const max = Math.max(...selected.categories.map((c) => c.value), 1);
  const note =
    selected.total != null
      ? `Shares use the official total of ${formatCount(selected.total)}.`
      : `No official total for ${selected.year}; shares use the sum of published heads (${formatCount(selected.categorySum)}).`;

  root.innerHTML = `
    <p class="compose-note">${note}</p>
    <ul class="compose-list">
      ${selected.categories
        .map((c) => {
          const share = denom ? (c.value / denom) * 100 : 0;
          const color = CAT_COLORS[c.name] || CAT_COLORS.Other;
          return `<li>
            <div class="cat-row">
              <span class="cat-name"><i class="swatch" style="background:${color}"></i>${c.name}</span>
              <span class="cat-val">${formatCount(c.value)} <em>${share.toFixed(0)}%</em></span>
            </div>
            <div class="cat-bar" aria-hidden="true">
              <span style="width:${(c.value / max) * 100}%; background:${color}"></span>
            </div>
          </li>`;
        })
        .join("")}
    </ul>
  `;
}

function renderMatrix(snapshots, selectedYear) {
  const root = document.getElementById("matrix-root");
  const years = snapshots.map((s) => s.year);
  const lookup = new Map();
  snapshots.forEach((s) => {
    s.categories.forEach((c) => lookup.set(`${s.year}|${c.name}`, c.value));
  });

  const rowMax = {};
  MATRIX_CATS.forEach((cat) => {
    rowMax[cat] = Math.max(
      0,
      ...years.map((y) => lookup.get(`${y}|${cat}`) || 0),
    );
  });

  const head = `<tr><th scope="row">Category</th>${years
    .map(
      (y) =>
        `<th scope="col" class="${y === selectedYear ? "is-selected" : ""}">${y}</th>`,
    )
    .join("")}</tr>`;

  const body = MATRIX_CATS.map((cat) => {
    if (rowMax[cat] <= 0) return "";
    const cells = years
      .map((y) => {
        const v = lookup.get(`${y}|${cat}`);
        if (v == null) {
          return `<td class="matrix-empty ${y === selectedYear ? "is-selected" : ""}" title="Not in published set">·</td>`;
        }
        const intensity = v / rowMax[cat];
        const bg = `rgba(15, 76, 92, ${0.12 + intensity * 0.75})`;
        const fg = intensity > 0.55 ? "#f4f7f8" : "#142226";
        return `<td class="${y === selectedYear ? "is-selected" : ""}" style="background:${bg};color:${fg}" title="${cat} ${y}: ${formatCount(v)}">${formatCount(v)}</td>`;
      })
      .join("");
    return `<tr><th scope="row">${cat}</th>${cells}</tr>`;
  }).join("");

  root.innerHTML = `<table class="matrix" aria-label="Category by year">${head}${body}</table>`;
}

function cityMetric(selected) {
  if (!selected) return { value: null, kind: "none", label: "No data" };
  if (selected.total != null) {
    return {
      value: selected.total,
      kind: "official",
      label: "Official city total",
    };
  }
  if (selected.categorySum > 0) {
    return {
      value: selected.categorySum,
      kind: "heads",
      label: "Sum of published heads",
    };
  }
  return { value: null, kind: "none", label: "No data" };
}

function maxCityMetric(snapshots) {
  let max = 1;
  snapshots.forEach((s) => {
    const m = cityMetric(s);
    if (m.value != null) max = Math.max(max, m.value);
  });
  return max;
}

function updateMapCrimeCard(selected) {
  if (!mapCrimeCardEl) return;
  const m = cityMetric(selected);
  if (mapMode === "city") {
    mapCrimeCardEl.hidden = false;
    if (m.value != null) {
      const perDay = (m.value / 365).toFixed(1);
      mapCrimeCardEl.innerHTML = `
        <p class="map-card-kicker">Bengaluru City · ${selected.year}</p>
        <p class="map-card-num">${formatCount(m.value)}</p>
        <p class="map-card-desc">${m.label} · ~${perDay} cases/day city-wide</p>
        <p class="map-card-foot">Map shade is the same everywhere — one city figure</p>
      `;
    } else {
      mapCrimeCardEl.innerHTML = `
        <p class="map-card-kicker">Bengaluru City · ${selected.year}</p>
        <p class="map-card-num">—</p>
        <p class="map-card-desc">No publishable crime figures for this year</p>
      `;
    }
  }
  if (typeof applyMapYear === "function") applyMapYear(selected);
}

function renderCrimePanel(snapshots, selectedYear, onSelect) {
  const selected = snapshots.find((s) => s.year === selectedYear);
  if (!selected) return;

  document.getElementById("crime-panel").hidden = false;
  const switchEl = document.getElementById("year-switch");
  switchEl.innerHTML = snapshots
    .map(
      (s) =>
        `<button type="button" role="option" aria-selected="${s.year === selectedYear}" class="${s.year === selectedYear ? "is-active" : ""}" data-year="${s.year}">${s.year}</button>`,
    )
    .join("");
  switchEl.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => onSelect(Number(btn.dataset.year)));
  });

  renderPulse(snapshots, selected);
  renderComposition(selected);
  renderMatrix(snapshots, selectedYear);
  updateMapCrimeCard(selected);
}

function normStationKey(name) {
  return String(name || "")
    .toLowerCase()
    .replace(/\bps\b/g, " ")
    .replace(/police\s*station/g, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function stationDisplayName(props) {
  return (
    props?.name ||
    props?.POL_STAName ||
    props?.PS_BOUNDName ||
    props?.WardName ||
    "Unnamed"
  );
}

async function loadPsCrimeCsv() {
  psCrimeByStation = new Map();
  psCrimeLoaded = true;
  psCrimeHasRows = false;
  try {
    const res = await fetch("./data/geo/ps_crime.csv");
    if (!res.ok) return;
    const rows = parseCsv(await res.text());
    rows.forEach((r) => {
      const year = Number(r.year);
      const value = Number(r.reported_cases);
      if (!Number.isFinite(year) || !Number.isFinite(value)) return;
      const cat = String(r.category || TOTAL);
      // Prefer totals; also accept bare total-like labels
      const isTotal =
        cat === TOTAL || /^total$/i.test(cat) || /total crimes against women/i.test(cat);
      if (!isTotal) return;
      const keys = [r.station_name, r.station_code].filter(Boolean).map(normStationKey);
      keys.forEach((key) => {
        if (!key) return;
        if (!psCrimeByStation.has(key)) psCrimeByStation.set(key, new Map());
        psCrimeByStation.get(key).set(year, value);
        psCrimeHasRows = true;
      });
    });
  } catch {
    // optional file
  }
}

function lookupPsCases(props, year) {
  const candidates = [
    props?.POL_STAName,
    props?.PS_BOUNDName,
    props?.name,
    props?.KGISPSCode,
    props?.PS_BOUNDCode,
  ]
    .filter(Boolean)
    .map(normStationKey);
  for (const key of candidates) {
    const byYear = psCrimeByStation.get(key);
    if (byYear && byYear.has(year)) return byYear.get(year);
  }
  return null;
}

function maxPsMetric(year) {
  let max = 1;
  psCrimeByStation.forEach((byYear) => {
    if (byYear.has(year)) max = Math.max(max, byYear.get(year));
  });
  return max;
}

function stationPopupHtml(props, selected) {
  const name = stationDisplayName(props);
  const city = cityMetric(selected);
  const local = lookupPsCases(props, selected.year);
  if (local != null) {
    return `<strong>${name}</strong>
      <div class="popup-stat">${formatCount(local)} reported (this station · ${selected.year})</div>
      <div class="popup-note">Station-level figure from ps_crime.csv — not the city total.</div>
      <div class="popup-note">City-wide same year: ${city.value != null ? formatCount(city.value) : "—"}</div>`;
  }
  if (!psCrimeHasRows) {
    return `<strong>${name}</strong>
      <div class="popup-stat">No station-level crime on file</div>
      <div class="popup-note">City-wide ${selected.year}: <strong>${city.value != null ? formatCount(city.value) : "—"}</strong> (${city.label})</div>
      <div class="popup-note">To answer “what about this PS?”, add <code>web/data/geo/ps_crime.csv</code> (RTI/BCP). See docs/ps_level_data_spec.md</div>`;
  }
  return `<strong>${name}</strong>
    <div class="popup-stat">No match in ps_crime.csv for ${selected.year}</div>
    <div class="popup-note">City-wide same year: ${city.value != null ? formatCount(city.value) : "—"}</div>`;
}

async function initReferenceMap() {
  const caption = document.getElementById("map-caption");
  const toggles = document.getElementById("layer-toggles");
  const mapEl = document.getElementById("map");
  const modeSwitch = document.getElementById("mode-switch");
  mapCrimeCardEl = document.getElementById("map-crime-card");
  mapLegendEl = document.getElementById("map-legend");
  if (!mapEl || typeof L === "undefined") {
    if (caption) caption.textContent = "Map library failed to load.";
    return;
  }

  await loadPsCrimeCsv();

  try {
    const manRes = await fetch("./data/geo/manifest.json");
    if (!manRes.ok) throw new Error("Map manifest missing — run prepare_map_layers.py");
    const manifest = await manRes.json();

    const map = L.map(mapEl, {
      scrollWheelZoom: false,
      attributionControl: true,
    }).setView([12.9716, 77.5946], 11);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · boundaries OpenCity',
      maxZoom: 19,
    }).addTo(map);

    const bounds = L.latLngBounds([]);
    let jurisdictionLayer = null;
    let stationLayer = null;
    let wardLayer = null;
    let bubble = null;
    let bubbleLabel = null;
    let currentSelected =
      [...latestSnapshots].reverse().find((s) => s.total != null) ||
      latestSnapshots[latestSnapshots.length - 1];
    const scaleMax = maxCityMetric(latestSnapshots);

    const layerInputs = {};

    for (const layer of manifest.layers) {
      const res = await fetch(`./${layer.file}`);
      if (!res.ok) {
        console.warn("layer fetch failed", layer.file, res.status);
        continue;
      }
      const geojson = await res.json();

      const leafletLayer = L.geoJSON(geojson, {
        style:
          layer.id === "police_jurisdictions"
            ? { color: "#5c2418", weight: 0.7, fillColor: "#8a3b2a", fillOpacity: 0.2 }
            : layer.id === "bbmp_wards_2023"
              ? { color: "#8a6a12", weight: 0.8, fillColor: "#c97816", fillOpacity: 0.03 }
              : undefined,
        pointToLayer:
          layer.id === "police_stations"
            ? (feature, latlng) =>
                L.circleMarker(latlng, {
                  radius: 5,
                  color: "#0a3440",
                  weight: 1.2,
                  fillColor: "#c97816",
                  fillOpacity: 0.85,
                })
            : undefined,
        onEachFeature(feature, lyr) {
          if (layer.id === "police_stations" || layer.id === "police_jurisdictions") {
            lyr.bindPopup(() => stationPopupHtml(feature.properties || {}, currentSelected));
          } else {
            const name = stationDisplayName(feature.properties || {});
            lyr.bindPopup(
              `<strong>${name}</strong><div class="popup-note">Ward boundary — not a crime count</div>`,
            );
          }
        },
      });

      if (leafletLayer.getBounds().isValid()) bounds.extend(leafletLayer.getBounds());
      if (layer.id === "police_jurisdictions") jurisdictionLayer = leafletLayer;
      if (layer.id === "police_stations") stationLayer = leafletLayer;
      if (layer.id === "bbmp_wards_2023") wardLayer = leafletLayer;

      const label = document.createElement("label");
      label.innerHTML = `<input type="checkbox" data-layer="${layer.id}" /> ${layer.label}`;
      toggles.appendChild(label);
      const input = label.querySelector("input");
      layerInputs[layer.id] = input;
      input.addEventListener("change", () => {
        if (input.checked) map.addLayer(leafletLayer);
        else map.removeLayer(leafletLayer);
      });
    }

    if (bounds.isValid()) {
      map.fitBounds(bounds.pad(0.04));
      const center = bounds.getCenter();
      bubble = L.circleMarker(center, {
        radius: 28,
        color: "#5c2418",
        weight: 2,
        fillColor: "#8a3b2a",
        fillOpacity: 0.55,
        interactive: false,
      });
      bubbleLabel = L.marker(center, {
        interactive: false,
        icon: L.divIcon({
          className: "city-bubble-label",
          html: "",
          iconSize: [120, 40],
          iconAnchor: [60, 20],
        }),
      });
    }

    const setLayerOn = (id, on) => {
      const layer =
        id === "police_jurisdictions"
          ? jurisdictionLayer
          : id === "police_stations"
            ? stationLayer
            : id === "bbmp_wards_2023"
              ? wardLayer
              : null;
      const input = layerInputs[id];
      if (!layer || !input) return;
      input.checked = on;
      if (on) map.addLayer(layer);
      else map.removeLayer(layer);
    };

    const restyleStations = (selected) => {
      if (!stationLayer) return;
      const year = selected.year;
      const maxLocal = maxPsMetric(year);
      stationLayer.eachLayer((lyr) => {
        if (typeof lyr.setStyle !== "function" || !lyr.feature) return;
        const local = lookupPsCases(lyr.feature.properties || {}, year);
        if (mapMode !== "station") {
          lyr.setStyle({
            radius: 4,
            fillColor: "#c97816",
            fillOpacity: 0.35,
            color: "#0a3440",
            weight: 1,
          });
          return;
        }
        if (local == null) {
          lyr.setStyle({
            radius: 5,
            fillColor: "#9aa4a8",
            fillOpacity: 0.55,
            color: "#3a4a4f",
            weight: 1,
          });
          return;
        }
        const t = local / maxLocal;
        lyr.setStyle({
          radius: 6 + t * 14,
          fillColor: "#8a3b2a",
          fillOpacity: 0.55 + t * 0.35,
          color: "#5c2418",
          weight: 1.5,
        });
      });
    };

    const applyMode = () => {
      if (mapMode === "city") {
        setLayerOn("police_jurisdictions", true);
        setLayerOn("police_stations", false);
        setLayerOn("bbmp_wards_2023", false);
        if (bubble && !map.hasLayer(bubble)) bubble.addTo(map);
        if (bubbleLabel && !map.hasLayer(bubbleLabel)) bubbleLabel.addTo(map);
      } else {
        setLayerOn("police_jurisdictions", true);
        setLayerOn("police_stations", true);
        setLayerOn("bbmp_wards_2023", false);
        if (bubble && map.hasLayer(bubble)) map.removeLayer(bubble);
        if (bubbleLabel && map.hasLayer(bubbleLabel)) map.removeLayer(bubbleLabel);
        // lighten city fill so stations read as the focus
        if (jurisdictionLayer) {
          jurisdictionLayer.setStyle({
            color: "#5c2418",
            weight: 0.6,
            fillColor: "#8a3b2a",
            fillOpacity: 0.08,
          });
        }
      }
    };

    applyMapYear = (selected) => {
      currentSelected = selected;
      const m = cityMetric(selected);
      const t = m.value == null ? 0 : m.value / scaleMax;
      const fillOpacity = m.value == null ? 0.05 : 0.12 + t * 0.55;
      const fillColor = m.kind === "heads" ? "#c97816" : "#8a3b2a";
      const edge = m.kind === "heads" ? "#8a6a12" : "#5c2418";

      if (mapMode === "city" && jurisdictionLayer) {
        jurisdictionLayer.setStyle({
          color: edge,
          weight: 0.75,
          fillColor,
          fillOpacity,
        });
      }

      if (mapMode === "city" && bubble) {
        const r = m.value == null ? 10 : 16 + t * 42;
        bubble.setRadius(r);
        bubble.setStyle({
          fillColor,
          color: edge,
          fillOpacity: 0.5 + t * 0.35,
        });
      }
      if (mapMode === "city" && bubbleLabel) {
        bubbleLabel.setIcon(
          L.divIcon({
            className: "city-bubble-label",
            html: m.value == null ? "" : formatCount(m.value),
            iconSize: [140, 44],
            iconAnchor: [70, 22],
          }),
        );
      }

      restyleStations(selected);

      if (mapLegendEl) {
        mapLegendEl.hidden = false;
        if (mapMode === "city") {
          mapLegendEl.innerHTML = `
            <strong>City pressure</strong>
            Darker / larger bubble = higher city-wide figure
            <div class="map-legend-scale" aria-hidden="true"></div>
            <div class="map-legend-labels"><span>Lower</span><span>Peak (${formatCount(scaleMax)})</span></div>
            <p style="margin:.45rem 0 0">Same shade on every jurisdiction.</p>`;
        } else if (psCrimeHasRows) {
          mapLegendEl.innerHTML = `
            <strong>Station detail · ${selected.year}</strong>
            Larger / darker dots = higher PS count in ps_crime.csv
            <p style="margin:.45rem 0 0">Grey dots = no local row for this year. City total is separate.</p>`;
        } else {
          mapLegendEl.innerHTML = `
            <strong>Station detail · waiting on data</strong>
            Dots are station locations. Click one to see the city-wide figure and what’s missing.
            <p style="margin:.45rem 0 0">Add <code>ps_crime.csv</code> to size dots by real PS counts.</p>`;
        }
      }

      if (mapCrimeCardEl) {
        if (mapMode === "city") {
          // card already set by updateMapCrimeCard body before this hook
        } else {
          mapCrimeCardEl.hidden = false;
          mapCrimeCardEl.innerHTML = psCrimeHasRows
            ? `<p class="map-card-kicker">Station mode · ${selected.year}</p>
               <p class="map-card-num">${formatCount(m.value ?? 0)}</p>
               <p class="map-card-desc">City-wide context (not a station)</p>
               <p class="map-card-foot">Dot size = PS file where matched</p>`
            : `<p class="map-card-kicker">Station mode · ${selected.year}</p>
               <p class="map-card-num">PS data needed</p>
               <p class="map-card-desc">City-wide: ${m.value != null ? formatCount(m.value) : "—"}</p>
               <p class="map-card-foot">Click a station · or add ps_crime.csv</p>`;
        }
      }

      caption.textContent = psCrimeHasRows
        ? `Dual grain: city aggregates + ${psCrimeByStation.size} station keys in ps_crime.csv.`
        : `City pressure is live. Station mode is ready — awaiting web/data/geo/ps_crime.csv (see docs/ps_level_data_spec.md).`;
    };

    modeSwitch?.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        mapMode = btn.dataset.mode === "station" ? "station" : "city";
        modeSwitch.querySelectorAll("button").forEach((b) => {
          b.classList.toggle("is-active", b === btn);
        });
        applyMode();
        if (currentSelected) {
          // refresh card footers for mode
          if (mapMode === "city") updateMapCrimeCard(currentSelected);
          else applyMapYear(currentSelected);
        }
      });
    });

    applyMode();
    setTimeout(() => map.invalidateSize(), 80);

    if (currentSelected) updateMapCrimeCard(currentSelected);
  } catch (err) {
    caption.innerHTML = `<span class="status status--error">${err.message}</span>`;
  }
}

async function main() {
  const chartRoot = document.getElementById("chart-root");
  try {
    const res = await fetch("./data/crime_annual_bengaluru_city.csv");
    if (!res.ok) throw new Error("Failed to load city dataset");
    const rows = parseCsv(await res.text());
    const snapshots = buildSnapshots(rows);
    latestSnapshots = snapshots;
    const points = totalsSeries(snapshots);

    const latest = [...snapshots].reverse().find((s) => s.total != null);
    let selectedYear = latest?.year ?? snapshots[snapshots.length - 1]?.year;

    if (latest) {
      const hero = document.getElementById("hero-stat");
      hero.hidden = false;
      document.getElementById("hero-stat-num").textContent = formatCount(latest.total);
      document.getElementById("hero-stat-label").textContent =
        `reported cases city-wide in ${latest.year}`;
    }

    const paint = () => {
      renderChart(chartRoot, points, selectedYear, (y) => {
        selectedYear = y;
        paint();
      });
      renderCrimePanel(snapshots, selectedYear, (y) => {
        selectedYear = y;
        paint();
      });
    };
    paint();
  } catch (err) {
    chartRoot.innerHTML = `<p class="status status--error">${err.message}. Serve this folder over HTTP after <code>python -m src.cli clean</code>.</p>`;
  }

  await initReferenceMap();
}

main();
