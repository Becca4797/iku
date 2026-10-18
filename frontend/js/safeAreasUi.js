
const list = document.getElementById("safe-list");
const emptyNote = document.getElementById("safe-empty");

const STORAGE_KEY = "ding-safe-places";

// Load previously saved postcodes
export function loadSafePlaces() {
  try {
    const saved = JSON.parse(
      localStorage.getItem(STORAGE_KEY) || "[]"
    );
    return Array.isArray(saved)
      ? saved.filter(p => typeof p === "string")
      : [];
  } catch {
    return [];
  }
}

// Save postcodes in browser storage
export function saveSafePlaces(postcodes) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(postcodes)
  );
}

// Check whether a UK postcode actually exists
export async function validatePostcode(postcode) {
  const response = await fetch(
    `https://api.postcodes.io/postcodes/${encodeURIComponent(postcode)}`
  );

  if (!response.ok) {
    if (response.status === 404) return null;
    throw new Error("Postcode lookup unavailable");
  }

  const data = await response.json();

  if (data.status === 200 && data.result) {
    return data.result.postcode;
  }

  return null;
}

// Render saved places with removable hearts
export function renderSafeAreas(
  postcodes,
  onRemove = () => {}
) {
  if (!list || !emptyNote) return;

  list.replaceChildren();
  emptyNote.hidden = postcodes.length > 0;

  postcodes.forEach(postcode => {
    const row = document.createElement("li");
    row.className = "safe-item";

    const heart = document.createElement("button");
    heart.type = "button";
    heart.className = "heart-btn";
    heart.setAttribute(
      "aria-label",
      `Remove ${postcode}`
    );

    heart.innerHTML = `
      <svg viewBox="0 0 24 24"
           width="32"
           height="32"
           aria-hidden="true">
        <path fill="currentColor"
          d="M12 21.2 10.6 20C5.4 15.3
             2 12.2 2 8.4 2 5.3
             4.4 3 7.4 3c1.7 0
             3.4.8 4.6 2.1C13.2
             3.8 14.9 3 16.6 3
             c3 0 5.4 2.3 5.4 5.4
             0 3.8-3.4 6.9-8.6
             11.6L12 21.2Z"/>
      </svg>
    `;

    const label = document.createElement("span");
    label.className = "safe-postcode";
    label.textContent = postcode;

    heart.addEventListener("click", () => {
      row.classList.add("removing");
      onRemove(postcode, row);
    });

    row.append(heart, label);
    list.appendChild(row);
  });
}

// Set up the postcode input and plus button
export function initSafeAreas({
  inputId = "safe-postcode-input",
  buttonId = "add-safe-btn",
  messageId = "safe-message"
} = {}) {
  const input = document.getElementById(inputId);
  const button = document.getElementById(buttonId);
  const message = document.getElementById(messageId);

  if (!input || !button) {
    console.error("Safe place input or button missing");
    return;
  }

  let postcodes = [...new Set(loadSafePlaces())];

  function showMessage(text, isError = false) {
    if (!message) return;
    message.textContent = text;
    message.className = isError
      ? "safe-message error"
      : "safe-message success";
  }

  function refresh() {
    renderSafeAreas(postcodes, removePostcode);
    saveSafePlaces(postcodes);
  }

  function removePostcode(postcode, row) {
    // Remove immediately after animation
    const finish = () => {
      postcodes = postcodes.filter(p => p !== postcode);
      refresh();
      showMessage("");
    };

    if (row) {
      setTimeout(finish, 200);
    } else {
      finish();
    }
  }

  async function addPostcode() {
    const value = input.value.trim().toUpperCase();

    if (!value) {
      showMessage("Please enter a postcode.", true);
      return;
    }

    button.disabled = true;
    showMessage("Checking postcode...");

    try {
      const validPostcode = await validatePostcode(value);

      if (!validPostcode) {
        showMessage(
          "Postcode not found. Please check and try again.",
          true
        );
        return;
      }

      if (postcodes.includes(validPostcode)) {
        showMessage("This safe place is already saved.", true);
        return;
      }

      postcodes.push(validPostcode);
      refresh();

      input.value = "";
      showMessage("Safe place added!");
    } catch (error) {
      console.error(error);
      showMessage(
        "Unable to verify postcode. Please try again.",
        true
      );
    } finally {
      button.disabled = false;
    }
  }

  button.addEventListener("click", addPostcode);

  input.addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      addPostcode();
    }
  });

  refresh();
}
