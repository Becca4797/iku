
const list = document.getElementById("safe-list");
const emptyNote = document.getElementById("safe-empty");
const message = document.getElementById("safe-message");
const input = document.getElementById("safe-input");
const form = document.getElementById("safe-form");

const STORAGE_KEY = "ding-safe-places";

export function loadSafePlaces() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(saved) ? saved : [];
  } catch {
    return [];
  }
}

function saveSafePlaces(postcodes) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(postcodes));
}

async function validatePostcode(postcode) {
  const response = await fetch(
    `https://api.postcodes.io/postcodes/${encodeURIComponent(postcode)}`
  );

  if (response.status === 404) return null;
  if (!response.ok) throw new Error("Postcode lookup failed");

  const data = await response.json();
  return data.status === 200 ? data.result.postcode : null;
}

export function renderSafeAreas(postcodes, onRemove = () => {}) {
  list.replaceChildren();
  emptyNote.hidden = postcodes.length > 0;

  postcodes.forEach(postcode => {
    const row = document.createElement("li");
    row.className = "safe-item";

    const heart = document.createElement("button");
    heart.type = "button";
    heart.className = "heart-btn";
    heart.setAttribute("aria-label", `Remove ${postcode}`);

    heart.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path fill="currentColor"
          d="M12 21.2 10.6 20C5.4 15.3
          2 12.2 2 8.4 2 5.3
          4.4 3 7.4 3c1.7 0 3.4.8
          4.6 2.1C13.2 3.8 14.9 3
          16.6 3c3 0 5.4 2.3
          5.4 5.4 0 3.8-3.4
          6.9-8.6 11.6L12 21.2Z"/>
      </svg>
    `;

    const label = document.createElement("span");
    label.className = "safe-postcode";
    label.textContent = postcode;

    heart.addEventListener("click", () => {
      onRemove(postcode);
    });

    row.append(heart, label);
    list.appendChild(row);
  });
}

export function initSafeAreas() {
  let postcodes = [...new Set(loadSafePlaces())];

  function refresh() {
    saveSafePlaces(postcodes);
    renderSafeAreas(postcodes, removePostcode);
  }

  function removePostcode(postcode) {
    postcodes = postcodes.filter(p => p !== postcode);
    refresh();
    message.textContent = "";
  }

  form.addEventListener("submit", async event => {
    event.preventDefault();

    const postcode = input.value.trim().toUpperCase();

    if (!postcode) {
      message.textContent = "Please enter a postcode.";
      return;
    }

    const addButton = form.querySelector(".plus-btn");
    addButton.disabled = true;
    message.textContent = "Checking postcode...";

    try {
      const validPostcode = await validatePostcode(postcode);

      if (!validPostcode) {
        message.textContent = "Invalid UK postcode.";
        return;
      }

      if (postcodes.includes(validPostcode)) {
        message.textContent = "This safe place is already saved.";
        return;
      }

      postcodes.push(validPostcode);
      refresh();

      input.value = "";
      message.textContent = "Safe place added!";
    } catch (error) {
      console.error(error);
      message.textContent = "Could not verify postcode. Try again.";
    } finally {
      addButton.disabled = false;
    }
  });

  refresh();
}

