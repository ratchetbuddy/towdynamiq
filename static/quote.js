document.getElementById("quote-form").addEventListener("submit", async function(e) {
  e.preventDefault();

  const tow_type = document.getElementById("tow_type").value;
  const service = document.getElementById("service").value;
  const distance = document.getElementById("distance").value;

  try {
    const response = await fetch("/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tow_type, service, distance })
    });

    const result = await response.json();
    const output = document.getElementById("quote-result");

    if (result.error) {
      output.innerText = "Error: " + result.error;
    } else {
      // ✅ use Python-preformatted breakdown
      output.innerText = result.breakdown;
    }

    // ✅ ensure the box becomes visible
    output.style.display = "inline-block";

  } catch (err) {
    document.getElementById("quote-result").innerText = "Error calculating quote.";
    document.getElementById("quote-result").style.display = "inline-block";
  }
});
