let data = {};

async function updateSearchContent(searchTerm, page = 1) {
    try {
        showLoading(); // Show loading spinner

        // Fetch data from the API endpoint
        const response = await fetch('/refresh-search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ search_term: searchTerm, page: page })
        });

        if (response.ok) {
            data = await response.json();
            data.API_Code = 200; // Set success code for consistent handling
            displaySearchResults(data); // Display the data on the page
        } else {
            displaySearchResults({ API_Code: response.status });
        }
    } catch (error) {
        console.error('Fetch error:', error);
        displaySearchResults({ API_Code: 'Error', message: 'An error occurred while fetching data.' });
    } finally {
        hideLoading(); // Hide loading spinner
    }
}

function displaySearchResults(data) {
    const resultsContainer = document.getElementById('results-container');
    const searchBox = document.getElementById('search_term');
    const errorBox = document.getElementById('errorBox');
    const apiStatusElement = document.getElementById('api-status');
    const paginationContainer = document.getElementById('pagination-container');
    const numResultsElement = document.getElementById('num-results');
    const pageInfo = document.getElementById('page-info');
    const nextButton = document.getElementById('next-button');
    const prevButton = document.getElementById('prev-button');

    resultsContainer.innerHTML = '';
    searchBox.value = "";
    paginationContainer.style.display = 'flex'; // Ensure pagination container is shown

    if (data.API_Code === 200) {
        apiStatusElement.textContent = '';

        if (data.members && data.members.length > 0) {
            numResultsElement.textContent = `${data.total_results} results found.`;
            errorBox.display = 'none';

            const tableContainer = document.createElement('div');
            tableContainer.className = 'table-container';

            const headerRow = document.createElement('div');
            headerRow.className = 'header-row';
            headerRow.innerHTML = `
                <div class="cell">ID</div>
                <div class="cell">Name</div>
                <div class="cell" style="min-width: 125px"></div>
                <div class="hidden-cell">ID</div>
                <div class="hidden-cell">Name</div>
                <div class="hidden-cell" style="min-width: 125px"></div>`;
            tableContainer.appendChild(headerRow);

            data.members.forEach(member => {
                const row = document.createElement('div');
                row.className = 'row';

                const idCell = document.createElement('div');
                idCell.className = 'cell';
                idCell.textContent = member.satelliteId;
                row.appendChild(idCell);

                const nameCell = document.createElement('div');
                nameCell.className = 'cell';
                nameCell.textContent = member.name;
                row.appendChild(nameCell);

                const buttonCell = document.createElement('div');
                buttonCell.className = 'cell';
                const button = document.createElement('button');
                button.className = 'submit-button';
                button.type = 'submit';
                button.name = 'selected_result';
                button.id = 'selected_result';
                button.value = member.satelliteId;
                button.textContent = 'Select';
                button.onclick = function(event) {
                    return verifySatellite(event);
                };
                buttonCell.appendChild(button);
                row.appendChild(buttonCell);

                tableContainer.appendChild(row);
            });

            resultsContainer.appendChild(tableContainer);

        } else {
            numResultsElement.textContent = 'No results found.';
        }
        pageInfo.innerHTML = `Page <input type="text" value="${data.page}" id="pageInput" style="width: 30px;" onkeydown="onEnterPage(event)"> of ${data.pages}`;

        // Handle visibility of Prev and Next buttons
        prevButton.style.display = data.page > 1 ? 'inline-block' : 'none';
        nextButton.style.display = data.page < data.pages ? 'inline-block' : 'none';

        // Set onclick actions for Prev and Next buttons
        prevButton.onclick = () => updateSearchContent(data.search_term, data.page - 1);
        nextButton.onclick = () => updateSearchContent(data.search_term, data.page + 1);
    } else {
        apiStatusElement.textContent = `Failure: API Code ${data.API_Code}`;
        numResultsElement.textContent = '';
        paginationContainer.style.display = 'none'; // Hide pagination if there's an error
    }
}

function showLoading() {
    document.getElementById('loading-overlay').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading-overlay').style.display = 'none';
}

function submitSearch(event) {
    event.preventDefault(); // Prevent the page from refreshing
    const searchTerm = document.getElementById('search_term').value;
    updateSearchContent(searchTerm, 1); // Start at page 1
}

// Load max prop info
async function setMaxProp() {
    const response = await fetch('/prop-time');
    const constants = await response.json();
    
    // Set the title with version
    document.getElementById('warning-text').innerText = `TLE is older than ${constants.maxprop} days. You can still collect information about this satellite, but some functions may be restricted to ensure accurate data. Continue anyway?`;
}

function onLoadFunctions() {
    updateSearchContent('ISS', 1);
    setMaxProp();
}

function onEnterPage(event) {
        if (event.key === "Enter") {
        pageVal = document.getElementById('pageInput').value
        if (validPage(pageVal)) {
            updateSearchContent(data.search_term, parseInt(pageVal));
        }
    }
}

function validPage(page) {
    if (!isNaN(page)) {
        if (parseInt(page) <= data.pages && parseInt(page) != data.page) {
            return true;
        }
    }
    return false;
}