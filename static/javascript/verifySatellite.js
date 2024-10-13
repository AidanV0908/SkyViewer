async function verifySatellite(event) {
    event.preventDefault();  // Prevent default form submission

    // Update or confirm the value of selected_result if it's set dynamically
    const selectedResultInput = event.target;
    const id = selectedResultInput.value;
    const yesBtn = document.getElementById('btn-yes');
    const noBtn = document.getElementById('btn-no');

    try {
        // Make the API call with the selected item
        const response = await fetch('/add-satellite-to-cache', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ "ID": id })
        });
    
        if (response.ok) {
            // Parse the response to get the days since epoch
            const data = await response.json();
            const daysSinceEpoch = data.days_since_epoch;
            const proptime = data.maxprop;

            yesBtn.onclick = () => continueAction(id);
            noBtn.onclick = () => closePopup(id);

            // Check if the TLE is stale (greater than 30 days)
            if (daysSinceEpoch > proptime) {
                // Show the warning pop-up if TLE is stale
                showWarningPopup();
            } else {
                // Proceed directly to submit the form
                submitSatelliteInfo(id);
            }
        } else {
            // Show error box if initial API call is not okay
            errorBox.style.display = "block";
        }
    } catch (error) {
        // Show error box if there's an issue with the API call
        console.error("Fetch error:", error);
        errorBox.style.display = "block";
    }
}

function showWarningPopup() {
    document.getElementById("warningPopup").style.display = "flex";
}

async function closePopup(id) {
    if (id != -1) {
        // Make the API call with the selected item
        const response = await fetch('/remove-satellite-from-cache', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ "ID": id })
        });

        if (response.ok) {
            console.log("Successfully removed from cache")
        } else {
            console.log("Removal failure")
        }
    }
    document.getElementById("warningPopup").style.display = "none";
}

function continueAction(id) {
    // Close the popup and proceed with form submission
    closePopup();
    submitSatelliteInfo(id);  // Call the function to submit the form after confirmation
}

async function submitSatelliteInfo(id) {
    const url = `/results?satelliteId=${encodeURIComponent(id)}`;
    window.location.href = url;
}

