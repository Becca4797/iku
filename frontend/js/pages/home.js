import { supabase } from "/js/supabaseClient.js";
import { logOut } from "/js/auth.js";
import { GOOGLE_MAPS_API_KEY } from "/js/config.js";
import {
  getShowOpenEstablishments,
  setShowOpenEstablishments,
} from "/js/mapSettings.js";
import { renderSafeAreas } from "/js/safeAreasUi.js";

// Roughly King's Cross / Bloomsbury, London
const LONDON_CENTRE = { lat: 51.5295, lng: -0.1245 };

const mapError = document.getElementById("map-error");

function showMapError(text) {
  mapError.textContent = text;
  mapError.hidden = false;
}

// ---------- Session check ----------
const { data: { session } } = await supabase.auth.getSession();
if (!session) {
  window.location.replace("/pages/login.html");
} else {
  start();
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

// Google calls this if the key is rejected (wrong key, restriction, billing)
window.gm_authFailure = () => {
  showMapError("The map couldn't load. Check the Google Maps key and billing.");
};

async function start() {
  let map;
  try {
    await loadGoogleMaps(GOOGLE_MAPS_API_KEY);
    const { Map } = await google.maps.importLibrary("maps");
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
    showMapError("The map couldn't load. Check your internet connection.");
  }

  // Layers button: switch between satellite-with-labels and the standard map
  document.getElementById("layers-btn").addEventListener("click", () => {
    if (!map) return;
    map.setMapTypeId(map.getMapTypeId() === "hybrid" ? "roadmap" : "hybrid");
  });

  // Search: Places autocomplete comes later
  document.getElementById("search-form").addEventListener("submit", (event) => {
    event.preventDefault();
  });

  // ---------- Bell, flag and bookmark toggles ----------
  // Opening one closes the others so they never overlap.
  const bellBtn = document.getElementById("bell-btn");
  const alertActions = document.getElementById("alert-actions");
  const flagBtn = document.getElementById("routes-btn");
  const reportPanel = document.getElementById("report-panel");
  const safeBtn = document.getElementById("safe-areas-btn");
  const safePanel = document.getElementById("safe-panel");

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

  setBell(false);
  setReport(false);
  setSafe(false);

  bellBtn.addEventListener("click", () => {
    const turnOn = alertActions.hidden;
    setBell(turnOn);
    if (turnOn) { setReport(false); setSafe(false); }
  });

  flagBtn.addEventListener("click", () => {
    const turnOn = reportPanel.hidden;
    setReport(turnOn);
    if (turnOn) { setBell(false); setSafe(false); }
  });

  safeBtn.addEventListener("click", () => {
    const turnOn = safePanel.hidden;
    setSafe(turnOn);
    if (turnOn) { setBell(false); setReport(false); }
  });

  // ---------- Safe places (interface only for now) ----------
  renderSafeAreas([]); // starts blank
  document.getElementById("safe-form").addEventListener("submit", (event) => {
    event.preventDefault(); // saving comes in the next step
  });

  // ---------- Placeholders for features we build later ----------
  document.getElementById("reroute-btn").addEventListener("click", () => {});
  document.getElementById("danger-btn").addEventListener("click", () => {});
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
}
