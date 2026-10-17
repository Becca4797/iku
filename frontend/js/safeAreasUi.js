// Draws the list of safe places. Later, the saving code will call
// renderSafeAreas(postcodes, onRemove) every time the list changes.

const list = document.getElementById("safe-list");
const emptyNote = document.getElementById("safe-empty");

export function renderSafeAreas(postcodes, onRemove = () => {}) {
  list.replaceChildren();
  emptyNote.hidden = postcodes.length > 0;

  postcodes.forEach((postcode) => {
    const row = document.createElement("li");
    row.className = "safe-item";

    const heart = document.createElement("button");
    heart.type = "button";
    heart.className = "heart-btn";
    heart.setAttribute("aria-label", `Remove ${postcode}`);
    heart.innerHTML =
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 21.2 10.6 20C5.4 15.300 2 12.200 2 8.400 2 5.300 4.400 3 7.500 3c1.700 0 3.400.8 4.500 2.100C13.100 3.800 14.800 3 16.500 3 19.600 3 22 5.300 22 8.400c0 3.800-3.400 6.900-8.600 11.600L12 21.200Z"/></svg>';

    const label = document.createElement("span");
    label.className = "safe-postcode";
    label.textContent = postcode;

    heart.addEventListener("click", () => {
      row.classList.add("removing"); // fades the heart
      onRemove(postcode, row);
    });

    row.append(heart, label);
    list.appendChild(row);
  });
}