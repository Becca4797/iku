import { supabase } from "/js/supabaseClient.js";
import { logOut } from "/js/auth.js";
import { GOOGLE_MAPS_API_KEY } from "/js/config.js";
import {
  getShowOpenEstablishments,
  setShowOpenEstablishments,
} from "/js/mapSettings.js";
import { isOnRoute, setOnRoute, onRouteChange } from "/js/routeState.js";

// Roughly King's Cross / Bloomsbury, London
const LONDON_CENTRE = { lat: 51.5295, lng: -0.1245 };

const mapError = document.getElementById("map-error");

function showMapError(text) {
  mapError.textContent = text;
  mapError.hidden = false;
}

// ---------- Helpers ----------
function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error(`${label} timed out after ${ms / 1000}s`)), ms)
    ),
  ]);
}

// If Supabase ends the session (log out, revoked token), go back to login
supabase.auth.onAuthStateChange((event) => {
  if (event === "SIGNED_OUT") {
    window.location.replace("/pages/login.html");
  }
});

// ---------- Google Maps ----------
function loadGoogleMaps(key) {
  return new Promise((resolve, reject) => {
    if (window.google && window.google.maps) return resolve();
    window.__gmapsReady = resolve;
    const script = document.createElement("script");
    script.src =
      "https://maps.googleapis.com/maps/api/js" +
      `?key=${encodeURIComponent(key)}&v=weekly&loading=async&callback=__gmapsReady`;
    script.async = true;
    script.onerror = () => reject(new Error("Google Maps script failed to load"));
    document.head.appendChild(script);
  });
}

// ---------- Destination + start ----------
// Holds the chosen destination and start. As soon as both are set, asks the
// back end for routes. (Drawing them on the map comes next.)
const routeStatus = document.getElementById("route-status");

function showStatus(text, kind = "info") {
  if (!routeStatus) {
    if (text) console.log("[iku] status:", text);
    return;
  }
  routeStatus.textContent = text;
  routeStatus.dataset.kind = kind;
  routeStatus.hidden = !text;
}

function describeRoutes(result) {
  const routes = result.routes || [];

  if (!routes.length) {
    const reason = result.errors?.[0] ? ` (${result.errors[0]})` : "";
    return { text: `No walking routes found${reason}`, kind: "error" };
  }

  const first = routes[0];
  const minutes = Math.round(first.seconds / 60);
  const km = (first.meters / 1000).toFixed(1);
  const summary = `${first.label}: ${minutes} min, ${km} km`;

  if (result.status === "unverified_only") {
    return {
      text: `No route passed the safety checks. ${routes.length} unverified alternative(s). ${summary}`,
      kind: "error",
    };
  }

  return { text: `${routes.length} route(s) found. ${summary}`, kind: "info" };
}

async function setupTrip(map) {
  // Loaded here (not at the top of the file) so that a problem with these
  // files can never stop the map itself from appearing.
  const { createPlaceField } = await import("/js/placeField.js");
  const { fetchRoutes } = await import("/js/routesApi.js");
  const { createRoutesUi } = await import("/js/routesUi.js");

  const startInput = document.getElementById("start-input");
  const destInput = document.getElementById("search-input");
  const startForm = document.getElementById("start-form");
  const destForm = document.getElementById("search-form");
  const home = document.querySelector(".home");

  if (!startInput || !destInput || !startForm || !destForm) {
    throw new Error(
      "home.html is missing the start/destination inputs (start-input, search-input, start-form, search-form)"
    );
  }

  let start = null;
  let destination = null;
  let latestRequest = 0;
  let controller = null;
  let startField = null;

  // The "choose a route" sheet and the route lines on the map
  const routesUi = createRoutesUi({
    map,
    sheet: document.getElementById("routes-sheet"),
    handle: document.getElementById("routes-handle"),
    message: document.getElementById("routes-message"),
    list: document.getElementById("routes-list"),
    notice: document.getElementById("routes-notice"),
    onChoose: (route) =>
      window.dispatchEvent(new CustomEvent("iku:route-chosen", { detail: route })),
  });

  function clearResults() {
    latestRequest++; // any request still in flight is now out of date
    controller?.abort();
    showStatus("");
    routesUi.clear();
    setOnRoute(false); // no route wanted any more, so the bell hides Reroute
  }

  async function findRoutes() {
    if (!start || !destination) return;

    setOnRoute(true); // a route is wanted, so the bell shows Reroute
    const thisRequest = ++latestRequest;
    controller?.abort();
    controller = new AbortController();

    // Open the routes sheet straight away; it fills in when routes arrive
    showStatus("");
    routesUi.showLoading();

    // Show both points on screen, above the sheet
    const { LatLngBounds } = await google.maps.importLibrary("core");
    if (thisRequest !== latestRequest) return;
    const bounds = new LatLngBounds();
    bounds.extend(start);
    bounds.extend(destination);
    const sheetHeight = document.getElementById("routes-sheet")?.offsetHeight ?? 0;
    map.fitBounds(bounds, { top: 230, bottom: sheetHeight + 24, left: 40, right: 40 });

    try {
      const result = await fetchRoutes(start, destination, "balanced", controller.signal);
      if (thisRequest !== latestRequest) return; // user changed something meanwhile

      console.log("[iku] routes:", result);
      const { text, kind } = describeRoutes(result);

      if (result.routes?.length) {
        showStatus(""); // the routes sheet takes over from the status line
        await routesUi.show(result.routes, {
          notice:
            result.status === "unverified_only"
              ? "None of these routes passed our safety checks, so their safety isn't verified."
              : "",
        });
      } else {
        routesUi.showError(text);
      }

      window.dispatchEvent(new CustomEvent("iku:routes-ready", { detail: result }));
    } catch (error) {
      if (error.name === "AbortError" || thisRequest !== latestRequest) return;
      console.error("Route request failed:", error);
      routesUi.showError(error.message || "Could not get routes");
    }
  }

  // Ask the browser for the user's position and use it as the start.
  function useCurrentLocation() {
    if (!window.isSecureContext || !navigator.geolocation) {
      showStatus(
        "Current location needs a secure (https) connection. Please type a starting point instead.",
        "error"
      );
      startInput.focus();
      return;
    }

    showStatus("Getting your location…");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        showStatus("");
        startField?.setPlace({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          address: "Current location",
        });
      },
      (err) => {
        const denied = err.code === err.PERMISSION_DENIED;
        showStatus(
          denied
            ? "Location permission was denied. Please type a starting point instead."
            : "Couldn't get your location. Please type a starting point instead.",
          "error"
        );
        startInput.focus();
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  startField = await createPlaceField({
    form: startForm,
    input: startInput,
    quickOptions: [{ label: "Use my current location", onPick: useCurrentLocation }],
    // Only keep the buttons pushed down while the start dropdown is showing
    onSuggestionsToggle: (open) => home?.classList.toggle("start-open", open),
    onSelect: (place) => {
      start = place;
      window.dispatchEvent(new CustomEvent("iku:start-selected", { detail: { ...place } }));
      findRoutes();
    },
    onClear: () => { start = null; clearResults(); },
  });

  await createPlaceField({
    form: destForm,
    input: destInput,
    onSelect: (place) => {
      destination = place;
      window.dispatchEvent(new CustomEvent("iku:destination-selected", { detail: { ...place } }));

      // Now ask where they're starting from
      startForm.hidden = false;
      home?.classList.add("trip-open");

      if (start) {
        findRoutes();
      } else {
        map.panTo(place);
        map.setZoom(16);
        startInput.focus(); // opens the "Use my current location" shortcut
      }
    },
    onClear: () => { destination = null; clearResults(); },
  });
}

// Google calls this if the key is rejected (wrong key, restriction, billing)
window.gm_authFailure = () => {
  showMapError("The map couldn't load. Check the Google Maps key and billing.");
};

async function loadMap() {
  let map;
  try {
    console.log("[iku] loading Google Maps script");
    await withTimeout(loadGoogleMaps(GOOGLE_MAPS_API_KEY), 15000, "Google Maps script");
    const { Map } = await withTimeout(google.maps.importLibrary("maps"), 15000, "Maps library");
    map = new Map(document.getElementById("map"), {
      center: LONDON_CENTRE,
      zoom: 15,
      mapTypeId: "hybrid",
      disableDefaultUI: true, // we draw our own buttons
      gestureHandling: "greedy",
      clickableIcons: false,
    });
  } catch (err) {
    console.error(err);
    showMapError("The map couldn't load: " + err.message);
    return map;
  }

  // Start/destination is set up separately: if it fails, the map still works.
  setupTrip(map).catch((error) => {
    console.error("Start/destination setup failed:", error);
    showStatus("Start/destination search failed to load: " + error.message, "error");
  });

  return map;
}

async function start() {
  let map; // filled in by loadMap() below; buttons check it before using it

  // Layers button: switch between satellite-with-labels and the standard map
  document.getElementById("layers-btn")?.addEventListener("click", () => {
    if (!map) return;
    map.setMapTypeId(map.getMapTypeId() === "hybrid" ? "roadmap" : "hybrid");
  });

  // Pressing Enter in the start/destination boxes must never reload the page
  for (const id of ["start-form", "search-form"]) {
    document.getElementById(id)?.addEventListener("submit", (event) => event.preventDefault());
  }

  // ---------- Bell, flag and bookmark toggles ----------
  // Opening one closes the others so they never overlap.
  const bellBtn = document.getElementById("bell-btn");
  const alertActions = document.getElementById("alert-actions");
  const flagBtn = document.getElementById("routes-btn");
  const reportPanel = document.getElementById("report-panel");
  const safeBtn = document.getElementById("safe-areas-btn");
  const safePanel = document.getElementById("safe-panel");
  const dangerPanel = document.getElementById("danger-panel");

  function setBell(on) {
    alertActions.hidden = !on;
    bellBtn.setAttribute("aria-pressed", String(on));
  }

  function setReport(on) {
    reportPanel.hidden = !on;
    flagBtn.setAttribute("aria-pressed", String(on));
  }

  function setSafe(on) {
    safePanel.hidden = !on;
    safeBtn.setAttribute("aria-pressed", String(on));
  }

  function setDanger(on) {
    dangerPanel.hidden = !on;
  }

  setBell(false);
  setReport(false);
  setSafe(false);
  setDanger(false);

  bellBtn.addEventListener("click", () => {
    const turnOn = alertActions.hidden;
    setBell(turnOn);
    if (turnOn) { setReport(false); setSafe(false); setDanger(false); }
  });

  flagBtn.addEventListener("click", () => {
    const turnOn = reportPanel.hidden;
    setReport(turnOn);
    if (turnOn) { setBell(false); setSafe(false); setDanger(false); }
  });

  safeBtn.addEventListener("click", () => {
    const turnOn = safePanel.hidden;
    setSafe(turnOn);
    if (turnOn) { setBell(false); setReport(false); setDanger(false); }
  });

  // ---------- Placeholders for features we build later ----------
  // Reroute is only available while the user is on a route
  const rerouteBtn = document.getElementById("reroute-btn");
  rerouteBtn.hidden = !isOnRoute();
  onRouteChange((on) => {
    rerouteBtn.hidden = !on;
  });
  rerouteBtn.addEventListener("click", () => {
    // Recalculating the route comes later
  });
  // Danger Alert: hide the bell buttons and show the emergency popup
  document.getElementById("danger-btn").addEventListener("click", () => {
    setBell(false);
    setReport(false);
    setSafe(false);
    setDanger(true);
  });
  document.getElementById("danger-close").addEventListener("click", () => {
    setDanger(false);
  });
  document.querySelectorAll(".report-item").forEach((item) => {
    item.addEventListener("click", () => {
      // item.dataset.type is the problem type, e.g. "crime-scene"
    });
  });

  // ---------- Settings sheet ----------
  const sheet = document.getElementById("sheet");
  document.getElementById("settings-btn").addEventListener("click", () => {
    sheet.hidden = false;
  });
  document.getElementById("sheet-close").addEventListener("click", () => {
    sheet.hidden = true;
  });
  sheet.addEventListener("click", (event) => {
    if (event.target === sheet) sheet.hidden = true;
  });

  // "Show open establishments": true = on, false = off
  const openToggle = document.getElementById("open-toggle");
  openToggle.checked = getShowOpenEstablishments();
  openToggle.addEventListener("change", () => {
    setShowOpenEstablishments(openToggle.checked);
  });

  document.getElementById("logout-btn").addEventListener("click", async () => {
    await logOut();
    window.location.replace("/pages/login.html");
  });
  // ---------- Session check, then map (UI above already works) ----------
  try {
    console.log("[iku] checking session");
    const { data: { session } } = await withTimeout(
      supabase.auth.getSession(), 8000, "Supabase session check"
    );
    if (!session) {
      window.location.replace("/pages/login.html");
      return;
    }
  } catch (err) {
    console.error(err);
    showMapError("Could not reach Supabase: " + err.message +
      ". If the project is paused, restore it in the Supabase dashboard.");
  }
  map = await loadMap();
}

start();