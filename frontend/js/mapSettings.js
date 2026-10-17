// Holds the "Show open establishments" setting.
// Later features read it with getShowOpenEstablishments(), or react to
// changes with onShowOpenEstablishmentsChange(callback).

const KEY = "iku_show_open_establishments";
let showOpen = true; // default: on, as in your design

try {
  const saved = localStorage.getItem(KEY);
  if (saved !== null) showOpen = saved === "true";
} catch {
  // storage unavailable: just use the default
}

const listeners = new Set();

export function getShowOpenEstablishments() {
  return showOpen;
}

export function setShowOpenEstablishments(value) {
  showOpen = Boolean(value);
  try {
    localStorage.setItem(KEY, String(showOpen));
  } catch {
    // ignore
  }
  listeners.forEach((callback) => callback(showOpen));
}

export function onShowOpenEstablishmentsChange(callback) {
  listeners.add(callback);
  return () => listeners.delete(callback); // call this to stop listening
}