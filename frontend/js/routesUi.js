// The "choose a route" sheet and the route lines on the map.
//
//   const routesUi = createRoutesUi({ map, sheet, handle, message, list, notice, onChoose });
//   routesUi.showLoading();                 // sheet opens straight away
//   await routesUi.show(result.routes, { notice: "optional warning text" });
//   routesUi.showError("Something went wrong");
//   routesUi.clear();                       // hide the sheet and the lines
//
// The sheet can be dragged down by its handle to collapse into a small bar,
// and dragged (or tapped) back up.
//
// Every route is walking only. Each row shows the walking time, the distance
// and a safety shield coloured by the route's safety score (0-100).

// Shield colours: green above 65, orange 45-65, red below 45.
// Grey is used when a route has no safety score at all.
const BAND_COLOURS = {
  green: "#2e9e44",
  orange: "#f28a1e",
  red: "#d32f2f",
  unknown: "#8a8a8a",
};

export function safetyBand(score) {
  if (typeof score !== "number" || !Number.isFinite(score)) return "unknown";
  if (score > 65) return "green";
  if (score >= 45) return "orange";
  return "red";
}

function formatDuration(seconds) {
  const minutes = Math.max(1, Math.round(seconds / 60));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} h ${rest} min` : `${hours} h`;
}

function formatMiles(meters) {
  const miles = meters / 1609.344;
  if (miles < 0.1) return "<0.1 miles";
  return `${miles.toFixed(1)} miles`;
}

const SVG_NS = "http://www.w3.org/2000/svg";

function svg(viewBox, className, markup) {
  const el = document.createElementNS(SVG_NS, "svg");
  el.setAttribute("viewBox", viewBox);
  el.setAttribute("class", className);
  el.setAttribute("aria-hidden", "true");
  el.innerHTML = markup; // fixed strings written here, never user input
  return el;
}

function walkerIcon() {
  return svg(
    "0 0 48 48",
    "route-mode",
    `<g fill="none" stroke="currentColor" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round">
       <path d="M26 15 21 27" />
       <path d="M21 27 28 34 29 44" />
       <path d="M21 27 17 35 11 41" />
       <path d="M26 15 32 22 38 22" />
       <path d="M26 15 19 21 15 27" />
     </g>
     <circle cx="27.5" cy="7.5" r="4" fill="currentColor" />`
  );
}

function shieldIcon() {
  return svg(
    "0 0 24 24",
    "route-shield-icon",
    `<path d="M12 1.8 3.6 5v6.2c0 5.2 3.5 9.8 8.4 11 4.9-1.2 8.4-5.8 8.4-11V5L12 1.8Z" fill="currentColor" />
     <path d="m7.8 12.2 2.9 2.9 5.6-6" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />`
  );
}

export function createRoutesUi({ map, sheet, handle, message, list, notice, onChoose }) {
  if (!map || !sheet || !handle || !message || !list || !notice) {
    throw new Error(
      "home.html is missing part of the routes sheet (routes-sheet, routes-handle, routes-message, routes-list, routes-notice)"
    );
  }

  let routes = [];
  let lines = new Map(); // route id -> google.maps.Polyline
  let rows = new Map(); // route id -> row button
  let selectedId = null;
  let showToken = 0;
  let boundsById = new Map(); // route id -> LatLngBounds
  let SymbolPath = null; // filled in by show() once Google's core library is loaded

  // White direction arrows repeated along the chosen route, like Google Maps
  function arrowIcons() {
    return [
      {
        icon: {
          path: SymbolPath.FORWARD_CLOSED_ARROW,
          scale: 2.4,
          fillColor: "#ffffff",
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 1,
        },
        offset: "24px",
        repeat: "56px",
      },
    ];
  }

  // Fit the given bounds into the part of the map not covered by the search
  // card, buttons or the routes sheet.
  function fit(bounds) {
    const mapBox = map.getDiv().getBoundingClientRect();
    const sheetBox = sheet.getBoundingClientRect();
    map.fitBounds(bounds, {
      top: 230,
      bottom: Math.max(0, mapBox.bottom - sheetBox.top) + 24,
      left: 40,
      right: 40,
    });
  }

  // ---------- Collapsing the sheet ----------
  let collapsed = false;

  function collapsedOffset() {
    return Math.max(0, sheet.offsetHeight - handle.offsetHeight);
  }

  function setOffset(px, animate) {
    sheet.style.transition = animate ? "transform 0.25s ease" : "none";
    sheet.style.transform = px ? `translateY(${px}px)` : "";
  }

  function setCollapsed(on) {
    collapsed = on;
    setOffset(on ? collapsedOffset() : 0, true);
    handle.setAttribute("aria-expanded", String(!on));
    handle.setAttribute("aria-label", on ? "Show routes" : "Hide routes");
  }

  let drag = null;

  handle.addEventListener("pointerdown", (event) => {
    drag = {
      startY: event.clientY,
      startOffset: collapsed ? collapsedOffset() : 0,
      max: collapsedOffset(),
      moved: false,
    };
    handle.setPointerCapture(event.pointerId);
  });

  handle.addEventListener("pointermove", (event) => {
    if (!drag) return;
    const dy = event.clientY - drag.startY;
    if (Math.abs(dy) > 4) drag.moved = true;
    if (!drag.moved) return;
    const offset = Math.min(drag.max, Math.max(0, drag.startOffset + dy));
    setOffset(offset, false);
  });

  function endDrag(event) {
    if (!drag) return;
    const { startY, startOffset, max, moved } = drag;
    drag = null;

    if (!moved) {
      setCollapsed(!collapsed); // a plain tap toggles
      return;
    }

    const offset = Math.min(max, Math.max(0, startOffset + (event.clientY - startY)));
    // Snap to whichever end it was dragged closer to (with a little leaning
    // in the direction of the drag).
    setCollapsed(collapsed ? offset > max * 0.7 : offset > max * 0.3);
  }

  handle.addEventListener("pointerup", endDrag);
  handle.addEventListener("pointercancel", endDrag);

  // ---------- Resetting ----------
  // Removes the lines and rows but leaves the sheet where it is.
  function reset() {
    for (const line of lines.values()) line.setMap(null);
    lines = new Map();
    rows = new Map();
    boundsById = new Map();
    routes = [];
    selectedId = null;
    list.replaceChildren();
    notice.textContent = "";
    notice.hidden = true;
    message.textContent = "";
    message.hidden = true;
    message.classList.remove("error");
  }

  function open() {
    sheet.hidden = false;
    collapsed = false;
    setOffset(0, false);
    handle.setAttribute("aria-expanded", "true");
    handle.setAttribute("aria-label", "Hide routes");
  }

  function clear() {
    showToken++; // a show() still waiting on Google is now out of date
    reset();
    sheet.hidden = true;
    collapsed = false;
    setOffset(0, false);
  }

  // Sheet opens straight away with placeholder rows while routes load
  function showLoading() {
    showToken++;
    reset();
    open();
    message.textContent = "Finding walking routes…";
    message.hidden = false;

    for (let i = 0; i < 3; i++) {
      const item = document.createElement("li");
      item.className = "route-item route-skeleton";
      item.innerHTML =
        `<span class="sk sk-icon"></span>` +
        `<span class="sk-lines"><span class="sk sk-line"></span><span class="sk sk-line short"></span></span>` +
        `<span class="sk sk-shield"></span>`;
      list.appendChild(item);
    }
  }

  function showError(text) {
    showToken++;
    reset();
    open();
    message.textContent = text || "Couldn't get routes";
    message.classList.add("error");
    message.hidden = false;
  }

  function select(id, { announce = true, zoom = false } = {}) {
    selectedId = id;

    // The chosen route is the bold line with arrows; the others fade back.
    for (const [routeId, line] of lines) {
      const on = routeId === id;
      line.setOptions({
        strokeWeight: on ? 9 : 5,
        strokeOpacity: on ? 1 : 0.45,
        zIndex: on ? 10 : 1,
        icons: on ? arrowIcons() : [],
      });
    }

    if (zoom && boundsById.has(id)) fit(boundsById.get(id));

    for (const [routeId, row] of rows) {
      const on = routeId === id;
      row.classList.toggle("selected", on);
      row.setAttribute("aria-selected", String(on));
    }

    if (announce) {
      const route = routes.find((r) => r.id === id);
      if (route) onChoose?.(route);
    }
  }

  function buildRow(route) {
    const band = safetyBand(route.safety);
    const colour = BAND_COLOURS[band];

    const item = document.createElement("li");
    item.className = "route-item";

    const row = document.createElement("button");
    row.type = "button";
    row.className = "route-row";
    row.setAttribute("role", "option");
    row.dataset.band = band;

    const info = document.createElement("span");
    info.className = "route-info";

    const time = document.createElement("span");
    time.className = "route-time";
    time.textContent = formatDuration(route.seconds);
    info.appendChild(time);

    const distance = document.createElement("span");
    distance.className = "route-distance";
    distance.textContent = formatMiles(route.meters);
    info.appendChild(distance);

    if (route.label) {
      const tag = document.createElement("span");
      tag.className = "route-tag";
      tag.textContent = route.label;
      info.appendChild(tag);
    }

    const safety = document.createElement("span");
    safety.className = "route-safety";
    safety.style.color = colour;
    safety.appendChild(shieldIcon());

    const score = document.createElement("span");
    score.className = "route-score";
    score.textContent = band === "unknown" ? "–" : String(Math.round(route.safety));
    safety.appendChild(score);

    const label =
      band === "unknown"
        ? "safety not verified"
        : `safety ${Math.round(route.safety)} out of 100`;
    row.setAttribute(
      "aria-label",
      `${route.label || "Route"}, ${formatDuration(route.seconds)}, ${formatMiles(route.meters)}, ${label}`
    );

    row.append(walkerIcon(), info, safety);
    row.addEventListener("click", () => select(route.id, { zoom: true }));

    item.appendChild(row);
    rows.set(route.id, row);
    return item;
  }

  async function show(newRoutes, { notice: noticeText = "" } = {}) {
    const token = ++showToken;
    if (!newRoutes?.length) return;

    const core = await google.maps.importLibrary("core");
    const { LatLngBounds } = core;
    SymbolPath = core.SymbolPath;
    const { Polyline } = await google.maps.importLibrary("maps");
    if (token !== showToken) return; // cleared or replaced while loading

    reset(); // swaps the loading rows for the real ones in one go
    routes = newRoutes;
    const bounds = new LatLngBounds();

    for (const route of routes) {
      const line = new Polyline({
        map,
        path: route.pts,
        strokeColor: BAND_COLOURS[safetyBand(route.safety)],
        strokeOpacity: 0.55,
        strokeWeight: 5,
        zIndex: 1,
      });
      line.addListener("click", () => select(route.id));
      lines.set(route.id, line);

      const routeBounds = new LatLngBounds();
      for (const point of route.pts) {
        bounds.extend(point);
        routeBounds.extend(point);
      }
      boundsById.set(route.id, routeBounds);
      list.appendChild(buildRow(route));
    }

    if (noticeText) {
      notice.textContent = noticeText;
      notice.hidden = false;
    }

    open();
    select(routes[0].id);

    // Show all routes first; tapping one zooms in on it
    fit(bounds);
  }

  return { show, showLoading, showError, clear, select };
}