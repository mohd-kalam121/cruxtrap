// CruxTrap dashboard behaviour. Loaded from /static so it satisfies the CSP (no inline JS).
// All attacker-controlled strings are inserted with textContent, never innerHTML.
(function () {
  "use strict";

  // Clickable table rows
  document.querySelectorAll("tr.click[data-href]").forEach(function (tr) {
    tr.addEventListener("click", function (e) {
      if (e.target.closest("a")) return;
      window.location = tr.getAttribute("data-href");
    });
  });

  // Live stats tiles
  var live = document.getElementById("live");
  var fmt = function (k, v) {
    if (v === null || v === undefined) return "—";
    if (k === "epsilon") return Number(v).toFixed(3);
    if (k === "avg_commands") return Number(v).toFixed(2);
    return Number(v).toLocaleString("en-US");
  };
  function refresh() {
    fetch("/api/stats", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (s) {
        live.classList.remove("stale");
        document.querySelectorAll("[data-stat]").forEach(function (el) {
          var k = el.getAttribute("data-stat");
          var next = fmt(k, s[k]);
          if (el.textContent !== next) {
            el.textContent = next;
            el.classList.add("flash");
            setTimeout(function () { el.classList.remove("flash"); }, 1200);
          }
        });
      })
      .catch(function () { live.classList.add("stale"); });
  }
  if (document.querySelector("[data-stat]")) setInterval(refresh, 10000);
  else if (live) live.style.visibility = "hidden";

  // Session replay
  var dataEl = document.getElementById("replay-data");
  if (!dataEl) return;
  var steps = JSON.parse(dataEl.textContent);
  var meta = JSON.parse(document.getElementById("replay-meta").textContent);
  var term = document.getElementById("term");
  var playBtn = document.getElementById("play");
  var speedSel = document.getElementById("speed");
  var COLORS = { ALLOW: "#3fb950", DELAY: "#d29922", FAKE: "#a371f7", TARPIT: "#db6d28", BLOCK: "#f85149" };
  var prompt = meta.user + "@ubuntu-srv01:~" + (meta.user === "root" ? "# " : "$ ");
  var timer = null;

  function span(cls, text, color) {
    var s = document.createElement("span");
    s.className = cls;
    s.textContent = text;
    if (color) s.style.color = color;
    return s;
  }
  function line(step) {
    term.appendChild(span("p", prompt));
    term.appendChild(document.createTextNode(step.cmd));
    term.appendChild(span("a", "[" + step.action + " · " + step.category + "]", COLORS[step.action]));
    term.appendChild(document.createTextNode("\n"));
    term.scrollTop = term.scrollHeight;
  }
  function showAll() {
    term.textContent = "";
    steps.forEach(line);
    if (!steps.length) term.textContent = "(no commands)";
  }
  function stop() {
    if (timer) clearTimeout(timer);
    timer = null;
    playBtn.textContent = "▶ Play";
  }
  function play() {
    if (timer) { stop(); showAll(); return; }
    term.textContent = "";
    playBtn.textContent = "■ Stop";
    var i = 0;
    var cursor = span("cursor", " ");
    function next() {
      if (cursor.parentNode) cursor.remove();
      if (i >= steps.length) { stop(); return; }
      line(steps[i]);
      term.appendChild(cursor);
      var gap = i + 1 < steps.length ? (steps[i + 1].t - steps[i].t) : 0;
      i += 1;
      var speed = Number(speedSel.value) || 1;
      timer = setTimeout(next, Math.min(4000, Math.max(120, (gap * 1000) / speed)));
    }
    next();
  }
  playBtn.addEventListener("click", play);
  showAll();
})();
