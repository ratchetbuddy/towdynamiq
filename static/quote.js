// Read the pricing JSON that Flask embedded in quote.html
const pricing = JSON.parse(document.getElementById("pricing-data").textContent);

const towTypeSelect = document.getElementById("tow_type");
const serviceSelect = document.getElementById("service_type");
const form = document.getElementById("quote-form");
const resultBox = document.getElementById("quote-result");

// Update the Service dropdown when Tow Type changes
function updateServices() {
  const towType = towTypeSelect.value;
  const services = pricing[towType];
  serviceSelect.innerHTML = "";

  serviceSelect.innerHTML = "";


  Object.keys(services).forEach((key) => {
    const option = document.createElement("option");
    option.value = key;                   // backend key (e.g. "hook", "connex")
    option.textContent = services[key].label; // user-friendly label
    serviceSelect.appendChild(option);
  });

  if (serviceSelect.options.length > 0) {
    serviceSelect.selectedIndex = 0;
  }

  console.log("Tow type:", towType, "Services loaded:", Object.keys(services));
}

// Listen for tow_type changes
towTypeSelect.addEventListener("change", updateServices);

// Initialize Service dropdown on page load
updateServices();

// Handle form submission
form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    tow_type: towTypeSelect.value,
    service: serviceSelect.value,
    distance: document.getElementById("distance").value
  };

  try {
    const res = await fetch("/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    resultBox.textContent = data.breakdown || data.error || JSON.stringify(data, null, 2);
    resultBox.style.display = "block";   // ✅ reveal the box after calculation
  } catch (err) {
    resultBox.textContent = "⚠️ Error contacting server.";
    console.error("Fetch error:", err);
  }
});
