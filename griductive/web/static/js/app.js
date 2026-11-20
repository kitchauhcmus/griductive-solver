import {createCard, createCardPreview, updateCard, element as el} from "./card_art.js";

const $ = id => document.getElementById(id);
const grid = $("grid");
const pitch = $("pitch");
const lineLayer = $("lines").querySelector("g");
const svgNS = "http://www.w3.org/2000/svg";
const nodes = new Map();
const formatNumber = new Intl.NumberFormat("en-US");
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");

let match, selected, previewed, hint;
let tab = "squad";
let busy = false, running = false, needsSync = false, sound = false;
let timer, noticeTimer, audio, laserFrame;
let lasers = [];

const metricLabels = {
  solved: "Solved", primary: "Primary", aux: "Aux", clauses: "Clauses",
  calls: "SAT calls", decisions: "Decisions", backtracks: "Backtracks", runtime_ms: "Time · ms"
};
const metricNodes = Object.entries(metricLabels).map(([key, label]) => {
  const item = el("div", "metric");
  item.dataset.key = key;
  const value = el("strong", "", "–");
  item.append(el("small", "", label), value);
  $("metrics").append(item);
  return {key, value};
});

const msg = {
  NOT_PROVABLE: "The revealed clues allow both verdicts.",
  CONTRADICTED: "The public clues prove the opposite verdict.",
  INCONSISTENT: "The active clues contradict one another.",
  SOLVED: "Every player has a proved verdict.",
  UNIQUE: "The complete clue set has exactly one solution.",
  AMBIGUOUS: "The complete clue set allows multiple solutions.",
  ACCEPTED: "Verdict proved. The player’s clue is now public.",
  ALREADY_SOLVED: "This player’s verdict has already been proved."
};
const varMessages = {
  NOT_PROVABLE: "NO GUESSING — NOT LOGICALLY FORCED",
  CONTRADICTED: "VAR OVERTURNED — OPPOSITE STATUS FORCED",
  INCONSISTENT: "PLAY STOPPED — INCONSISTENT CLUES"
};

class ConnectionError extends Error {}
class SessionChangedError extends Error {}

async function request(path, payload) {
  const options = {cache:"no-store"};
  if(payload !== undefined){
    options.method="POST";
    options.headers={"Content-Type":"application/json","X-Griductive-Session":match.session};
    options.body=JSON.stringify(payload);
  }
  let response, data;
  try{
    response=await fetch("/api/"+path,options);
    data=await response.json();
  } catch {
    throw new ConnectionError("Start the game with python main.py and use the URL printed in the terminal.");
  }
  if(response.status===409) throw new SessionChangedError(data.error);
  if(!response.ok) throw Error(data.error || "Request failed");
  return data;
}
function signal(frequency, duration=.12){
  if(!sound) return;
  try {
    audio ||= new AudioContext();
    const osc=audio.createOscillator(), gain=audio.createGain();
    osc.connect(gain);gain.connect(audio.destination);
    osc.frequency.setValueAtTime(frequency,audio.currentTime);
    osc.frequency.exponentialRampToValueAtTime(frequency*1.28,audio.currentTime+duration);
    gain.gain.setValueAtTime(.055,audio.currentTime);
    gain.gain.exponentialRampToValueAtTime(.001,audio.currentTime+duration);
    osc.start();osc.stop(audio.currentTime+duration);
  } catch { /* Audio is optional. */ }
}
function dismissNotice() {
  clearTimeout(noticeTimer);
  $("alert").hidden = true;
}

function notice(result, message) {
  clearTimeout(noticeTimer);
  const box = $("alert");
  const review = varMessages[result];
  box.dataset.result = result;
  box.dataset.review = Boolean(review);
  $("alert-label").textContent = review ? "VAR REVIEW" : result.replaceAll("_", " ");
  $("alert-message").textContent = review || message || msg[result] || "";
  $("alert-details").textContent = review ? result.replaceAll("_", " ") + " · " + msg[result] : "";
  $("alert-details").hidden = !review;
  box.hidden = false;
  box.classList.remove("notice-in");
  void box.offsetWidth;
  box.classList.add("notice-in");
  if (result !== "DISCONNECTED") noticeTimer = setTimeout(dismissNotice, 4600);
}

function renderBoard(fresh) {
  const size = match.size;
  pitch.dataset.size = size;
  pitch.style.setProperty("--size", size);
  if (fresh) {
    grid.replaceChildren();
    nodes.clear();
    $("col-rail").replaceChildren(...Array.from({length: size}, (_, i) => el("span", "", String.fromCharCode(65 + i))));
    $("row-rail").replaceChildren(...Array.from({length: size}, (_, i) => el("span", "", i + 1)));
  }
  for (const player of match.cards) {
    const slot = nodes.get(player.id);
    if (slot) {
      updateCard(slot, player);
    } else {
      const card = createCard(player, {
        select: selectCard,
        preview: previewCard,
        verdict: (cell, status) => perform("verdict", {cell, status})
      });
      nodes.set(player.id, card);
      grid.append(card);
    }
  }
}

function previewCard(id) {
  previewed = id;
  if (match) renderPitchClue();
}

function renderPitchClue() {
  const projected = match.cards.find(card => card.id === previewed && card.clue);
  const player = projected ?? match.cards.find(card => card.id === selected);
  const activeHint = player?.id === hint?.cell && !player?.clue ? hint : null;
  const banner = $("pitch-clue");
  banner.hidden = !player?.clue && !activeHint;
  if (banner.hidden) return;
  banner.dataset.status = player.status;
  banner.querySelector(".pitch-clue-source span").textContent = activeHint ? "Tactical hint" : "Active clue";
  $("pitch-clue-owner").textContent = player.id + " · " + player.name;
  $("pitch-clue-text").textContent = player.clue?.text ??
    (player.name + " is provably " + activeHint.status + ". Highlighted cards have active clues.");
}

function clueLinks(clue) {
  const groups = clue?.groups;
  const overlap = clue?.formula.type === "OVERLAP_COUNT";
  const left = new Set(overlap ? groups?.region : groups?.left);
  const right = new Set(overlap ? groups?.left : groups?.right);
  const pair = ["SAME", "DIFFERENT"].includes(clue?.formula.type);
  const pairCells = pair ? [clue.formula.person, clue.formula.other] : [];

  return new Map((clue?.targets || []).map(id => {
    const color = pairCells.includes(id) ? "pair" :
      right.has(id) ? (left.has(id) ? "both" : "b") : "a";
    return [id, color];
  }));
}

function buildLaser(from, to, color) {
  const group = document.createElementNS(svgNS, "g");
  group.classList.add("laser");
  group.dataset.link = color;
  const paths = ["laser-halo", "laser-track", "laser-pulse"].map(className => {
    const path = document.createElementNS(svgNS, "path");
    path.classList.add(className);
    return path;
  });
  const tip = document.createElementNS(svgNS, "circle");
  tip.setAttribute("r", "2.4");
  group.append(...paths, tip);
  return {from, to, group, paths, tip};
}

function updateHighlights() {
  const player = match.cards.find(card => card.id === selected);
  const targets = clueLinks(player?.clue);
  if (hint?.cell === selected) {
    for (const id of hint.active) targets.set(id, "hint");
  }

  for (const [id, slot] of nodes) {
    slot.classList.toggle("selected", id === selected);
    slot.querySelector(".shield").setAttribute("aria-pressed", String(id === selected));
    const color = id === selected ? undefined : targets.get(id);
    if (color) slot.dataset.link = color;
    else delete slot.dataset.link;
  }
  lasers = [...targets].flatMap(([cell, color]) => {
    if (cell === selected || !nodes.has(cell)) return [];
    return [color === "hint" ? buildLaser(cell, selected, color) : buildLaser(selected, cell, color)];
  });
  lineLayer.replaceChildren(...lasers.map(laser => laser.group));
  drawLasers();
}

function drawLasers() {
  if (!lasers.length) return;
  const frame = $("lines").getBoundingClientRect();
  const locations = new Map();
  const location = id => {
    if (!locations.has(id)) {
      const rect = nodes.get(id).querySelector(".shield").getBoundingClientRect();
      locations.set(id, {
        x: rect.left + rect.width / 2 - frame.left,
        y: rect.top + rect.height / 2 - frame.top,
        width: rect.width,
        height: rect.height
      });
    }
    return locations.get(id);
  };

  for (const laser of lasers) {
    const a = location(laser.from), b = location(laser.to);
    const length = Math.hypot(b.x - a.x, b.y - a.y);
    if (!length || !a.width || !b.width) continue;
    const dx = (b.x - a.x) / length, dy = (b.y - a.y) / length;
    const startGap = Math.min(length * .36, .46 / Math.hypot(dx / a.width, dy / a.height));
    const endGap = Math.min(length * .36, .47 / Math.hypot(dx / b.width, dy / b.height));
    const x1 = a.x + dx * startGap, y1 = a.y + dy * startGap;
    const x2 = b.x - dx * endGap, y2 = b.y - dy * endGap;
    const bend = Math.min(29, length * .11);
    const cx = (x1 + x2) / 2 - dy * bend, cy = (y1 + y2) / 2 + dx * bend;
    const d = "M" + x1 + "," + y1 + " Q" + cx + "," + cy + " " + x2 + "," + y2;
    for (const path of laser.paths) path.setAttribute("d", d);
    laser.tip.setAttribute("cx", x2);
    laser.tip.setAttribute("cy", y2);
  }
}

function followPitchTransform() {
  cancelAnimationFrame(laserFrame);
  if (reducedMotion.matches) {
    laserFrame = requestAnimationFrame(drawLasers);
    return;
  }
  const end = performance.now() + 410;
  function follow(time) {
    drawLasers();
    if (time < end) laserFrame = requestAnimationFrame(follow);
  }
  laserFrame = requestAnimationFrame(follow);
}

function selectCard(id, focus = false) {
  if (id !== selected) hint = undefined;
  selected = id;
  inspect();
  sheet();
  renderPitchClue();
  updateHighlights();
  if (focus) nodes.get(id)?.querySelector(".shield").focus({preventScroll: true});
}

function inspect() {
  const wrap = el("div", "inspect-body");
  const panel = $("inspection");
  const player = match.cards.find(card => card.id === selected);
  const cell = $("inspector-cell");
  cell.hidden = !player;
  cell.textContent = player?.id ?? "";
  if (!player) {
    wrap.append(el("p", "selection-note", "Select a player to read a clue or call a verdict."));
    panel.replaceChildren(wrap);
    return;
  }

  const ticket = el("div", "inspector-ticket");
  const thumbnail = el("div", "inspect-card");
  thumbnail.append(createCardPreview(player));
  const profile = el("div", "inspect-profile");
  const line = el("div", "player-line");
  line.append(el("strong", "", player.name), el("span", "badge " + player.status, player.status));
  const meta = [player.profession, player.ovr && player.ovr + " OVR", player.club,
    player.nation, player.tier, player.shirt_number && "#" + player.shirt_number]
    .filter(Boolean).join(" · ");
  profile.append(line, el("div", "meta-line", meta));
  ticket.append(thumbnail, profile);
  wrap.append(ticket);

  const sameCard = panel.dataset.cell === player.id;
  const scroll = sameCard ? panel.scrollTop : 0;
  panel.dataset.cell = player.id;
  if (player.clue) {
    wrap.append(el("p", "clue-text", player.clue.text));
    if (player.clue.groups.left && player.clue.groups.right) {
      const legend = el("p", "group-legend");
      legend.append(el("span", "group-key", "Region A"), el("span", "group-key", "Region B"));
      wrap.append(legend);
    }
    const more = el("details", "structured");
    const label = el("summary", "");
    label.append(el("span", "", player.clue.formula.type), document.createTextNode(" Structured clue"));
    more.append(label, el("pre", "", JSON.stringify(player.clue.formula, null, 2)));
    more.open = Boolean(sameCard && panel.querySelector("details")?.open);
    wrap.append(more);
  } else {
    const context = hint?.cell === player.id ?
      "Hint: " + player.name + " is provably " + hint.status + "." : "Call a verdict using the revealed clues.";
    wrap.append(el("p", "selection-note", context));
    const buttons = el("div", "verdicts");
    for (const status of ["INNOCENT", "CRIMINAL"]) {
      const button = el("button", "", status);
      button.type = "button";
      button.dataset.verdict = status;
      button.addEventListener("click", () => perform("verdict", {cell: player.id, status}));
      buttons.append(button);
    }
    wrap.append(buttons);
  }
  panel.replaceChildren(wrap);
  panel.scrollTop = scroll;
}

function roster(){
  const table=el("table"), head=table.createTHead().insertRow();
  ["Pos","Cell","Player","OVR","Status"].forEach(s=>head.append(el("th","",s)));
  const body=table.createTBody();
  for(const p of match.cards){
    const row=body.insertRow();row.className="roster-row"+(selected===p.id?" active":"");
    row.insertCell().append(el("span","pos",p.profession));row.insertCell().textContent=p.id;
    const button=el("button","player-link",p.name);row.insertCell().append(button);
    row.insertCell().textContent=p.ovr ?? "–";
    const dot=el("span","dot "+p.status);dot.setAttribute("aria-label",p.status);dot.title=p.status;dot.setAttribute("role","img");
    row.insertCell().append(dot);row.onclick=()=>selectCard(p.id,true);
  }
  return table;
}
function sheet(){
  const pane=$("sheet-body"), scroll=pane.scrollTop;
  if(tab==="squad") pane.replaceChildren(roster());
  else if(tab==="trace"){
    const items=match.trace.map(step=>{
      const entry=el("div","trace-entry"), button=el("button","",step.step+". "+step.cell_id+" · "+step.verdict);
      button.onclick=()=>selectCard(step.cell_id,true);
      entry.append(button,el("p","",step.sat_queries.join(" / ")),el("p","","Active: "+step.active_clues.join(", ")),
        el("p","","Revealed: "+step.revealed_clue));return entry;
    });
    pane.replaceChildren(...(items.length?items:[el("p","empty","Proved verdicts appear here as the match progresses.")]));
  } else{
    const detail=el("div","detail"), clues=match.cards.filter(c=>c.clue);
    detail.append(el("strong","",clues.length+" active clues · "+match.metrics.clauses+" clauses"));
    for(const c of clues) detail.append(el("p","",c.id+" · "+c.clue.text));
    const more=el("details");more.append(el("summary","","CNF preview ("+match.clause_preview.length+")"),
      el("pre","",match.clause_preview.map(c=>c.join(" ")+" 0").join("\n")));detail.append(more);pane.replaceChildren(detail);
  }
  pane.scrollTop=scroll;
}
function renderMetrics(state, fresh) {
  for (const {key, value} of metricNodes) {
    const next = key === "solved" ? state.solved + " / " + state.total :
      key === "runtime_ms" ? state.metrics[key].toFixed(1) : formatNumber.format(state.metrics[key]);
    if (value.textContent === next) continue;
    value.textContent = next;
    if (!fresh && !reducedMotion.matches) {
      value.getAnimations().forEach(animation => animation.cancel());
      value.animate([{opacity: .65, transform: "translateY(2px)"},
        {opacity: 1, transform: "translateY(0)"}], {duration: 270, easing: "ease-out"});
    }
  }
}

function render(state, fresh = false) {
  fresh ||= !match || state.puzzle !== match.puzzle;
  match = state;
  if (fresh) {
    selected = state.cards.find(card => card.status !== "UNKNOWN")?.id ?? state.cards[0]?.id;
    hint = undefined;
    previewed = undefined;
  }
  $("case-title").textContent = state.title;
  $("squad-count").textContent = state.total + " players";
  $("cases").value = state.puzzle;
  renderMetrics(state, fresh);
  renderBoard(fresh);
  inspect();
  sheet();
  renderPitchClue();
  updateHighlights();
}

const actionButtons = {step: "step", hint: "hint", instant: "solve", restart: "restart", unique: "uniqueness"};

function setBusy(value) {
  busy = value;
  for (const id of ["cases", ...Object.keys(actionButtons)]) $(id).disabled = value;
  document.querySelectorAll("button[data-verdict]").forEach(button => { button.disabled = value; });
}

function setAuto(value) {
  running = value;
  clearTimeout(timer);
  const button = $("auto");
  button.setAttribute("aria-pressed", String(value));
  button.querySelector("span").textContent = value ? "Pause" : "Auto solve";
  button.querySelector("use").setAttribute("href", value ? "#i-pause" : "#i-play");
}

async function refreshMatch() {
  const [catalog, state] = await Promise.all([request("puzzles"), request("state")]);
  const groups = new Map();
  for (const puzzle of catalog) {
    const label = puzzle.diagnostic ? "Diagnostic puzzles" : puzzle.size + " × " + puzzle.size;
    if (!groups.has(label)) {
      const group = el("optgroup");
      group.label = label;
      groups.set(label, group);
    }
    groups.get(label).append(new Option(puzzle.title, puzzle.id));
  }
  $("cases").replaceChildren(...groups.values());
  render(state, true);
  needsSync = false;
}

async function perform(action, payload = {}, auto = false) {
  if (busy) return;
  if (!auto) setAuto(false);
  setBusy(true);

  try {
    if (!match || needsSync) {
      await refreshMatch();
      setAuto(false);
      notice("CONNECTED", "Board refreshed. Choose an action to continue.");
      return;
    }
    const result = await request(action, payload);
    if (result.cell) selected = result.cell;
    hint = result.result === "HINT" ? {
      cell: result.cell, status: result.status, active: result.active
    } : undefined;
    render(result.state, action === "restart" || action === "load");

    if (action === "uniqueness") {
      dismissNotice();
      $("review-result").textContent = msg[result.result];
      $("review").showModal();
    } else if (result.result === "HINT") {
      signal(680);
      notice("HINT", result.cell + " is provably " + result.status + ". Highlighted cards have active clues.");
    } else if (result.result) {
      const rejected = Boolean(varMessages[result.result]);
      if (!auto || rejected || result.result === "SOLVED") notice(result.result);
      if (rejected && result.cell) {
        const slot = nodes.get(result.cell);
        slot?.classList.add("rejected");
        setTimeout(() => slot?.classList.remove("rejected"), 330);
      }
      signal(rejected ? 165 : 500);
    } else {
      dismissNotice();
    }
    return result;
  } catch (error) {
    setAuto(false);
    if (match) $("cases").value = match.puzzle;
    if (error instanceof SessionChangedError) {
      needsSync = true;
      try {
        await refreshMatch();
        notice("CONNECTED", "Game restarted. Choose an action on the refreshed board.");
      } catch (refreshError) {
        notice("DISCONNECTED", refreshError.message);
      }
    } else if (error instanceof ConnectionError) {
      needsSync = true;
      notice("DISCONNECTED", error.message);
    } else {
      notice("ERROR", error.message);
    }
  } finally {
    setBusy(false);
  }
}

async function autoTick() {
  if (!running) return;
  const result = await perform("step", {}, true);
  if (result?.result !== "ACCEPTED") {
    setAuto(false);
    return;
  }
  if (running) timer = setTimeout(autoTick, [1450, 1060, 780, 505, 310][Number($("speed").value) - 1]);
}

$("auto").onclick = () => {
  if (running) {
    setAuto(false);
  } else if (!busy) {
    dismissNotice();
    setAuto(true);
    autoTick();
  }
};

for (const [id, action] of Object.entries(actionButtons)) $(id).onclick = () => perform(action);
$("cases").onchange = event => perform("load", {puzzle: event.target.value});

$("view").onclick = () => {
  const tilted = pitch.classList.toggle("angled");
  const button = $("view");
  button.setAttribute("aria-pressed", String(tilted));
  button.title = tilted ? "Switch to 2D pitch" : "Switch to 2.5D pitch";
  button.querySelector("span").textContent = tilted ? "2.5D Pitch" : "2D Pitch";
  followPitchTransform();
};

$("sound").onclick = () => {
  sound = !sound;
  const label = sound ? "Mute sound" : "Enable sound";
  const button = $("sound");
  button.setAttribute("aria-pressed", String(sound));
  button.setAttribute("aria-label", label);
  button.title = label;
  button.querySelector("use").setAttribute("href", sound ? "#i-sound" : "#i-muted");
  if (sound) signal(600);
};

$("close-alert").onclick = dismissNotice;
$("close-review").onclick = () => $("review").close();

const sheetTabs = [...document.querySelectorAll("[data-tab]")];
function selectTab(button) {
  tab = button.dataset.tab;
  for (const other of sheetTabs) {
    other.setAttribute("aria-selected", String(other === button));
    other.tabIndex = other === button ? 0 : -1;
  }
  $("sheet-body").setAttribute("aria-labelledby", button.id);
  if (match) {
    sheet();
    $("sheet-body").scrollTop = 0;
  }
}

sheetTabs.forEach((button, index) => {
  button.addEventListener("click", () => selectTab(button));
  button.addEventListener("keydown", event => {
    const last = sheetTabs.length - 1;
    const target = {
      ArrowLeft: (index + last) % sheetTabs.length,
      ArrowRight: (index + 1) % sheetTabs.length,
      Home: 0,
      End: last
    }[event.key];
    if (target === undefined) return;
    event.preventDefault();
    selectTab(sheetTabs[target]);
    sheetTabs[target].focus();
  });
});

new ResizeObserver(() => requestAnimationFrame(drawLasers)).observe($("pitch-stage"));

setBusy(true);
try {
  await refreshMatch();
} catch (error) {
  notice("DISCONNECTED", error.message);
} finally {
  setBusy(false);
}
