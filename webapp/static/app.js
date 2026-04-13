const HOLD_TYPES = ["Start", "Any", "Finish", "Feet"];
const HOLD_COLORS = {
  Start: "#62d852",
  Any: "#53e6e6",
  Finish: "#bd45ff",
  Feet: "#f3a21b",
};
const GRID = { cols: 35, rows: 39 };

const state = {
  sourceClimbs: [],
  savedClimbs: [],
  currentClimb: null,
  mode: "view",
  view: "2d",
  selectedHoldType: "Start",
  scanCache: new Map(),
  sequence: [],
  animationStart: performance.now(),
  betaVisible: false,
  baseImage: null,
  templateImage: null,
};

const boardCanvas = document.querySelector("#boardCanvas");
const animationCanvas = document.querySelector("#animationCanvas");
const sampleCanvas = document.querySelector("#sampleCanvas");
const ctx = boardCanvas.getContext("2d");
const animCtx = animationCanvas.getContext("2d");
const sampleCtx = sampleCanvas.getContext("2d", { willReadFrequently: true });

const climbSelect = document.querySelector("#climbSelect");
const viewMode = document.querySelector("#viewMode");
const setModeButton = document.querySelector("#setModeButton");
const generateBetaButton = document.querySelector("#generateBetaButton");
const setterPanel = document.querySelector("#setterPanel");
const statusText = document.querySelector("#statusText");
const climbName = document.querySelector("#climbName");
const climbMeta = document.querySelector("#climbMeta");
const holdCounts = document.querySelector("#holdCounts");
const newName = document.querySelector("#newName");
const newGrade = document.querySelector("#newGrade");
const newAngle = document.querySelector("#newAngle");

function emptyHolds() {
  return { Start: [], Any: [], Finish: [], Feet: [] };
}

function boardBox() {
  return { x: 0, y: 320, w: 750, h: 835 };
}

function holdToPoint(hold) {
  const x = 20.8 * hold.x + 0.7;
  const y = 1153.3 - 20.8 * hold.y;
  if (state.view === "3d") {
    const depth = (GRID.rows - hold.y) / GRID.rows;
    return {
      x: x + 72 * depth - 36,
      y: y - 70 * depth,
      z: depth,
    };
  }
  return { x, y, z: 0 };
}

function pointToHold(px, py) {
  let best = { x: 1, y: 1, d: Infinity };
  for (let y = 1; y <= GRID.rows; y += 1) {
    for (let x = 1; x <= GRID.cols; x += 1) {
      const point = holdToPoint({ x, y });
      const d = Math.hypot(px - point.x, py - point.y);
      if (d < best.d) best = { x, y, d };
    }
  }
  return best.d < 18 ? { x: best.x, y: best.y } : null;
}

function classifyPixel(r, g, b) {
  if (g > 190 && r < 150 && b < 150) return "Start";
  if (b > 145 && g > 185 && r < 150) return "Any";
  if (r > 170 && b > 145 && g < 150) return "Finish";
  if (r > 170 && g > 130 && b < 130) return "Feet";
  return null;
}

async function scanSourceClimb(climb) {
  if (state.scanCache.has(climb.id)) return state.scanCache.get(climb.id);
  const image = await loadImage(climb.sourceImage);
  sampleCtx.clearRect(0, 0, sampleCanvas.width, sampleCanvas.height);
  sampleCtx.drawImage(image, 0, 0, sampleCanvas.width, sampleCanvas.height);
  const holds = detectColoredHoldComponents();
  const scanned = { ...climb, holds, baseImage: image };
  state.scanCache.set(climb.id, scanned);
  return scanned;
}

function detectColoredHoldComponents() {
  const width = sampleCanvas.width;
  const height = sampleCanvas.height;
  const data = sampleCtx.getImageData(0, 0, width, height).data;
  const labels = new Uint8Array(width * height);
  const holds = emptyHolds();
  const typeIndex = { Start: 1, Any: 2, Finish: 3, Feet: 4 };
  const indexType = ["", "Start", "Any", "Finish", "Feet"];

  for (let y = 290; y < 1220; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const i = (y * width + x) * 4;
      const holdType = classifyPixel(data[i], data[i + 1], data[i + 2]);
      if (holdType) labels[y * width + x] = typeIndex[holdType];
    }
  }

  const visited = new Uint8Array(width * height);
  const queue = [];
  const seenHolds = new Set();
  for (let y = 290; y < 1220; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const start = y * width + x;
      const label = labels[start];
      if (!label || visited[start]) continue;
      let minX = x;
      let maxX = x;
      let minY = y;
      let maxY = y;
      let count = 0;
      let sumX = 0;
      let sumY = 0;
      queue.length = 0;
      queue.push(start);
      visited[start] = 1;
      while (queue.length) {
        const current = queue.pop();
        const cx = current % width;
        const cy = Math.floor(current / width);
        count += 1;
        sumX += cx;
        sumY += cy;
        minX = Math.min(minX, cx);
        maxX = Math.max(maxX, cx);
        minY = Math.min(minY, cy);
        maxY = Math.max(maxY, cy);
        for (const neighbor of [current - 1, current + 1, current - width, current + width]) {
          if (neighbor < 0 || neighbor >= labels.length || visited[neighbor] || labels[neighbor] !== label) continue;
          visited[neighbor] = 1;
          queue.push(neighbor);
        }
      }
      const componentWidth = maxX - minX + 1;
      const componentHeight = maxY - minY + 1;
      if (count < 24 || componentWidth > 70 || componentHeight > 70) continue;
      const center = { x: sumX / count, y: sumY / count };
      const hx = Math.round((center.x - 0.7) / 20.8);
      const hy = Math.round((1153.3 - center.y) / 20.8);
      if (hx < 1 || hx > GRID.cols || hy < 1 || hy > GRID.rows) continue;
      const holdType = indexType[label];
      const key = `${holdType}:${hx}:${hy}`;
      if (seenHolds.has(key)) continue;
      seenHolds.add(key);
      holds[holdType].push([hx, hy]);
    }
  }
  return holds;
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = src;
  });
}

function normalizeClimb(raw) {
  const holds = emptyHolds();
  for (const holdType of HOLD_TYPES) {
    for (const hold of raw.holds?.[holdType] || []) {
      const x = Array.isArray(hold) ? hold[0] : hold.x;
      const y = Array.isArray(hold) ? hold[1] : hold.y;
      holds[holdType].push([Number(x), Number(y)]);
    }
  }
  return {
    name: raw.name || raw.Name || raw.id || "Untitled",
    grade: raw.grade || raw.Grade || "Unknown",
    angle: raw.angle || raw.Angle || "Unknown",
    holds,
  };
}

function drawBoard() {
  ctx.clearRect(0, 0, boardCanvas.width, boardCanvas.height);
  ctx.fillStyle = "#050505";
  ctx.fillRect(0, 0, boardCanvas.width, boardCanvas.height);
  drawWall();
  if (state.currentClimb) drawClimbHolds(state.currentClimb.holds);
}

function drawWall() {
  ctx.save();
  const image = state.baseImage || state.templateImage;
  if (state.view === "3d") {
    const box = boardBox();
    ctx.fillStyle = "#050505";
    ctx.fillRect(0, 0, boardCanvas.width, boardCanvas.height);
    ctx.strokeStyle = "#555";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(box.x - 44, box.y + box.h);
    ctx.lineTo(box.x + box.w + 44, box.y + box.h);
    ctx.lineTo(box.x + box.w - 44, box.y - 58);
    ctx.lineTo(box.x - 132, box.y - 58);
    ctx.closePath();
    ctx.clip();
    if (image) {
      ctx.setTransform(0.96, -0.08, 0.12, 0.96, -58, 120);
      ctx.drawImage(image, 0, 0, boardCanvas.width, boardCanvas.height);
      ctx.setTransform(1, 0, 0, 1, 0, 0);
    }
    ctx.beginPath();
    ctx.moveTo(box.x - 44, box.y + box.h);
    ctx.lineTo(box.x + box.w + 44, box.y + box.h);
    ctx.lineTo(box.x + box.w - 44, box.y - 58);
    ctx.lineTo(box.x - 132, box.y - 58);
    ctx.closePath();
    ctx.stroke();
  } else if (image) {
    ctx.drawImage(image, 0, 0, boardCanvas.width, boardCanvas.height);
    if (image === state.templateImage) maskLightbulb();
  } else {
    ctx.fillStyle = "#050505";
    ctx.fill();
  }
  ctx.restore();
}

function maskLightbulb() {
  ctx.save();
  ctx.fillStyle = "#171717";
  ctx.fillRect(330, 1246, 92, 88);
  ctx.restore();
}

function drawClimbHolds(holds) {
  ctx.save();
  ctx.lineWidth = 5;
  for (const holdType of HOLD_TYPES) {
    ctx.strokeStyle = HOLD_COLORS[holdType];
    for (const [x, y] of holds[holdType] || []) {
      const p = holdToPoint({ x, y });
      ctx.beginPath();
      ctx.arc(p.x, p.y, 17, 0, Math.PI * 2);
      ctx.stroke();
    }
  }
  ctx.restore();
}

function drawMonkeyFrame(time) {
  animCtx.clearRect(0, 0, animationCanvas.width, animationCanvas.height);
  if (!state.betaVisible || !state.currentClimb || state.sequence.length === 0) return;
  const elapsed = ((time - state.animationStart) / 1000) % 8.5;
  const dropPhase = elapsed > 7.2;
  const progress = Math.min(elapsed / 7.2, 1);
  const pose = climberPose(progress, dropPhase ? (elapsed - 7.2) / 1.3 : 0);
  drawForceVector(pose);
  drawMonkey(pose);
}

function climberPose(progress, dropProgress) {
  const handPath = state.sequence.map((move) => holdToPoint(move));
  const index = Math.min(handPath.length - 1, Math.floor(progress * Math.max(1, handPath.length - 1)));
  const nextIndex = Math.min(handPath.length - 1, index + 1);
  const local = handPath.length <= 1 ? 0 : (progress * (handPath.length - 1)) % 1;
  const active = lerpPoint(handPath[index], handPath[nextIndex], local);
  const previous = handPath[Math.max(0, index - 1)] || active;
  const center = {
    x: active.x * 0.65 + previous.x * 0.35,
    y: active.y + 118,
  };
  if (dropProgress > 0) {
    center.y += 620 * easeIn(dropProgress);
  }
  const torso = { x: center.x, y: center.y - 20 };
  const shoulder = { x: torso.x, y: torso.y - 44 };
  const hip = { x: torso.x, y: torso.y + 44 };
  const leftHand = clampLimb({ x: previous.x - 8, y: previous.y }, shoulder, 150);
  const rightHand = clampLimb({ x: active.x + 8, y: active.y }, shoulder, 150);
  const feet = nearestFeet(hip);
  return {
    head: { x: shoulder.x, y: shoulder.y - 38 },
    shoulder,
    torso,
    hip,
    leftHand,
    rightHand,
    leftFoot: clampLimb(feet[0], hip, 170),
    rightFoot: clampLimb(feet[1], hip, 170),
    force: { x: (rightHand.x + leftHand.x) / 2 - hip.x, y: -90 },
  };
}

function nearestFeet(hip) {
  const footHolds = [...(state.currentClimb.holds.Feet || []), ...(state.currentClimb.holds.Any || [])]
    .map(([x, y]) => holdToPoint({ x, y }))
    .filter((point) => point.y > hip.y - 10)
    .sort((a, b) => Math.hypot(a.x - hip.x, a.y - hip.y) - Math.hypot(b.x - hip.x, b.y - hip.y));
  if (footHolds.length >= 2) return [footHolds[0], footHolds[1]];
  const wallFoot = { x: hip.x - 42, y: hip.y + 118 };
  return [footHolds[0] || wallFoot, { x: hip.x + 42, y: hip.y + 118 }];
}

function drawMonkey(pose) {
  animCtx.save();
  animCtx.lineCap = "round";
  animCtx.lineJoin = "round";
  animCtx.strokeStyle = "#5b4a33";
  animCtx.lineWidth = 18;
  limb(pose.shoulder, pose.leftHand);
  limb(pose.shoulder, pose.rightHand);
  limb(pose.hip, pose.leftFoot);
  limb(pose.hip, pose.rightFoot);
  animCtx.strokeStyle = "#704f2d";
  animCtx.lineWidth = 24;
  limb(pose.shoulder, pose.hip);
  animCtx.fillStyle = "#7c5c36";
  circle(pose.head, 25);
  animCtx.fillStyle = "#e5d0a6";
  circle({ x: pose.head.x, y: pose.head.y + 4 }, 15);
  animCtx.fillStyle = "#101010";
  circle({ x: pose.head.x - 8, y: pose.head.y - 2 }, 2.5);
  circle({ x: pose.head.x + 8, y: pose.head.y - 2 }, 2.5);
  animCtx.restore();
}

function limb(a, b) {
  animCtx.beginPath();
  animCtx.moveTo(a.x, a.y);
  animCtx.lineTo((a.x + b.x) / 2, (a.y + b.y) / 2 + 12);
  animCtx.lineTo(b.x, b.y);
  animCtx.stroke();
}

function circle(p, r) {
  animCtx.beginPath();
  animCtx.arc(p.x, p.y, r, 0, Math.PI * 2);
  animCtx.fill();
}

function drawForceVector(pose) {
  animCtx.save();
  animCtx.strokeStyle = "#f3a21b";
  animCtx.lineWidth = 4;
  animCtx.beginPath();
  animCtx.moveTo(pose.hip.x, pose.hip.y);
  animCtx.lineTo(pose.hip.x + pose.force.x * 0.45, pose.hip.y + pose.force.y * 0.45);
  animCtx.stroke();
  animCtx.restore();
}

function clampLimb(target, anchor, maxLength) {
  const dx = target.x - anchor.x;
  const dy = target.y - anchor.y;
  const d = Math.max(1, Math.hypot(dx, dy));
  if (d <= maxLength) return target;
  return { x: anchor.x + (dx / d) * maxLength, y: anchor.y + (dy / d) * maxLength };
}

function lerpPoint(a, b, t) {
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
}

function easeIn(t) {
  return Math.min(1, t) * Math.min(1, t);
}

async function requestSequence(climb) {
  const response = await fetch("/api/sequence", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ holds: climb.holds }),
  });
  const payload = await response.json();
  state.sequence = payload.sequence || [];
}

function renderMeta() {
  climbName.textContent = state.currentClimb?.name || "Untitled";
  climbMeta.textContent = `${state.currentClimb?.grade || "Unknown"} · ${state.currentClimb?.angle || "Unknown"} degrees`;
  holdCounts.innerHTML = HOLD_TYPES.map((holdType) => {
    const count = state.currentClimb?.holds?.[holdType]?.length || 0;
    return `<div class="countLine" style="border-color:${HOLD_COLORS[holdType]}">${holdType}: ${count}</div>`;
  }).join("");
}

async function selectClimb(value) {
  statusText.textContent = "Loading climb coordinates.";
  state.betaVisible = false;
  state.sequence = [];
  animCtx.clearRect(0, 0, animationCanvas.width, animationCanvas.height);
  const [kind, id] = value.split(":");
  if (kind === "source") {
    const source = state.sourceClimbs.find((item) => item.id === id);
    const scanned = await scanSourceClimb(source);
    state.currentClimb = normalizeClimb(scanned);
    state.baseImage = scanned.baseImage;
  } else {
    state.currentClimb = normalizeClimb(state.savedClimbs[Number(id)]);
    state.baseImage = state.templateImage;
  }
  renderMeta();
  drawBoard();
  statusText.textContent = "Climb loaded. Use Generate beta to animate.";
}

function populateSelect() {
  const sourceOptions = state.sourceClimbs.map(
    (climb) => `<option value="source:${climb.id}">${climb.name}</option>`,
  );
  const savedOptions = state.savedClimbs.map(
    (climb, index) => `<option value="saved:${index}">Saved: ${climb.name}</option>`,
  );
  climbSelect.innerHTML = [...sourceOptions, ...savedOptions].join("");
}

function toggleSetMode() {
  state.mode = state.mode === "set" ? "view" : "set";
  setterPanel.hidden = state.mode !== "set";
  setModeButton.textContent = state.mode === "set" ? "View Climbs" : "Set a Climb";
  if (state.mode === "set") {
    state.currentClimb = { name: newName.value, grade: newGrade.value, angle: newAngle.value, holds: emptyHolds() };
    state.sequence = [];
    state.betaVisible = false;
    state.baseImage = state.templateImage;
    animCtx.clearRect(0, 0, animationCanvas.width, animationCanvas.height);
    renderMeta();
    drawBoard();
    statusText.textContent = "Pick a hold type, then click the board.";
  }
}

function addOrRemoveHold(point) {
  const holds = state.currentClimb.holds[state.selectedHoldType];
  const existingIndex = holds.findIndex(([x, y]) => x === point.x && y === point.y);
  if (existingIndex >= 0) {
    holds.splice(existingIndex, 1);
  } else {
    if (state.selectedHoldType === "Start" && holds.length >= 2) {
      statusText.textContent = "A climb can have at most two start holds.";
      return;
    }
    if (state.selectedHoldType === "Finish" && holds.length >= 2) {
      statusText.textContent = "A climb can have at most two finish holds.";
      return;
    }
    holds.push([point.x, point.y]);
  }
  renderMeta();
  drawBoard();
}

async function saveCurrentClimb() {
  const payload = {
    name: newName.value,
    grade: newGrade.value,
    angle: newAngle.value,
    holds: state.currentClimb.holds,
  };
  const response = await fetch("/api/climbs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok) {
    statusText.textContent = result.error || "Could not save climb.";
    return;
  }
  state.currentClimb = normalizeClimb(result.climb);
  state.sequence = result.sequence || [];
  state.betaVisible = false;
  state.baseImage = state.templateImage;
  await refreshClimbs();
  statusText.textContent = "Climb saved and displayed from coordinates.";
  renderMeta();
  drawBoard();
}

async function generateBeta() {
  if (!state.currentClimb) return;
  statusText.textContent = "Generating beta animation.";
  await requestSequence(state.currentClimb);
  state.betaVisible = true;
  state.animationStart = performance.now();
  statusText.textContent = "Generated beta is looping on the climb.";
}

async function refreshClimbs() {
  const response = await fetch("/api/climbs");
  const payload = await response.json();
  state.sourceClimbs = payload.sourceClimbs || [];
  state.savedClimbs = payload.savedClimbs || [];
  populateSelect();
}

boardCanvas.addEventListener("click", (event) => {
  if (state.mode !== "set") return;
  const rect = boardCanvas.getBoundingClientRect();
  const point = pointToHold(
    ((event.clientX - rect.left) / rect.width) * boardCanvas.width,
    ((event.clientY - rect.top) / rect.height) * boardCanvas.height,
  );
  if (point) addOrRemoveHold(point);
});

viewMode.addEventListener("change", async () => {
  state.view = viewMode.value;
  drawBoard();
});

climbSelect.addEventListener("change", () => selectClimb(climbSelect.value));
setModeButton.addEventListener("click", toggleSetMode);
generateBetaButton.addEventListener("click", generateBeta);
document.querySelector("#clearButton").addEventListener("click", () => {
  state.currentClimb.holds = emptyHolds();
  renderMeta();
  drawBoard();
});
document.querySelector("#saveButton").addEventListener("click", saveCurrentClimb);
document.querySelectorAll("[data-hold-type]").forEach((button) => {
  button.addEventListener("click", () => {
    state.selectedHoldType = button.dataset.holdType;
    document.querySelectorAll("[data-hold-type]").forEach((item) => item.classList.remove("selected"));
    button.classList.add("selected");
  });
});

function tick(time) {
  drawMonkeyFrame(time);
  requestAnimationFrame(tick);
}

async function init() {
  state.templateImage = await loadImage("/kilter_climbs_output/output_template.png");
  state.baseImage = state.templateImage;
  await refreshClimbs();
  if (climbSelect.value) await selectClimb(climbSelect.value);
  requestAnimationFrame(tick);
}

init().catch((error) => {
  statusText.textContent = `Failed to start: ${error.message}`;
});
