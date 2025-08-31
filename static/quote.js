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

function createServiceBlock(isFirst = false) {
  const wrapper = document.createElement("div");
  wrapper.classList.add("service-block");

  const label = document.createElement("label");
  label.textContent = "Service Type:";

  const select = document.createElement("select");
  select.name = "service_type";
  if (!isFirst) select.classList.add("extra-service");

  populateServices(select, towTypeSelect.value);

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

// Initialize with the first block (main dropdown + button)
extraServicesDiv.appendChild(createServiceBlock(true));

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
