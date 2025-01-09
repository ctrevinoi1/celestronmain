const telescopeList = document.getElementById('telescope-list');
const noradList = document.getElementById('norad-list');
const updateNoradButton = document.getElementById('update-norad');

async function fetchTelescopes() {
    const response = await fetch('http://localhost:5000/telescopes');
    const telescopes = await response.json();
    telescopeList.innerHTML = telescopes.map(t => `<li>${t}</li>`).join('');
}

async function fetchNoradIDs() {
    const response = await fetch('http://localhost:5000/norad');
    const noradIDs = await response.json();
    noradList.value = noradIDs.join('\n');
}

async function updateNoradIDs() {
    const newNoradIDs = noradList.value.split('\n').map(Number);
    const response = await fetch('http://localhost:5000/norad', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ norad_ids: newNoradIDs }),
    });

    if (response.ok) {
        alert('NORAD IDs updated successfully!');
    } else {
        const errorData = await response.json();
        alert(`Error updating NORAD IDs: ${errorData.error}`);
    }
}

updateNoradButton.addEventListener('click', updateNoradIDs);

// Initial data fetch
fetchTelescopes();
fetchNoradIDs();

// Refresh data periodically (optional)
setInterval(fetchTelescopes, 5000); // Refresh every 5 seconds