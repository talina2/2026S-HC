// Pollt /api/broker und zeigt den rohen, verschlüsselten Datenstrom
const REFRESH_MS = 2000;

function fmtTime(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleTimeString("de-DE"); } catch { return iso; }
}

async function refresh() {
  let s;
  try { s = await (await fetch("/api/broker")).json(); }
  catch { document.getElementById("updated").textContent = "Server nicht erreichbar"; return; }

  document.getElementById("updated").textContent = "Stand: " + fmtTime(s.generatedAt);
  const ul = document.getElementById("feed");
  ul.innerHTML = "";
  if (!s.feed.length) {
    ul.innerHTML = `<li class="empty">Noch keine Nachrichten. Starte Sensoren/Automation.</li>`;
    return;
  }
  for (const m of s.feed) {
    const li = document.createElement("li");
    li.className = "feed-item";
    li.innerHTML = `
      <div class="feed-head">
        <span class="t">${fmtTime(m.observedAt)}</span>
        <span class="topic">${m.topic || ""}</span>
        <span class="dev">${m.deviceId || ""}</span>
        <span class="alg">${m.algorithm || ""}</span>
      </div>
      <div class="cipher"><span class="lbl">nonce</span> ${m.nonce || "-"}</div>
      <div class="cipher"><span class="lbl">ciphertext</span> ${(m.ciphertext || m.raw || "-")}</div>`;
    ul.appendChild(li);
  }
}

refresh();
setInterval(refresh, REFRESH_MS);