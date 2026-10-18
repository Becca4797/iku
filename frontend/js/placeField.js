// A Google Places autocomplete attached to one text input.
// Used for both the start and the destination fields.
//
//   const field = await createPlaceField({
//     form, input,
//     onSelect: ({ lat, lng, address }) => { ... },
//     onClear: () => { ... },   // user edited the text after choosing a place
//     quickOptions: [{ label: "Use my current location", onPick: () => {} }],
//   });
//   field.setPlace({ lat, lng, address });  // fill it in from code

export async function createPlaceField({ form, input, onSelect, onClear, onSuggestionsToggle, quickOptions = [] }) {
  const { AutocompleteSuggestion, AutocompleteSessionToken } =
    await google.maps.importLibrary("places");

  if (!form || !input) return null;

  let sessionToken = null;
  let requestId = 0;
  let hasSelection = false;

  // Dropdown that sits under the field
  const results = document.createElement("div");
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
    onSuggestionsToggle?.(false);
  }

  function openSuggestions() {
    results.style.display = "block";
    onSuggestionsToggle?.(true);
  }

  function styleOption(option, bold) {
    option.type = "button";
    option.style.cssText = `
      display: block;
      width: 100%;
      padding: 12px 14px;
      border: 0;
      background: white;
      color: #310400;
      text-align: left;
      font: inherit;
      font-weight: ${bold ? "700" : "400"};
      cursor: pointer;
    `;
    option.addEventListener("mouseenter", () => { option.style.background = "#fff2e8"; });
    option.addEventListener("mouseleave", () => { option.style.background = "white"; });
  }

  // Shortcuts (e.g. "Use my current location") shown before the user types
  function showQuickOptions() {
    if (!quickOptions.length) return closeSuggestions();
    results.replaceChildren();
    for (const item of quickOptions) {
      const option = document.createElement("button");
      option.textContent = item.label;
      styleOption(option, true);
      option.addEventListener("click", () => {
        closeSuggestions();
        item.onPick();
      });
      results.appendChild(option);
    }
    openSuggestions();
  }

  input.addEventListener("focus", () => {
    if (!hasSelection && input.value.trim().length < 3) showQuickOptions();
  });

  function setSelected(place) {
    hasSelection = true;
    input.value = place.address;
    closeSuggestions();
    sessionToken = null; // ends this autocomplete session
  }

  input.addEventListener("input", async () => {
    const query = input.value.trim();
    const currentRequest = ++requestId;

    // Typing after choosing a place means the choice no longer applies.
    if (hasSelection) {
      hasSelection = false;
      onClear?.();
    }

    if (query.length < 3) {
      showQuickOptions();
      return;
    }

    if (!sessionToken) sessionToken = new AutocompleteSessionToken();

    try {
      const { suggestions } =
        await AutocompleteSuggestion.fetchAutocompleteSuggestions({
          input: query,
          sessionToken,
          includedRegionCodes: ["gb"],
          language: "en-GB",
        });

      // Ignore outdated responses if the user has kept typing.
      if (currentRequest !== requestId) return;

      closeSuggestions();

      for (const suggestion of suggestions) {
        const prediction = suggestion.placePrediction;
        if (!prediction) continue;

        const option = document.createElement("button");
        option.textContent = prediction.text.toString();
        styleOption(option, false);

        option.addEventListener("click", async () => {
          try {
            const place = prediction.toPlace();
            await place.fetchFields({
              fields: ["formattedAddress", "location", "displayName"],
            });
            if (!place.location) return;

            const chosen = {
              lat: place.location.lat(),
              lng: place.location.lng(),
              address:
                place.formattedAddress ||
                place.displayName ||
                prediction.text.toString(),
            };

            setSelected(chosen);
            onSelect?.(chosen);
          } catch (error) {
            console.error("Could not retrieve selected place:", error);
          }
        });

        results.appendChild(option);
      }

      if (results.childElementCount > 0) openSuggestions();
    } catch (error) {
      console.error("Places autocomplete failed:", error);
      closeSuggestions();
    }
  });

  document.addEventListener("click", (event) => {
    if (!form.contains(event.target)) closeSuggestions();
  });

  // Pressing Enter must not reload the page. If the user has typed a place
  // but not picked it yet, Enter picks the top suggestion.
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (hasSelection) return;

    const top = input.value.trim().length >= 3 ? results.querySelector("button") : null;
    if (top) top.click();
    else input.focus();
  });

  return {
    // Fill the field from code (e.g. "Current location"). Counts as a selection.
    setPlace(place) {
      setSelected(place);
      onSelect?.(place);
    },
    focus() {
      input.focus();
    },
  };
}