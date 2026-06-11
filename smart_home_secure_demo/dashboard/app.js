// Pollt /api/state und rendert den aktuellen Zustand
const REFRESH_MS = 1000;

function fmtTime(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleTimeString("de-DE"); } catch { return iso; }
}

// colorState: "on" (grün), "off" (grau), "danger" (rot) oder null
function setCard(id, value, sub, colorState) {
  document.getElementById(id + "-value").textContent = value;
  document.getElementById(id + "-sub").textContent = sub || "";
  const card = document.getElementById("card-" + id);
  card.classList.remove("state-on", "state-off", "state-danger");
  if (colorState) card.classList.add("state-" + colorState);
}

async function refresh() {
  let s;
  try { s = await (await fetch("/api/state")).json(); }
  catch { document.getElementById("updated").textContent = "Server nicht erreichbar"; return; }

  document.getElementById("updated").textContent = "Stand: " + fmtTime(s.generatedAt);

  setCard("temperature",
    s.temperature ? `${s.temperature.value} °C` : "--",
    s.temperature ? `${s.temperature.room || ""} · ${fmtTime(s.temperature.receivedAt)}` : "keine Daten");

  setCard("humidity",
    s.humidity ? `${s.humidity.value} %` : "--",
    s.humidity ? `${s.humidity.room || ""} · ${fmtTime(s.humidity.receivedAt)}` : "keine Daten");

  setCard("motion",
    s.motion ? (s.motion.value ? "Bewegung" : "ruhig") : "--",
    s.motion ? fmtTime(s.motion.receivedAt) : "keine Daten");

  // Eingang (Aussen-/Perimetersensor): rot, wenn Bewegung
  setCard("entrance",
    s.entrance ? (s.entrance.value ? "Bewegung" : "ruhig") : "--",
    s.entrance ? fmtTime(s.entrance.receivedAt) : "keine Daten",
    s.entrance ? (s.entrance.value ? "danger" : "off") : null);

  // Aussen/Perimeter: rot, wenn Bewegung
  setCard("perimeter",
    s.perimeter ? (s.perimeter.value ? "Bewegung" : "ruhig") : "--",
    s.perimeter ? fmtTime(s.perimeter.receivedAt) : "keine Daten",
    s.perimeter ? (s.perimeter.value ? "danger" : "off") : null);

  setCard("light",
    s.light ? s.light.state.toUpperCase() : "--",
    s.light ? (s.light.reason || "") : "keine Daten",
    s.light ? s.light.state : null);

  setCard("heating",
    s.heating ? s.heating.state.toUpperCase() : "--",
    s.heating ? (s.heating.reason || "") : "keine Daten",
    s.heating ? s.heating.state : null);

  // Rollladen: open -> OFFEN (gruen), closed -> ZU (grau)
  setCard("shutter",
    s.shutter ? (s.shutter.state === "open" ? "OFFEN" : "ZU") : "--",
    s.shutter ? (s.shutter.reason || "") : "keine Daten",
    s.shutter ? (s.shutter.state === "open" ? "on" : "off") : null);

  // Alarm: on -> ALARM (rot), off -> RUHIG (gruen)
  setCard("alarm",
    s.alarm ? (s.alarm.state === "on" ? "ALARM" : "RUHIG") : "--",
    s.alarm ? (s.alarm.reason || "") : "keine Daten",
    s.alarm ? (s.alarm.state === "on" ? "danger" : "on") : null);

  // Lüftung: on -> AN (gruen), off -> AUS (grau)
  setCard("ventilation",
    s.ventilation ? (s.ventilation.state === "on" ? "AN" : "AUS") : "--",
    s.ventilation ? (s.ventilation.reason || "") : "keine Daten",
    s.ventilation ? (s.ventilation.state === "on" ? "on" : "off") : null);


  let presentText = "--", presentSub = "keine Daten", presentColor = null;
  if (s.presence && s.presence.state) {
    const anwesend = s.presence.state === "anwesend";
    presentText = anwesend ? "ANWESEND" : "ABWESEND";
    presentSub = s.presence.source || "";
    presentColor = anwesend ? "on" : "off";
  }
  setCard("presence", presentText, presentSub, presentColor);

  // Geräte mit Online/Offline-Status
  const tbody = document.querySelector("#devices tbody");
  tbody.innerHTML = "";
  if (!s.devices.length) {
    tbody.innerHTML = `<tr><td colspan="4" class="empty">Noch keine Geräte aufgenommen.</td></tr>`;
  } else {
    for (const d of s.devices) {
      const st = d.status || "unknown";
      const dot = st === "online" ? "🟢" : st === "offline" ? "🔴" : "⚪";
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${d.deviceId}</td>`
        + `<td class="status-${st}">${dot} ${st}</td>`
        + `<td><code>${d.fingerprint || "-"}</code></td>`
        + `<td>${fmtTime(d.onboardedAt)}</td>`;
      tbody.appendChild(tr);
    }
  }

  // Security Events
  const ul = document.getElementById("events");
  ul.innerHTML = "";
  if (!s.securityEvents.length) {
    ul.innerHTML = `<li class="empty">Noch keine Events.</li>`;
  } else {
    for (const e of s.securityEvents) {
      const cls = e.message.includes("ACCEPTED") ? "accepted"
                : e.message.includes("REJECTED") ? "rejected" : "";
      const li = document.createElement("li");
      li.innerHTML = `<span class="t">${fmtTime(e.time)}</span><span class="${cls}">${e.message}</span>`;
      ul.appendChild(li);
    }
  }
}

refresh();
setInterval(refresh, REFRESH_MS);