// Get the modal
const modal = document.getElementById("popupModal");

// Get the button that opens the modal
const btn = document.getElementById("openPopup");

// Get the <span> element that closes the modal
const span = document.getElementsByClassName("close")[0];

// When the user clicks the button, open the modal 
btn.onclick = function() {
    modal.style.display = "block";
}

// When the user clicks on <span> (x), close the modal
span.onclick = function() {
    modal.style.display = "none";
}

// When the user clicks on <div>, open the popup
function Popup() {
    var popup = document.getElementById("myPopup");
    popup.classList.toggle("show");
}

// Load version info
async function loadVersion() {
    const response = await fetch('/api/version');
    const constants = await response.json();
    
    // Set the title with version
    document.getElementById('version').innerText = `v${constants.version}`;
}