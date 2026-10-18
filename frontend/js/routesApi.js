import { API_BASE_URL } from "/js/config.js";

// Ask the back end for walking routes from start to destination.
// start / destination: { lat, lng }
// preference: "safest" | "balanced" | "fastest"
export async function fetchRoutes(start, destination, preference = "balanced", signal) {
  const response = await fetch(`${API_BASE_URL}/api/routes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      start: { lat: start.lat, lng: start.lng },
      destination: { lat: destination.lat, lng: destination.lng },
      preference,
    }),
    signal,
  });

  if (!response.ok) {
    let message = `Route request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = "Invalid start or destination";
    } catch {
      // keep the default message
    }
    throw new Error(message);
  }

  return response.json();
}