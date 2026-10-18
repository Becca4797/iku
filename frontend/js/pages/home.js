import { supabase } from "/js/supabaseClient.js";
import { logOut } from "/js/auth.js";
import { GOOGLE_MAPS_API_KEY } from "/js/config.js";
import {
  getShowOpenEstablishments,
  setShowOpenEstablishments,
} from "/js/mapSettings.js";
import { isOnRoute, onRouteChange } from "/js/routeState.js";

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


async function setupPlaceAutocomplete(input, map) {
  const { AutocompleteSuggestion, AutocompleteSessionToken } =
    await google.maps.importLibrary("places");

  let sessionToken = null;
  let requestId = 0;
  let selectedDestination = null;

  const form = document.getElementById("search-form");
  if (!form || !input) return;

  // Create a dropdown while keeping the existing search input.
  const results = document.createElement("div");
  results.id = "place-suggestions";
  results.style.cssText = `
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    right: 0;
    z-index: 1000;
    background: white;
    color: #310400;
    border-radius: 10px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.18);
    overflow: hidden;
    display: none;
  `;

  form.appendChild(results);

  function closeSuggestions() {
    results.replaceChildren();
    results.style.display = "none";
  }

  input.addEventListener("input", async () => {
    const query = input.value.trim();
    const currentRequest = ++requestId;

    selectedDestination = null;

    if (query.length < 3) {
      closeSuggestions();
      return;
    }

    if (!sessionToken) {
      sessionToken = new AutocompleteSessionToken();
    }

    try {
      const { suggestions } =
        await AutocompleteSuggestion.fetchAutocompleteSuggestions({
          input: query,
          sessionToken,
          includedRegionCodes: ["gb"],
          language: "en-GB",
        });

      // Ignore outdated responses if the user has continued typing.
      if (currentRequest !== requestId) return;

      closeSuggestions();

      for (const suggestion of suggestions) {
        const prediction = suggestion.placePrediction;
        if (!prediction) continue;

        const option = document.createElement("button");
        option.type = "button";
        option.textContent = prediction.text.toString();

        option.style.cssText = `
          display: block;
          width: 100%;
          padding: 12px 14px;
          border: 0;
          background: white;
          color: #310400;
          text-align: left;
          font: inherit;
          cursor: pointer;
        `;

        option.addEventListener("mouseenter", () => {
          option.style.background = "#fff2e8";
        });

        option.addEventListener("mouseleave", () => {
          option.style.background = "white";
        });

        option.addEventListener("click", async () => {
          try {
            const place = prediction.toPlace();

            await place.fetchFields({
              fields: [
                "formattedAddress",
                "location",
                "displayName",
              ],
            });

            if (!place.location) return;

            selectedDestination = {
              lat: place.location.lat(),
              lng: place.location.lng(),
              address: place.formattedAddress ||
                place.displayName ||
                prediction.text.toString(),
            };

            input.value = selectedDestination.address;
            closeSuggestions();

            // End this autocomplete session.
            sessionToken = null;

            // For now, centre the map on the selected destination.
            // Route calculation will be added separately.
            map.panTo(place.location);
            map.setZoom(16);

            // Make the selected destination available to other
            // front-end code without storing Google's place data.
            window.dispatchEvent(
              new CustomEvent("iku:destination-selected", {
                detail: { ...selectedDestination },
              })
            );
          } catch (error) {
            console.error("Could not retrieve selected place:", error);
          }
        });

        results.appendChild(option);
      }

      if (results.childElementCount > 0) {
        results.style.display = "block";
      }
    } catch (error) {
      console.error("Places autocomplete failed:", error);
      closeSuggestions();
    }
  });

  document.addEventListener("click", (event) => {
    if (!form.contains(event.target)) {
      closeSuggestions();
    }
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();

    // Don't treat unselected text as a confirmed destination.
    if (!selectedDestination) {
      input.focus();
    }
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
    const searchInput = document.getElementById("search-input");

    setupPlaceAutocomplete(searchInput, map).catch(error => {
  console.error("Autocomplete setup failed:", error);
});
  } catch (err) {
    console.error(err);
    showMapError("The map couldn't load: " + err.message);
  }
  return map;
}

async function start() {
  let map; // filled in by loadMap() below; buttons check it before using it

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