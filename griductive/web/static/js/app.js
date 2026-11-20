import {createCard, updateCard, element as el} from "./card_art.js";

const $ = id => document.getElementById(id);
const grid = $("grid");
const nodes = new Map();
let match, selected, tab="squad", hintCells=[], busy=false, running=false, timer, noticeTimer;
let sound=false, audio;
const metricLabels = {solved:"Solved",primary:"Primary vars",aux:"Aux vars",clauses:"CNF clauses",
  calls:"SAT calls",decisions:"Decisions",backtracks:"Backtracks",runtime_ms:"Runtime · ms"};
const msg = {
  NOT_PROVABLE:"Insufficient proof from the revealed clues.",
  CONTRADICTED:"The public clues prove the opposite verdict.",
  INCONSISTENT:"The active clues contradict one another.",
  SOLVED:"Every player has a proved verdict.",
  UNIQUE:"The complete clue set has exactly one solution.",
  AMBIGUOUS:"The complete clue set allows multiple solutions.",
  ACCEPTED:"Verdict proved. The player’s clue is now public."
};

async function request(path, payload) {
  const options = payload === undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)};
  const response=await fetch("/api/"+path,options);
  const data=await response.json();
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
function notice(result, message){
  clearTimeout(noticeTimer);
  const box=$("alert");
  box.dataset.result=result;
  box.textContent=[result.replaceAll("_"," "),message || msg[result]].filter(Boolean).join(" · ");
  box.hidden=false;
  noticeTimer=setTimeout(()=>box.hidden=true,4600);
}
function renderBoard(fresh) {
  const size=match.size;
  $("pitch").style.setProperty("--size",size);
  if(fresh){
    grid.replaceChildren();nodes.clear();
    $("col-rail").replaceChildren(...Array.from({length:size},(_,i)=>el("span","",String.fromCharCode(65+i))));
    $("row-rail").replaceChildren(...Array.from({length:size},(_,i)=>el("span","",i+1)));
  }
  for(const player of match.cards){
    let node=nodes.get(player.id);
    if(!node){
      node=createCard(player);nodes.set(player.id,node);grid.append(node);
      node.addEventListener("click",()=>selectCard(player.id));
    } else updateCard(node,player);
  }
}
function highlight(){
  if(!match) return;
  const player=match.cards.find(c=>c.id===selected);
  const targets=new Set(player?.clue?.targets || []);
  const second=new Set(player?.clue?.groups?.right || []);
  for(const [id,node] of nodes){
    node.classList.toggle("selected",id===selected);
    node.setAttribute("aria-pressed",String(id===selected));
    node.classList.toggle("linked",targets.has(id) && id!==selected);
    node.classList.toggle("linked-b",second.has(id) && id!==selected);
    node.classList.toggle("support",hintCells.includes(id) && id!==selected);
  }
  const lines=$("lines").querySelector("g");lines.replaceChildren();
  if(!player) return;
  const frame=$("lines").getBoundingClientRect();
  function center(id){
    const rect=nodes.get(id).getBoundingClientRect();
    return [rect.left+rect.width/2-frame.left,rect.top+rect.height/2-frame.top];
  }
  const [x1,y1]=center(selected);
  for(const id of new Set([...targets,...hintCells])){
    if(id===selected || !nodes.has(id)) continue;
    const [x2,y2]=center(id), len=Math.hypot(x2-x1,y2-y1);
    if(len===0) continue;
    const gap=nodes.get(id).offsetWidth*.46/len;
    const line=document.createElementNS("http://www.w3.org/2000/svg","line");
    for(const [key,value] of Object.entries({x1:x1+(x2-x1)*gap,y1:y1+(y2-y1)*gap,
      x2:x2-(x2-x1)*gap,y2:y2-(y2-y1)*gap,"marker-end":"url(#arrow)"})) line.setAttribute(key,value);
    if(second.has(id)) line.classList.add("group-b");
    lines.append(line);
  }
}
function selectCard(id, keepHint=false, focus=false){
  selected=id;if(!keepHint) hintCells=[];
  inspect();sheet();highlight();
  if(focus) nodes.get(id)?.focus({preventScroll:true});
}
function inspect(){
  const wrap=el("div","inspect-body");
  const player=match.cards.find(c=>c.id===selected);
  if(!player){
    wrap.append(el("p","","Select a player on the pitch to inspect a clue or call a verdict."));
  } else {
    const line=el("div","player-line");
    line.append(el("strong","",player.id+" · "+player.name),el("span","badge "+player.status,player.status));
    wrap.append(line,el("div","meta-line",[player.profession,player.ovr && player.ovr+" OVR",player.club,
      player.nation,player.tier,player.shirt_number && "#"+player.shirt_number].filter(Boolean).join(" · ")));
    if(player.clue){
      wrap.append(el("p","",player.clue.text));
      const more=el("details");more.append(el("summary","",player.clue.formula.type+" · Structured clue"),
        el("pre","",JSON.stringify(player.clue.formula,null,2)));wrap.append(more);
    } else {
      const buttons=el("div","verdicts");
      for(const status of ["INNOCENT","CRIMINAL"]){
        const b=el("button","",status);b.dataset.verdict=status;b.onclick=()=>perform("verdict",{cell:selected,status});
        buttons.append(b);
      }
      wrap.append(buttons);
    }
  }
  $("inspection").replaceChildren(wrap);
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
    row.insertCell().append(dot);row.onclick=()=>selectCard(p.id,false,true);
  }
  return table;
}
function sheet(){
  const pane=$("sheet-body"), scroll=pane.scrollTop;
  if(tab==="squad") pane.replaceChildren(roster());
  else if(tab==="trace"){
    const items=match.trace.map(step=>{
      const entry=el("div","trace-entry"), button=el("button","",step.step+". "+step.cell_id+" · "+step.verdict);
      button.onclick=()=>selectCard(step.cell_id,false,true);
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
function render(state, fresh=false){
  fresh ||= !match || state.puzzle!==match.puzzle;
  match=state;
  if(fresh){selected=state.cards.find(c=>c.status!=="UNKNOWN")?.id ?? state.cards[0].id;hintCells=[];}
  $("case-title").textContent=state.title;
  $("squad-count").textContent=state.total+" PLAYERS";
  $("cases").value=state.puzzle;
  $("metrics").replaceChildren(...Object.entries(metricLabels).map(([key,label])=>{
    const item=el("div","metric");
    const value=key==="solved"?state.solved+" / "+state.total:key==="runtime_ms"?state.metrics[key].toFixed(1):state.metrics[key];
    item.append(el("small","",label),el("strong","",value));return item;
  }));
  renderBoard(fresh);inspect();sheet();highlight();
}
function stopAuto(){
  running=false;clearTimeout(timer);$("auto").querySelector("span").textContent="Auto solve";
  $("auto").querySelector("use").setAttribute("href","#i-play");
}
async function perform(action,payload={},auto=false){
  if(busy) return;
  if(!auto) stopAuto();
  busy=true;
  const controls=["cases","step","instant","restart","hint","unique"];
  controls.forEach(id=>$(id).disabled=true);
  try{
    const result=await request(action,payload);
    hintCells=[];
    if(result.cell) selected=result.cell;
    if(action==="hint" && result.result==="HINT") hintCells=result.active;
    render(result.state,action==="restart" || action==="load");
    if(action==="uniqueness"){
      $("review-result").textContent=msg[result.result];$("review").showModal();
    } else if(result.result==="HINT"){
      signal(680);notice("HINT",result.cell+" is provably "+result.status+". Highlighted cards supplied the active clues.");
    } else if(result.result){
      const rejected=["INCONSISTENT","CONTRADICTED","NOT_PROVABLE"].includes(result.result);
      if(!auto || rejected || result.result==="SOLVED") notice(result.result);
      if(rejected && result.cell){
        const card=nodes.get(result.cell);card?.classList.add("rejected");setTimeout(()=>card?.classList.remove("rejected"),310);
      }
      signal(rejected?165:500);
    } else {$("alert").hidden=true;}
    return result;
  } catch(error){notice("ERROR",error.message);stopAuto();}
  finally {busy=false;controls.forEach(id=>$(id).disabled=false);}
}
async function autoTick(){
  if(!running) return;
  const r=await perform("step",{},true);
  if(!r || r.result!=="ACCEPTED"){stopAuto();return;}
  if(running) timer=setTimeout(autoTick,[1400,950,620,330,130][Number($("speed").value)-1]);
}
$("auto").onclick=()=>{
  if(running){stopAuto();return;}
  if(busy) return;
  running=true;$("auto").querySelector("span").textContent="Pause";$("auto").querySelector("use").setAttribute("href","#i-pause");autoTick();
};
for(const [id,action] of Object.entries({step:"step",hint:"hint",instant:"solve",restart:"restart",unique:"uniqueness"}))
  $(id).onclick=()=>perform(action);
$("cases").onchange=e=>perform("load",{puzzle:e.target.value});
$("view").onclick=()=>{
  const tilted=$("pitch").classList.toggle("angled");
  $("view").setAttribute("aria-pressed",tilted);
  $("view").querySelector("span").textContent=tilted?"2.5D pitch":"2D pitch";requestAnimationFrame(highlight);
};
$("sound").onclick=()=>{
  sound=!sound;const label=sound?"Mute sound":"Enable sound";
  $("sound").title=label;$("sound").setAttribute("aria-label",label);
  $("sound").querySelector("use").setAttribute("href",sound?"#i-sound":"#i-muted");if(sound) signal(600);
};
$("close-review").onclick=()=>$("review").close();
document.querySelectorAll("[data-tab]").forEach(button=>button.onclick=()=>{
  tab=button.dataset.tab;document.querySelectorAll("[data-tab]").forEach(b=>b.setAttribute("aria-selected",b===button));
  sheet();$("sheet-body").scrollTop=0;
});
new ResizeObserver(()=>requestAnimationFrame(highlight)).observe($("pitch"));
function fitPitch(){
  const space=window.innerHeight-($("pitch").getBoundingClientRect().top+window.scrollY)
    -document.querySelector(".board-foot").offsetHeight-document.querySelector(".bottom").offsetHeight-9;
  $("pitch").style.setProperty("--pitch-height",space+"px");
}
window.addEventListener("resize",fitPitch);
try{
  const [catalog,state]=await Promise.all([request("puzzles"),request("state")]);
  const groups=new Map();
  for(const puzzle of catalog){
    const label=puzzle.diagnostic?"Diagnostic puzzles":puzzle.size+" × "+puzzle.size;
    if(!groups.has(label)){const group=el("optgroup");group.label=label;groups.set(label,group);$("cases").append(group);}
    groups.get(label).append(new Option(puzzle.title,puzzle.id));
  }
  render(state);
  fitPitch();
} catch(error){notice("ERROR",error.message);}
