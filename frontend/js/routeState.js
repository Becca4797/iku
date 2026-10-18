// Tracks whether the user is currently following a route.
// The navigation code will call setOnRoute(true) when a route starts
// and setOnRoute(false) when it ends or is cancelled.

let onRoute = false;
const listeners = new Set();

export function isOnRoute() {
  return onRoute;
}

export function setOnRoute(value) {
  onRoute = Boolean(value);
  listeners.forEach((callback) => callback(onRoute));
}

export function onRouteChange(callback) {
  listeners.add(callback);
  return () => listeners.delete(callback);
}