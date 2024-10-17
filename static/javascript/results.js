// Generate time zone options
const timeZoneDropdown = document.getElementById("timezone");

for (let offset = -12; offset <= 14; offset++) {
    const option = document.createElement("option");
    option.value = offset; // Set the value for the option
    option.textContent = `UTC ${offset >= 0 ? "+" : ""}${offset}`; // Label with UTC offset
    timeZoneDropdown.appendChild(option);
}

// Period slider JS
function updateSliderValue(value) {
    document.getElementById("current-value").innerText = value;
}

// Set restrictions based on epoch
async function setEpochRestrictions() {
    const id = document.getElementById("satId").value;

    try {
        // Send POST request to the Flask API endpoint
        const response = await fetch('/epoch-data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ "ID": id })
        });

        // Check if the response is OK (status code 200)
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Parse the JSON response
        const data = await response.json();

        const maxprop = data.maxprop;
        const days_since_epoch = data.days_since_epoch; // Assuming `days_since_epoch` comes from the response

        const prop_min_date = data.prop_min;
        const prop_max_date = data.prop_max;

        // Compare maxprop with days_since_epoch to set restrictions
        if (days_since_epoch > maxprop) {
            hideOptionByIndex(1);  // Assuming index 1 is the "current" option
            const warningTxtField = document.getElementById("warningtxt");
            warningTxtField.style.display = "block";
            document.getElementById("nextPass").style.display = "none";
        }

        setDateRange(prop_min_date, prop_max_date)
    } catch (error) {
        console.error("Error fetching data:", error);
    }
}

// Show / hide other time form
function updateOtherTimeField() {
    const selection = document.getElementById("startAt").value;
    if (selection == "other") {
        document.getElementById("hiddentime").style.display = "block";
        const epochdate = document.getElementById("epochdate").value;
        document.getElementById("otherDate").value = epochdate;
        document.getElementById("otherTime").value = "00:00";
    } else {
        document.getElementById("hiddentime").style.display = "none";
    }
}

// Remove option from startAt list
function hideOptionByIndex(index) {
    const select = document.getElementById("startAt");
    if (index >= 0 && index < select.options.length) {
        select.options[index].style.display = "none";
    }
}


// Initialize on page load
document.addEventListener("DOMContentLoaded", function() {
    const slider = document.getElementById("periods");
    updateSliderValue(slider.value);
    updateOtherTimeField();
    setEpochRestrictions();
    document.getElementById('use-current-location').checked = true;
    setCurrentLocation();
    document.getElementById('use-system-time').checked = true;
    setSystemTimeZone(nextPass = false);
});

// Function to set the system time zone
function setSystemTimeZone(nextPass = true) {
    const checkbox = document.getElementById("use-system-time");
    const timezoneSelect = document.getElementById("timezone");
    const errorText = document.getElementById("timezone-error");

    errorText.style.display = "none";

    if (checkbox.checked) {
        try {
            const currentTimeZoneOffset = new Date().getTimezoneOffset() / -60; // System timezone offset in hours
            timezoneSelect.value = currentTimeZoneOffset; // Set to the closest matching UTC offset
            timezoneSelect.disabled = true;
        } catch (error) {
            checkbox.checked = false;
            errorText.style.display = "block";
        }
    } else {
        timezoneSelect.value = "";
        timezoneSelect.disabled = false;
    }
    if (nextPass) {
        findNextPass();
    }
}

// Set date ranges for date fields based off of epoch
function setDateRange(minDateStr, maxDateStr) {
    const otherDateInput = document.getElementById("otherDate");
    const sunDateInput = document.getElementById("sunDate");

    // Set the min and max attributes based on the provided date strings
    otherDateInput.min = minDateStr;
    otherDateInput.max = maxDateStr;
    sunDateInput.min = minDateStr;
    sunDateInput.max = maxDateStr;
}

// Function to set the user's current location
function setCurrentLocation() {
    const checkbox = document.getElementById("use-current-location");
    const latitudeInput = document.getElementById("latitude");
    const longitudeInput = document.getElementById("longitude");
    const errorText = document.getElementById("latlong-error");
    const loadText = document.getElementById("loadText");
    const genButton = document.getElementById("generateButton");
    genButton.disabled = true;

    errorText.style.display = "none";
    loadText.style.display = "block";

    if (checkbox.checked) {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    latitudeInput.value = position.coords.latitude.toFixed(6);
                    longitudeInput.value = position.coords.longitude.toFixed(6);
                    latitudeInput.disabled = true;
                    longitudeInput.disabled = true;
                    findNextPass();
                    loadText.style.display = "none";
                    genButton.disabled = false;
                },
                function() {
                    checkbox.checked = false;
                    errorText.style.display = "block";
                    errorText.textContent = "Could not retrieve location. Make sure location services are enabled.";
                    findNextPass();
                    loadText.style.display = "none";
                    genButton.disabled = false;
                },
                {
                    enableHighAccuracy: true, // Request high accuracy
                    timeout : 7500,
                    maximumAge: 0 // Do not use a cached position
                }
            );
        } else {
            checkbox.checked = false;
            errorText.style.display = "block";
            errorText.textContent = "ERROR"
            loadText.style.display = "none";
            genButton.disabled = false;
        }
    } else {
        latitudeInput.disabled = false;
        longitudeInput.disabled = false;
        latitudeInput.value = "";
        longitudeInput.value = "";
        loadText.style.display = "none";
        genButton.disabled = false;
        findNextPass();
    }
}

// Validate inputs for latitude and longitude
function validateLatLong() {
    const latitudeInput = document.getElementById("latitude");
    const longitudeInput = document.getElementById("longitude");
    const errorText = document.getElementById("latlong-error");

    if (isNaN(latitudeInput.value) || isNaN(longitudeInput.value)) {
        errorText.style.display = "block";
        if (isNaN(latitudeInput.value)) {
            errorText.textContent = "Non-numeric input for latitude. Please re-enter.";
            latitudeInput.value = "";
        } else {
            errorText.textContent = "Non-numeric input for longitude. Please re-enter.";
            longitudeInput.value = "";
        }
    } else if (Math.abs(latitudeInput.value) > 90 || Math.abs(longitudeInput.value) > 180) {
        errorText.style.display = "block";
        if (Math.abs(latitudeInput.value) > 90) {
            errorText.textContent = "Value for latitude out of range. Please re-enter.";
            latitudeInput.value = "";
        } else {
            errorText.textContent = "Value for longitude out of range. Please re-enter.";
            longitudeInput.value = "";
        }
    } else {
        errorText.style.display = "none";
        errorText.textContent = "ERROR";
    }
}

// Validate input for next pass
function validateNextPass() {
    const nextPassElevation = document.getElementById("minElevation");
    const errorText = document.getElementById("nextPassError");

    if (isNaN(nextPassElevation.value)) {
        errorText.style.display = "block";
        errorText.textContent = "Non-numeric input for minimum elevation. Please re-enter.";
        nextPassElevation.value = "";
    } else if (nextPassElevation.value > 90) {
        errorText.style.display = "block";
        errorText.textContent = "Value for minimum elevation too large. Please re-enter.";
        nextPassElevation.value = "";
    } else if (nextPassElevation.value < 0){
        nextPassElevation.value = "0";
    } else {
        errorText.style.display = "none";
        errorText.textContent = "ERROR";
        findNextPass(parseFloat(nextPassElevation.value))
    }
}

async function checkSunlit() {
    const sunlitText = document.getElementById("sunText");
    const satelliteId = document.getElementById("satId").value;

    const date = document.getElementById("sunDate").value
    const time = document.getElementById("sunTime").value

    const errorText = document.getElementById("sunErrorText");

    // Pick up time zone
    const tz = tzOffset();

    if (date != "" && time != "") {
        const time_f = convertToFullTime(time)
        errorText.style.display = "none"
        // Send POST request to the Flask API endpoint
        const response = await fetch('/is-sunlit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ "ID": satelliteId, "date" : date, "time" : time_f, "tz" : tz })
        });

        const data = await response.json();
        if (response.ok) {
            sunlitText.innerText  = `On ${date} at ${time}, ${data.satelliteName} will ${data.sunStatus}.`
            sunlitText.style.display = "block"
        } else {
            sunlitText.style.display = "none"
            errorText.style.display = "block"
            console.error("Error fetching ground track:", data.message);
        }
    } else {
        errorText.style.display = "block"
    }
}

async function findNextPass(minEl=0) {
    if(isNaN(minEl)) {
        minEl = 0
    }
    // Pick up time zone
    const tz = tzOffset();
    const nextPassText = document.getElementById("nextPassText");
    const satelliteId = document.getElementById("satId").value;

    // Pick up observer location
    obsLat_unv = document.getElementById("latitude").value;
    obsLong_unv = document.getElementById("longitude").value;
    const obsLong = validateInput(obsLong_unv, 0);
    const obsLat = validateInput(obsLat_unv, 0);

    // Send POST request to the Flask API endpoint
    const response = await fetch('/next-pass', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ "ID": satelliteId, "lat" : obsLat, "long" : obsLong, "minEl" : minEl, "tz" : tz})
    });

    const data = await response.json();
    if (response.ok) {
        nextPassText.innerText  = `${data.message}`
        nextPassText.style.display = "block"
    } else {
        nextPassText.style.display = "none"
        console.error("Error fetching next pass:", data.message);
    }

}

// Function to check inputs for ground track and return a default if not recognized
function validateInput(input, defaultValue = 0) {
    const result = Number(input);
    return isNaN(result) ? defaultValue : result;
}   

// Function that gets the current date
function getCurrentDate() {
    const today = new Date();

    // Format the date as YYYY-MM-DD
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0'); // Months are zero-indexed
    const day = String(today.getDate()).padStart(2, '0');

    return `${year}-${month}-${day}`;
}

// Gets current time
function getCurrentTime() {
    const now = new Date();

    // Get hours, minutes, and seconds, each padded to two digits
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');

    return `${hours}:${minutes}:${seconds}`;
}

// Converts current time from HH:MM to HH:MM:SS, with seconds set to 00
function convertToFullTime(time) {
    // Check if the input is in HH:MM format
    const timeRegex = /^\d{2}:\d{2}$/;
    if (timeRegex.test(time)) {
        return `${time}:00`;  // Add ":00" for seconds
    } else {
        throw new Error("Invalid time format. Expected HH:MM.");
    }
}

function tzOffset() {
    const dropdown = document.getElementById("timezone");
    const selectedValue = dropdown.value;

    if (selectedValue === "") {
        return 0;
    }

    return selectedValue;
}