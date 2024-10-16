async function loadGroundTrack() {
    // Pick up satellite ID
    const satelliteId = document.getElementById("satId").value;

    // Pick up epoch date and time
    const epochdate = document.getElementById("epochdate").value;
    const epochtime = document.getElementById("epochtime").value;

    // Pick up time zone
    tz = 0;

    // Pick up observer location
    obsLat_unv = document.getElementById("latitude").value;
    obsLong_unv = document.getElementById("longitude").value;
    const obsLong = validateInput(obsLong_unv, 0);
    const obsLat = validateInput(obsLat_unv, 0);

    // Pick up observation date and time
    const startAtVal = document.getElementById("startAt").value;
    date_unv = epochdate; 
    time_unv = epochtime;
    if (startAtVal == "current") {
        date_unv = getCurrentDate();
        time_unv = getCurrentTime();
    } else if (startAtVal == "other") {
        date_unv = document.getElementById("otherDate").value;
        time_unv = convertToFullTime(document.getElementById("otherTime").value);
        tz = tzOffset();
    }

    const date = date_unv;
    const time = time_unv;
    const timeZone = tz;
    
    // Pick up periods
    const periods = document.getElementById("periods").value;

    // Pick up direction
    const direction = document.getElementById("direction").value;

    // Pick up direction
    const saveButton = document.getElementById("saveButton");

    // Pick up colors
    const pathColor = document.getElementById("pathColor").value;
    const observerColor = document.getElementById("observerColor").value;
    const refTimeColor = document.getElementById("refTimeColor").value;

    // Tip text object
    const tipText = document.getElementById("tipText");

    // Display as null
    if (tipText.style.display != "none") {
        tipText.style.display = "none";
        saveButton.disabled = false;
    }

    const bodyData = { "ID": satelliteId, "lat" : obsLat, "long" : obsLong, "timezone" : timeZone, "date" : date, "time" : time, "periods" : periods, "direction" : direction, "pathColor" : pathColor, "observerColor" : observerColor, "refTimeColor" : refTimeColor }

    const response = await fetch('/generate-gt', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(bodyData),
    });

    const data = await response.json();
    if (response.ok) {
        plotData(data);
    } else {
        console.error("Error fetching ground track:", data.message);
    }
};

function plotData(data) {
    const longitudes = data.longitudes;
    const latitudes = data.latitudes;

    let segments = [];
    let segmentLongs = [];
    let segmentLats = [];

    for (let i = 1; i < longitudes.length; i++) {
        // Push current longitude and latitude into the segment arrays
        segmentLongs.push(longitudes[i - 1]);
        segmentLats.push(latitudes[i - 1]);

        // Check if there's a jump in longitude
        if (i > 0) {
            const diff = Math.abs(longitudes[i] - longitudes[i - 1]);
            if (diff > 180) {
                // Push the current segment to segments array
                segments.push({
                    longs: segmentLongs,
                    lats: segmentLats
                });

                // Reset for the next segment starting with the current point
                segmentLongs = [longitudes[i]];
                segmentLats = [latitudes[i]];
            }
        }
    }

    // Add the last segment if it exists
    if (segmentLongs.length > 0) {
        segments.push({
            longs: segmentLongs,
            lats: segmentLats
        });
    }

    // Create traces for each segment with specified line thickness
    const traces = segments.map((segment, index) => ({
        lon: segment.longs,
        lat: segment.lats,
        mode: 'lines',
        type: 'scattergeo',
        name: `Segment ${index + 1}`,
        line: { width: 2, color: data.pathColor },
        legendgroup: 'Ground Track',
    }));

    // Observer data
    const trace2 = {
        lon: [data.observerLong],
        lat: [data.observerLat],
        mode: 'markers',
        type: 'scattergeo',
        name: 'Observer',
        marker: { shape: 'x', size: 5, color: data.observerColor },
        legendgroup: 'Ground Track',
        showlegend: true
    };

    // Reference time data data
    const trace3 = {
        lon: [data.refLong],
        lat: [data.refLat],
        mode: 'markers',
        type: 'scattergeo',
        name: 'Satellite @ Reference',
        marker: { size: 5, color: data.refTimeColor },
        legendgroup: 'Ground Track',
        showlegend: true
    };
    // Layout configuration with tick marks at increments of 30 degrees
    const layout = {
        title: `${data.name} Ground Track`,
        autosize: true, 
        geo: {
            projection: { type: 'equirectangular' }, // Keeps a consistent projection type
            showcoastlines: true
        },
        showlegend: false,
    };


    // Combine all traces into one array for Plotly
    const plotData = [...traces, trace2, trace3]; // Spread the traces into the array
    Plotly.newPlot('plot', plotData, layout, {responsive: true});
}


// Function to save the plot as an image
document.getElementById('saveButton').onclick = function() {
    const now = new Date();
    const timestamp = now.toISOString().replace(/[-:]/g, '').split('.')[0];

    const id = document.getElementById('satId').value;

    Plotly.downloadImage('plot', {
        format: 'png', // Options: png, jpeg, webp, svg
        width: 800, // Set the width of the image
        height: 600, // Set the height of the image
        filename: `Groundtrack_${id}_${timestamp}` // Set the filename
    });
};

