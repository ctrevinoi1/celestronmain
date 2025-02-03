const telescopeList = document.getElementById('telescope-list');
const noradList = document.getElementById('norad-list');
const updateNoradButton = document.getElementById('update-norad');
const messageDiv = document.getElementById('message');

async function fetchTelescopes() {
    const response = await fetch('http://localhost:5000/telescopes');
    const telescopes = await response.json();
    telescopeList.innerHTML = telescopes.map(t => `<li class="list-group-item">${t}</li>`).join('');
}

async function fetchNoradIDs() {
    const response = await fetch('http://localhost:5000/norad');
    const noradIDs = await response.json();
    // Display one ID per line
    noradList.value = noradIDs.join('\n');
}

function showMessage(type, text) {
    // type can be "success", "danger", etc.
    messageDiv.innerHTML = `<div class="alert alert-${type}" role="alert">${text}</div>`;
    // Remove message after 3 seconds
    setTimeout(() => { messageDiv.innerHTML = ""; }, 3000);
}

async function updateNoradIDs() {
    // Process the textarea: trim each line, remove empty lines, and convert to numbers
    const newNoradIDs = noradList.value.split('\n')
        .map(line => line.trim())
        .filter(line => line !== "")
        .map(Number);

    const response = await fetch('http://localhost:5000/norad', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ norad_ids: newNoradIDs }),
    });

    if (response.ok) {
        showMessage('success', 'NORAD IDs updated successfully!');
    } else {
        const errorData = await response.json();
        showMessage('danger', `Error updating NORAD IDs: ${errorData.error}`);
    }
}

updateNoradButton.addEventListener('click', updateNoradIDs);

// Initial data fetch
fetchTelescopes();
fetchNoradIDs();
// Refresh connected telescopes periodically (every 5 seconds)
setInterval(fetchTelescopes, 5000);