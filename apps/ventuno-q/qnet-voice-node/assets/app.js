const fields = {
  identity: document.querySelector('#identity'),
  state: document.querySelector('#state'),
  mqtt: document.querySelector('#mqtt'),
  queue: document.querySelector('#queue'),
  request: document.querySelector('#request'),
  tts: document.querySelector('#tts'),
  error: document.querySelector('#error'),
};

function valueOrDash(value) {
  return value || '—';
}

async function refresh() {
  try {
    const response = await fetch('/api/status', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const status = await response.json();
    fields.identity.textContent = `${status.device_id} · ${status.room_id}`;
    fields.state.textContent = status.state;
    fields.mqtt.textContent = status.mqtt_connected ? 'CONNECTED' : 'DISCONNECTED';
    fields.mqtt.dataset.ok = String(status.mqtt_connected);
    fields.queue.textContent = status.queued_tts;
    fields.request.textContent = valueOrDash(status.last_request);
    fields.tts.textContent = valueOrDash(status.last_tts);
    fields.error.textContent = status.last_error || 'None';
  } catch (error) {
    fields.mqtt.textContent = 'UI OFFLINE';
    fields.error.textContent = error.message;
  }
}

refresh();
setInterval(refresh, 1000);
