// Run this whole script only AFTER the page's HTML is fully loaded
document.addEventListener("DOMContentLoaded", () => {

// ---------------- Current Date/Time ----------------
function updateDateTime() {
  const now = new Date();

  const dateStr = now.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });

  const timeStr = now.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });

  const el = document.getElementById("current-datetime");
  if (el) {
    el.innerHTML = `${dateStr}<br>${timeStr}`; // date on one line, time on next
  }
}

setInterval(updateDateTime, 1000);
updateDateTime();
  
  // ---------------- Safe Location Radios ----------------
  // Grab all radio buttons for "Is the vehicle in a safe location?"
  const vehicleRadios = document.querySelectorAll("input[name='vehicle_location']");
  // Grab the div that contains the "unsafe location" follow-up question
  const unsafeLocationDiv = document.getElementById("unsafe_location");
  const unsafeLocationSelect = document.getElementById("unsafe_location_select");

  // Show or hide the unsafe location dropdown depending on radio selection
  function toggleUnsafeLocation() {
    const selected = document.querySelector("input[name='vehicle_location']:checked");
    if (selected && selected.value === "no") {
      // If user says "No, not safe", show the extra dropdown and make it required
      unsafeLocationDiv.style.display = "block";
      unsafeLocationSelect.setAttribute("required", "required");
    } else {
      // If safe (or nothing selected), hide the dropdown and reset its value
      unsafeLocationDiv.style.display = "none";
      unsafeLocationSelect.removeAttribute("required");
      unsafeLocationSelect.value = "";
    }
  }

  // Whenever a radio changes, re-check visibility of the unsafe location field
  vehicleRadios.forEach(radio => {
    radio.addEventListener("change", toggleUnsafeLocation);
  });
  toggleUnsafeLocation(); // Run once on page load, to set initial state


  const unsafeLocationDisplay = document.getElementById("unsafe_location_select");

  unsafeLocationDisplay.addEventListener("change", () => {
    const selected = unsafeLocationDisplay.options[unsafeLocationDisplay.selectedIndex];
    const roadType = selected.closest("optgroup")?.label || "";
    const laneLabel = selected.textContent;

    if (roadType && laneLabel) {
      // Update visible text inside the <option>
      selected.textContent = `${roadType} – ${laneLabel}`;
    }
  });


  // ---------------- Make / Model Dropdowns ----------------
  // Parse car make/model data from JSON embedded in the HTML
  const cars = JSON.parse(document.getElementById("cars-data").textContent);
  const makeInput = document.getElementById("make_input");
  const modelInput = document.getElementById("model_input");
  const modelList = document.getElementById("model_list");

  // Reset both inputs when user focuses into "make"
  makeInput.addEventListener("focus", () => {
    makeInput.value = "";
    modelInput.value = "";
    modelList.innerHTML = "";
    modelInput.disabled = true;
  });

  // Reset model input when user focuses into it
  modelInput.addEventListener("focus", () => {
    modelInput.value = "";
  });

  // Populate model dropdown once a make has been chosen
  function populateModels() {
    const selectedMake = makeInput.value.trim();

    // Always reset the model list first
    modelList.innerHTML = "";
    modelInput.value = "";
    modelInput.disabled = true;

    if (!selectedMake) return;

    // Try direct dictionary key lookup first (cars["Ford"])
    let makeEntry = cars[selectedMake];

    // If not found by key, try to match by label instead
    if (!makeEntry) {
      makeEntry = Object.values(cars).find(m => m.label === selectedMake);
    }

    // If we found a valid make, populate the models
    if (makeEntry && makeEntry.models) {
      Object.keys(makeEntry.models).forEach(modelKey => {
        const modelData = makeEntry.models[modelKey];
        const opt = document.createElement("option");
        opt.value = modelData.label || modelKey;
        modelList.appendChild(opt);
      });
      modelInput.disabled = false;  // enable model input
    }
  }

  // Re-populate models whenever "make" changes
  makeInput.addEventListener("change", populateModels);

/**
 * Dynamic Truck Label Updater
 * ---------------------------
 * This code updates the "How many trucks are available?" label
 * to include the selected tow type (e.g., "Light Duty", "Heavy Duty").
 * It runs once on page load and again whenever the tow type changes.
 */

// Grab the tow type <select> element from the form
const towTypeSelectForLabel = document.getElementById("tow_type");

// Grab the label element for the truck utilization input
const truckLabel = document.getElementById("truck_utilization_label");

// Function that updates the label text based on the selected tow type
function updateTruckLabel() {
  const towType = towTypeSelectForLabel.value; // get the currently selected tow type

  if (towType) {
    // If a tow type is selected, customize the label with it
    truckLabel.textContent = `How many ${towType} trucks are available?`;
  } else {
    // If no tow type is selected, fall back to the default label
    truckLabel.textContent = "How many trucks are available?";
  }
}

// Run the function once right away so the label matches the default tow type on page load
updateTruckLabel();

// Attach an event listener so that every time the tow type changes,
// the truck label is updated dynamically
towTypeSelectForLabel.addEventListener("change", updateTruckLabel);


// ---------------- Pricing + Services ----------------
// Parse pricing JSON from hidden HTML element
const pricing = JSON.parse(document.getElementById("pricing-data").textContent);

const towTypeSelect = document.getElementById("tow_type");
const form = document.getElementById("quote-form");
const resultBox = document.getElementById("quote-result");

// Fill a <select> dropdown with services based on tow type
function populateServices(selectEl, towType) {
  const services = pricing[towType];
  if (!services) return; // Bail if no tow type chosen

  // Clear old options
  selectEl.innerHTML = "";
  // Add <option> for each service
  Object.keys(services).forEach((key) => {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = services[key].label;
    selectEl.appendChild(option);
  });

  // Default: select the first option
  if (selectEl.options.length > 0) {
    selectEl.selectedIndex = 0;
  }
}

// Update every service dropdown when tow type changes
function updateServices() {
  const towType = towTypeSelect.value;

  document.querySelectorAll("select[name='service_type']").forEach((sel) => {
    populateServices(sel, towType);
  });

}


// ---------------- Service Block Creation ----------------
// Build one "service block": label + dropdown + add/remove buttons
function createServiceBlock(isFirst = false, defaultValue = null) {
  const wrapper = document.createElement("div");
  wrapper.classList.add("service-block");
  wrapper.style.position = "relative"; // allow absolute positioning of ❌ button


  const blockCount = document.querySelectorAll(".service-block").length + 1;

  // Generate a label based on how many blocks exist
  let labelText;
  if (blockCount === 1) {
    labelText = "Service Type 1: Choose your first service";
  } else if (blockCount === 2) {
    labelText = "Service Type 2: Select another service";
  } else if (blockCount === 3) {
    labelText = "Service Type 3: Select final service";
  } else {
    labelText = "Service Type:";
  }

  const label = document.createElement("label");
  label.textContent = labelText;

  const select = document.createElement("select");
  select.name = "service_type";
  if (!isFirst) select.classList.add("extra-service");

  // Populate dropdown if towTypeSelect is ready
  if (typeof populateServices === "function" && typeof towTypeSelect !== "undefined") {
    populateServices(select, towTypeSelect.value);
  }

  // Pre-select default service if provided
  if (defaultValue && [...select.options].some(opt => opt.value === defaultValue)) {
    select.value = defaultValue;
  }

  // "+ Add More Service" button container
  const addContainer = document.createElement("div");
  addContainer.classList.add("add-container");

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.textContent = "+ Add More Service";
  addBtn.classList.add("add-service");

  addContainer.appendChild(addBtn);

  const msgBox = document.getElementById("service-limit-msg");

  // When user clicks "+ Add More Service"
  addBtn.addEventListener("click", () => {
    const currentBlocks = document.querySelectorAll(".service-block");

    if (currentBlocks.length < 3) {
      // Hide all other "+ Add" buttons so only the newest block shows it
      currentBlocks.forEach(block => {
        const container = block.querySelector(".add-container");
        if (container) container.style.display = "none";
      });

      // Add a new block to the DOM
      extraServicesDiv.appendChild(createServiceBlock());
      msgBox.classList.remove("show");
    } else {
      // Hit the limit → show warning message
      msgBox.textContent = "You can only select up to 3 services.";
      msgBox.classList.add("show");
    }
  });

  // ❌ Remove button only appears on non-first blocks
  if (!isFirst) {
    const removeBtn = document.createElement("span");
    removeBtn.textContent = "✖";
    removeBtn.style.position = "absolute";
    removeBtn.style.top = "5px";
    removeBtn.style.right = "5px";
    removeBtn.style.cursor = "pointer";
    removeBtn.style.color = "red";
    removeBtn.style.fontWeight = "bold";

    removeBtn.addEventListener("click", () => {
      wrapper.remove();
      msgBox.classList.remove("show");

      // Make sure the last remaining block always has its "+ Add" button visible
      const blocks = document.querySelectorAll(".service-block");
      if (blocks.length > 0) {
        const lastBlock = blocks[blocks.length - 1];
        const lastContainer = lastBlock.querySelector(".add-container");
        if (lastContainer) lastContainer.style.display = "block";
      }
    });

    wrapper.appendChild(removeBtn);
  }

  // Assemble the block
  wrapper.appendChild(label);
  wrapper.appendChild(select);
  wrapper.appendChild(addContainer);

  return wrapper;
}

const extraServicesDiv = document.getElementById("extra-services");


// ---------------- Need Tow Radios ----------------
// Show different service defaults depending on "Do you need a tow?"
const needTowRadios = document.querySelectorAll("input[name='need_tow']");
needTowRadios.forEach(radio => {
  radio.addEventListener("change", () => {
    extraServicesDiv.innerHTML = ""; // clear any old blocks
    if (radio.value === "yes" && radio.checked) {
      // First block is mandatory, preselect "tow"
      extraServicesDiv.appendChild(createServiceBlock(true, "tow"));
    } else if (radio.value === "no" && radio.checked) {
      // First block without a default
      extraServicesDiv.appendChild(createServiceBlock(true));
    }
  });
});

// Note: could auto-initialize the first block here, but code comments say maybe redundant
// extraServicesDiv.appendChild(createServiceBlock(true));


// ---------------- Tow Type Watcher ----------------
// Whenever tow type changes, repopulate all service dropdowns
towTypeSelect.addEventListener("change", updateServices);

// Initialize dropdowns on page load
updateServices();


// ---------------- Form Submission ----------------
form.addEventListener("submit", async (e) => {
  e.preventDefault();  // stop the default HTML form submission

  // Collect all selected services (skip blanks)
  const services = [];
  document.querySelectorAll("select[name='service_type']").forEach((sel) => {
    if (sel.value) services.push(sel.value);
  });

  // ✅ Get safe/unsafe vehicle location
  const vehicle_location = document.querySelector("input[name='vehicle_location']:checked")?.value;
  let unsafe_location = null;

  if (vehicle_location === "no") {
    const sel = document.getElementById("unsafe_location_select");
    const lane = sel.value || null;
    const roadType = sel.options[sel.selectedIndex]?.dataset.roadType || null;

    if (lane && roadType) {
      unsafe_location = { road_type: roadType, lane: lane };
    }
  }

  // Build JSON payload similar to a Python dict
  const payload = {
    need_tow: document.querySelector("input[name='need_tow']:checked")?.value || null,
    is_accident: document.querySelector("input[name='is_accident']:checked")?.value || null,
    vehicle_location: document.querySelector("input[name='vehicle_location']:checked")?.value || null,
    unsafe_location: unsafe_location,
    make: document.getElementById("make_input").value || null,
    model: document.getElementById("model_input").value || null,
    tow_type: towTypeSelect.value,
    services: services,
    distance: document.querySelector("input[name='distance']").value,
    quote_type: document.getElementById("quote_type_select").value,
    weather: document.getElementById("weather_select").value,
    truck_utilization: document.getElementById("truck_utilization_input").value,
  };

  console.log(payload)

  try {
    // POST to backend Flask route /calculate
    const res = await fetch("/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    console.log(data)
    resultBox.textContent =
      data.breakdown || data.error || JSON.stringify(data, null, 2);
    resultBox.style.display = "block"; // Show the result box
  } catch (err) {
    resultBox.textContent = "⚠️ Error contacting server.";
    console.error("Fetch error:", err);
  }
});
});