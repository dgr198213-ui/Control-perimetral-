const $ = (selector) => document.querySelector(selector);

const state = {
  profile: null,
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || payload.error?.message || `Error ${response.status}`);
  }
  return payload;
}

function setLoggedIn(loggedIn) {
  $("#login-panel").hidden = loggedIn;
  $("#app-panel").hidden = !loggedIn;
}

function renderStatus(status) {
  const statusText = { protected: "Protegido", attention: "Atención", setup_required: "Configuración pendiente" };
  $("#protection-status").textContent = statusText[status.status] || status.status;
  $("#protection-summary").textContent = status.summary || "";
  $("#protection-mark").style.color = status.status === "protected" ? "var(--accent)" : "var(--warning)";
  $("#protection-mark").style.borderColor = status.status === "protected" ? "var(--accent)" : "var(--warning)";
}

function renderDiscovery(discovery) {
  const resources = discovery.resources;
  const rows = [
    ["Cámaras", resources.cameras.count, `${resources.cameras.active_count} activas`],
    ["Zonas", resources.zones.count, resources.zones.truncated ? "lista limitada" : "configuradas"],
    ["Reglas de aviso", resources.notification_rules.count, `${resources.notification_rules.active_count} activas`],
  ];
  $("#resource-list").innerHTML = rows.map(([name, count, detail]) => `<div class="resource-row"><div><strong>${name}</strong><span>${detail}</span></div><strong>${count}</strong></div>`).join("");
  const frigate = discovery.integrations.frigate.status;
  const mqtt = discovery.integrations.mqtt.status;
  $("#integration-state").textContent = `Frigate: ${frigate} · MQTT: ${mqtt}`;
}

function renderRecommendations(payload) {
  const items = payload.items || [];
  $("#recommendations").innerHTML = items.length
    ? items.map((item) => `<div class="recommendation"><strong>${item.message}</strong></div>`).join("")
    : `<div class="recommendation" style="color: var(--accent)"><strong>No hay acciones pendientes.</strong></div>`;
}

function renderHealth(payload) {
  const items = payload.items || [];
  $("#health-list").innerHTML = items.length
    ? items.map((item) => `<div class="health-row"><div><strong>${item.sensor_id}</strong><span>${item.sensor_type} · ${item.reason}</span></div><span>${item.status}</span></div>`).join("")
    : `<p class="muted">Todavía no hay observaciones de sensores.</p>`;
}

function fillProfile(profile) {
  state.profile = profile;
  const form = $("#profile-form");
  for (const name of ["site_type", "protection_mode"]) form.elements[name].value = profile[name];
  for (const name of ["detect_people", "detect_vehicles", "detect_animals", "night_protection", "notify_on_suspicious", "notify_on_incident"]) form.elements[name].checked = profile[name];
}

async function loadDashboard() {
  const [status, discovery, recommendations, profile] = await Promise.all([
    api("/api/protection/status"),
    api("/api/protection/discovery"),
    api("/api/protection/recommendations"),
    api("/api/protection-profile"),
  ]);
  renderStatus(status);
  renderDiscovery(discovery);
  renderRecommendations(recommendations);
  fillProfile(profile);
  try {
    renderHealth(await api("/api/multisensor/health"));
  } catch (_error) {
    $("#health-list").innerHTML = `<p class="muted">La salud multisensor está pendiente de confirmar los requisitos de cumplimiento.</p>`;
  }
}

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  $("#login-error").textContent = "";
  try {
    await api("/api/auth/login", { method: "POST", body: JSON.stringify(Object.fromEntries(form)) });
    setLoggedIn(true);
    await loadDashboard();
  } catch (error) {
    $("#login-error").textContent = error.message;
  }
});

$("#profile-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const body = Object.fromEntries(new FormData(form));
  for (const name of ["detect_people", "detect_vehicles", "detect_animals", "night_protection", "notify_on_suspicious", "notify_on_incident"]) body[name] = form.elements[name].checked;
  try {
    await api("/api/protection-profile", { method: "PUT", body: JSON.stringify(body) });
    $("#profile-message").textContent = "Configuración guardada.";
    await loadDashboard();
  } catch (error) {
    $("#profile-message").textContent = error.message;
  }
});

$("#refresh-button").addEventListener("click", async () => {
  if (!$("#app-panel").hidden) await loadDashboard();
});

setLoggedIn(false);
