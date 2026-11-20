const kits = {
  LIV:["#bb2438","#f5e0ba"], RMA:["#f0ead9","#ae923f"], MCI:["#86bedc","#f2f8ff"],
  ATM:["#d65c60","#f0eadc"], BAR:["#344d8c","#c25264"], BAY:["#bb3340","#f3d9bf"],
  INT:["#e3a8bc","#302e3a"], SAN:["#eae8db","#3d4c4a"], ARS:["#af2b3a","#f5e6de"],
  ALN:["#e9c747","#3458a5"], TOT:["#e8e9ef","#28345b"]
};
const ribbons = {
  BRA:["#169655","#efd157","#34599e"], ENG:["#eee","#b94856","#eee"], BEL:["#252e35","#ebc640","#dd5161"],
  FRA:["#4d69b1","#ece7dc","#dd5260"], NOR:["#cb4a50","#edf2fa","#3c5490"], ESP:["#c33e4f","#edc956","#c33e4f"],
  GER:["#263039","#be3f47","#e3bf53"], POL:["#eee","#eee","#c73d52"], ARG:["#8ac8e7","#eee","#8ac8e7"],
  CRO:["#c9454f","#eee","#555daa"], POR:["#33765a","#c64c4c","#d6ad47"], EGY:["#d25255","#eee","#242d34"],
  KOR:["#eee","#c45061","#4976ab"], NED:["#c8444d","#eee","#4767af"]
};
const svgNS = "http://www.w3.org/2000/svg";
export function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function jersey(player) {
  const [body, trim] = kits[player.club] || ["#578491","#d4e3d9"];
  const ribbonsForPlayer = ribbons[player.nation] || [trim, body, trim];
  // The fallback is drawn locally, including the collar, kit number and club crest.
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox","0 0 100 92");
  svg.setAttribute("preserveAspectRatio","xMidYMax meet");
  svg.setAttribute("aria-hidden","true");
  svg.innerHTML = `<g stroke-linejoin="round">
    <path d="M30 50 43 45 57 45 70 50 82 55 95 72 82 82 74 71 73 92H25l-1-21-8 11L4 73l13-18z" fill="${body}" stroke="${trim}" stroke-width="1.5"/>
    <path d="m30 51 9-4 11 37 11-37 9 4-9 41H40z" fill="${trim}" opacity=".24"/>
    <path d="m41 45 2-8h14l2 8-9 9z" fill="#846e63"/>
    <path d="M35 20q0-17 16-17 16 0 16 16l-2 12-6 10-8 3-9-4-6-10z" fill="#516879"/>
    <path d="M35 22q-4-16 6-20 8-5 19 0 11 3 7 19l-6-9q-11 6-20 2l-4 9z" fill="#1d2d3a"/>
    <path d="m39 47 11 7 11-7-4 10-7-2-7 2z" fill="${trim}"/>
    <path d="M62 59h10v7l-5 4-5-4z" fill="${trim}"/>
    <text x="67" y="65" font-size="3.8" font-family="sans-serif" font-weight="bold" text-anchor="middle" fill="#263237"></text>
    <text x="49" y="83" font-size="24" font-family="Arial,sans-serif" font-weight="bold" text-anchor="middle" fill="${trim}"></text>
    ${ribbonsForPlayer.map((c,i)=>`<rect x="${26+3*i}" y="61" width="3" height="3.8" fill="${c}"/>`).join("")}
  </g>`;
  const labels=svg.querySelectorAll("text");
  labels[0].textContent=player.club;
  labels[1].textContent=player.shirt_number ?? "";
  return svg;
}

function updatePortrait(layer, url) {
  if (layer.dataset.url === (url || "")) return;
  layer.dataset.url = url || "";
  layer.querySelector(".photo-frame")?.remove();
  layer.classList.remove("photo");
  if (!url) return;

  const image = new Image();
  image.alt = "";
  image.decoding = "async";
  // Keep the kit visible until the portrait has decoded.
  image.onload = async () => {
    try { await image.decode(); } catch { return; }
    if (url !== layer.dataset.url || !image.naturalWidth) return;
    const frame = element("span", "photo-frame");
    frame.append(image);
    layer.append(frame);
    layer.classList.add("photo");
  };
  image.src = url;
}

function buildShield(player, preview = false) {
  const shield = element(preview ? "div" : "button", preview ? "shield card-preview" : "shield");
  if (preview) shield.setAttribute("aria-hidden", "true");
  else shield.type = "button";

  const motion = element("span", "card-motion");
  const shell = element("span", "card-shell");
  const face = element("span", "card-face");
  const art = element("span", "art");
  const rating = element("span", "rating");

  art.append(jersey(player));
  rating.append(element("b", "", player.ovr ?? "–"), element("small", "", player.profession));
  face.append(
    art, element("span", "wash"), element("span", "inner-trim"), rating,
    element("span", "coord", player.id), element("span", "clue-indicator", "Clue"),
    element("span", "plate", player.name), element("span", "status-crest"),
    element("span", "clue-strip"), element("span", "foil")
  );
  shell.append(face);
  motion.append(shell);
  if (!preview) motion.append(element("span", "card-back"));
  shield.append(motion);
  return shield;
}

function renderFace(shield, player) {
  shield.dataset.status = player.status;
  shield.querySelector(".status-crest").textContent = player.status;
  shield.querySelector(".clue-indicator").hidden = !player.clue;
  const strip = shield.querySelector(".clue-strip");
  strip.hidden = !player.clue;
  strip.textContent = player.clue?.text ?? "";
  updatePortrait(shield.querySelector(".art"), player.portrait);
}

export function createCardPreview(player) {
  const shield = buildShield(player, true);
  renderFace(shield, player);
  return shield;
}

export function createCard(player, { select, verdict, preview }) {
  const slot = element("div", "player-slot");
  slot.dataset.cell = player.id;

  const shield = buildShield(player);
  shield.dataset.cell = player.id;
  shield.addEventListener("click", () => select(player.id));
  shield.addEventListener("pointermove", event => {
    if (event.pointerType !== "mouse") return;
    const box = shield.getBoundingClientRect();
    const x = (event.clientX - box.left) / box.width - .5;
    const y = (event.clientY - box.top) / box.height - .5;
    shield.style.setProperty("--tilt-x", -y * 15 + "deg");
    shield.style.setProperty("--tilt-y", x * 19 + "deg");
  });

  const actions = element("div", "quick-verdicts");
  actions.setAttribute("role", "group");
  actions.setAttribute("aria-label", "Quick verdicts for " + player.name);
  for (const status of ["INNOCENT", "CRIMINAL"]) {
    const button = element("button", "", status);
    button.type = "button";
    button.dataset.verdict = status;
    button.setAttribute("aria-label", "Mark " + player.name + " " + status.toLowerCase());
    button.addEventListener("click", () => verdict(player.id, status));
    actions.append(button);
  }

  slot.addEventListener("pointerenter", () => preview(player.id));
  slot.addEventListener("pointerleave", () => preview(null));
  slot.addEventListener("focusin", () => preview(player.id));
  slot.addEventListener("focusout", event => {
    if (!slot.contains(event.relatedTarget)) preview(null);
  });
  slot.append(shield, element("span", "card-burst"), actions);
  updateCard(slot, player);
  return slot;
}

export function updateCard(slot, player) {
  const previous = slot.dataset.status;
  const shield = slot.querySelector(".shield");
  slot.dataset.status = player.status;
  slot.toggleAttribute("data-clue", Boolean(player.clue));
  slot.querySelector(".quick-verdicts").hidden = player.status !== "UNKNOWN";
  renderFace(shield, player);

  const summary = [player.id, player.name, player.profession, player.ovr, player.tier, player.status]
    .filter(Boolean).join(" · ");
  shield.title = player.clue ? summary + " — " + player.clue.text : summary;
  shield.setAttribute("aria-label", shield.title);
  if (previous === "UNKNOWN" && player.status !== "UNKNOWN") {
    slot.classList.add("flipping");
    setTimeout(() => slot.classList.remove("flipping"), 870);
  }
}
