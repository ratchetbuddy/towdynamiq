document.addEventListener("DOMContentLoaded", () => {
  // ---------------- Safe Location Radios ----------------
  const vehicleRadios = document.querySelectorAll("input[name='vehicle_location']");
  const unsafeLocationDiv = document.getElementById("unsafe_location");
  const unsafeLocationSelect = document.getElementById("unsafe_location_select");

  function toggleUnsafeLocation() {
    const selected = document.querySelector("input[name='vehicle_location']:checked");
    if (selected && selected.value === "no") {
      unsafeLocationDiv.style.display = "block";
      unsafeLocationSelect.setAttribute("required", "required");
    } else {
      unsafeLocationDiv.style.display = "none";
      unsafeLocationSelect.removeAttribute("required");
      unsafeLocationSelect.value = "";
    }
  }

  vehicleRadios.forEach(radio => {
    radio.addEventListener("change", toggleUnsafeLocation);
  });
  toggleUnsafeLocation(); // run on load


  // ---------------- Make / Model Dropdowns ----------------
  const cars = JSON.parse(document.getElementById("cars-data").textContent);
  const makeInput = document.getElementById("make_input");
  const modelInput = document.getElementById("model_input");
  const modelList = document.getElementById("model_list");


// 🔄 Reset when user clicks into make input
makeInput.addEventListener("focus", () => {
  makeInput.value = "";
  modelInput.value = "";
  modelList.innerHTML = "";
  modelInput.disabled = true;
});

// 🔄 Reset when user clicks into model input
modelInput.addEventListener("focus", () => {
  modelInput.value = "";
});

  function populateModels() {
    const selectedMake = makeInput.value.trim();
    console.log("Selected Make:", selectedMake);

    // Reset models
    modelList.innerHTML = "";
    modelInput.value = "";
    modelInput.disabled = true;

    if (!selectedMake) return;

    // Try direct key match first
    let makeEntry = cars[selectedMake];
    console.log("Direct lookup result:", makeEntry);

    // If not found, search by label
    if (!makeEntry) {
      makeEntry = Object.values(cars).find(m => m.label === selectedMake);
      console.log("Label lookup result:", makeEntry);
    }

    if (makeEntry && makeEntry.models) {
      Object.keys(makeEntry.models).forEach(modelKey => {
        const modelData = makeEntry.models[modelKey];
        const opt = document.createElement("option");
        opt.value = modelData.label || modelKey;
        modelList.appendChild(opt);
      });
      modelInput.disabled = false;  // ✅ enable
    }
  }
  makeInput.addEventListener("change", populateModels);
});

// Read the pricing JSON that Flask embedded in quote.html
const pricing = JSON.parse(document.getElementById("pricing-data").textContent);

const towTypeSelect = document.getElementById("tow_type");
const form = document.getElementById("quote-form");
const resultBox = document.getElementById("quote-result");

function populateServices(selectEl, towType) {
  const services = pricing[towType];
  if (!services) return; // ✅ prevent crash if towType not picked

  selectEl.innerHTML = "";
  Object.keys(services).forEach((key) => {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = services[key].label;
    selectEl.appendChild(option);
  });

  if (selectEl.options.length > 0) {
    selectEl.selectedIndex = 0;
  }
}



// Update the Service dropdown when Tow Type changes
function updateServices() {
  const towType = towTypeSelect.value;

  // update all service dropdowns
  document.querySelectorAll("select[name='service_type']").forEach((sel) => {
    populateServices(sel, towType);
  });

  console.log("Tow type:", towType, "Services loaded");
}

function createServiceBlock(isFirst = false, defaultValue = null) {
  const wrapper = document.createElement("div");
  wrapper.classList.add("service-block");

  const label = document.createElement("label");
  label.textContent = "Service Type:";

  const select = document.createElement("select");
  select.name = "service_type";
  if (!isFirst) select.classList.add("extra-service");

  populateServices(select, towTypeSelect.value);

  // ✅ Pre-select default value if provided
  if (defaultValue && [...select.options].some(opt => opt.value === defaultValue)) {
    select.value = defaultValue;
  }

  // Add More button
  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.textContent = "+ Add More Service";
  const msgBox = document.getElementById("service-limit-msg");

  addBtn.addEventListener("click", () => {
    const currentBlocks = document.querySelectorAll(".service-block").length;
    if (currentBlocks < 3) {
      extraServicesDiv.appendChild(createServiceBlock());
      msgBox.classList.remove("show");  // hide if under limit
    } else {
      msgBox.textContent = "You can only select up to 3 services.";
      msgBox.classList.add("show");
    }
  });

  // assemble
  wrapper.appendChild(label);
  wrapper.appendChild(select);
  wrapper.appendChild(document.createElement("br"));
  wrapper.appendChild(addBtn);
  wrapper.appendChild(document.createElement("br"));

  return wrapper;
}

const extraServicesDiv = document.getElementById("extra-services");

const needTowRadios = document.querySelectorAll("input[name='need_tow']");
needTowRadios.forEach(radio => {
  radio.addEventListener("change", () => {
    extraServicesDiv.innerHTML = ""; // clear old blocks
    if (radio.value === "yes" && radio.checked) {
      // ✅ Use "tow" because that's the option value in JSON
      extraServicesDiv.appendChild(createServiceBlock(true, "tow"));
    } else if (radio.value === "no" && radio.checked) {
      extraServicesDiv.appendChild(createServiceBlock(true));
    }
  });
});

//Next two lines could be rendundant
// // Initialize with the first block (main dropdown + button)
// extraServicesDiv.appendChild(createServiceBlock(true));

// Listen for tow_type changes
towTypeSelect.addEventListener("change", updateServices);

// Initialize Service dropdown on page load
updateServices();

// Handle form submission
form.addEventListener("submit", async (e) => {
  e.preventDefault();

  // ✅ Collect main + extra service values, skip blanks
  const services = [];
document.querySelectorAll("select[name='service_type']").forEach((sel) => {
  if (sel.value) services.push(sel.value);
});

  const payload = {
    tow_type: towTypeSelect.value,
    services: services, // send as array now
    distance: document.getElementById("distance").value,
  };

  try {
    const res = await fetch("/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    resultBox.textContent =
      data.breakdown || data.error || JSON.stringify(data, null, 2);
    resultBox.style.display = "block"; // ✅ reveal the box after calculation
  } catch (err) {
    resultBox.textContent = "⚠️ Error contacting server.";
    console.error("Fetch error:", err);
  }
});
