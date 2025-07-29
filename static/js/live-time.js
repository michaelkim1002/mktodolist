let helloShown = false;

function updateDateTime() {
  const now = new Date();

  const timeString = now.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true
  });
  document.getElementById('live-time').textContent = timeString;

  const dateString = now.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
  document.getElementById('live-date').textContent = dateString;


//  const hours = now.getHours();
//  const minutes = now.getMinutes();
//
//  if (hours === 17 && minutes === 23 && !helloShown) {
//    console.log("Hello");
//    alert("Hello");
//    helloShown = true;
//  }
}

updateDateTime();
setInterval(updateDateTime, 1000);