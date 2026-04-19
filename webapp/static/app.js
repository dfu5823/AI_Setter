const HOLD_TYPES = ["Start", "Any", "Finish", "Feet"];
const HOLD_COLORS = {
  Start: "#62d852",
  Any: "#53e6e6",
  Finish: "#bd45ff",
  Feet: "#f3a21b",
};
const GRID = { cols: 35, rows: 39 };
const BOARD_CROP = { x: 0, y: 300, w: 750, h: 925 };
const BOARD_SIZE_INCHES = { width: 144, height: 144 };
const HOLD_SPACING_INCHES = {
  x: BOARD_SIZE_INCHES.width / (GRID.cols - 1),
  y: BOARD_SIZE_INCHES.height / (GRID.rows - 1),
};

const state = {
  sourceClimbs: [],
  savedClimbs: [],
  visibleClimbs: [],
  sourceTotal: 0,
  currentClimb: null,
  currentSource: "kilter",
  page: "browse",
  view: "2d",
  selectedHoldType: "Start",
  scanCache: new Map(),
  sequence: [],
  footSequence: [],
  sequenceMetrics: null,
  animationStart: performance.now(),
  betaVisible: false,
  betaSpeed: 0.7,
  lastPose: null,
  lastPoseTime: 0,
  animationCycle: -1,
  baseImage: null,
  templateImage: null,
  overlayHolds: true,
  validHolds: new Set(),
  holdCenters: new Map(),
  betaMode: "handFoot",
  appliedFilters: { angle: "40", minGrade: 0, maxGrade: 16, source: "all", sort: "ascentsDesc" },
  searchName: "",
  randomGradePick: false,
};

const boardCanvas = document.querySelector("#boardCanvas");
const animationCanvas = document.querySelector("#animationCanvas");
const sampleCanvas = document.querySelector("#sampleCanvas");
const ctx = boardCanvas.getContext("2d");
const animCtx = animationCanvas.getContext("2d");
const sampleCtx = sampleCanvas.getContext("2d", { willReadFrequently: true });

const climbSelect = document.querySelector("#climbSelect");
const sortSelect = document.querySelector("#sortSelect");
const sourceFilter = document.querySelector("#sourceFilter");
const angleFilter = document.querySelector("#angleFilter");
const gradeMinRange = document.querySelector("#gradeMinRange");
const gradeMaxRange = document.querySelector("#gradeMaxRange");
const gradeRangeLabel = document.querySelector("#gradeRangeLabel");
const searchClimbsButton = document.querySelector("#searchClimbsButton");
const availableClimbCount = document.querySelector("#availableClimbCount");
const climbResults = document.querySelector("#climbResults");
const viewModes = document.querySelectorAll(".viewMode");
const generateBetaButton = document.querySelector("#generateBetaButton");
const setGenerateBetaButton = document.querySelector("#setGenerateBetaButton");
const restartBetaButton = document.querySelector("#restartBetaButton");
const speedInput = document.querySelector("#speedInput");
const unitSelect = document.querySelector("#unitSelect");
const heightInput = document.querySelector("#heightInput");
const apeInput = document.querySelector("#apeInput");
const betaBuddyUpload = document.querySelector("#betaBuddyUpload");
const betaModeSelect = document.querySelector("#betaModeSelect");
const generateOutputsButton = document.querySelector("#generateOutputsButton");
const generatorGrade = document.querySelector("#generatorGrade");
const generatorAngle = document.querySelector("#generatorAngle");
const generatorSeed = document.querySelector("#generatorSeed");
const generatorHandCount = document.querySelector("#generatorHandCount");
const generatorFootCount = document.querySelector("#generatorFootCount");
const handUsagePreference = document.querySelector("#handUsagePreference");
const footUsagePreference = document.querySelector("#footUsagePreference");
const statusText = document.querySelector("#statusText");
const climbName = document.querySelector("#climbName");
const climbMeta = document.querySelector("#climbMeta");
const climbDetails = document.querySelector("#climbDetails");
const holdCounts = document.querySelector("#holdCounts");
const sequenceDetails = document.querySelector("#sequenceDetails");
const newName = document.querySelector("#newName");
const newGrade = document.querySelector("#newGrade");
const newAngle = document.querySelector("#newAngle");
const pageTitle = document.querySelector("#pageTitle");

function emptyHolds() {
  return { Start: [], Any: [], Finish: [], Feet: [] };
}

function sourcePointFromHold(hold) {
  const calibrated = state.holdCenters.get(`${hold.x}:${hold.y}`);
  if (calibrated) return calibrated;
  return rawSourcePointFromHold(hold);
}

function rawSourcePointFromHold(hold) {
  return { x: 20.8 * hold.x + 0.7, y: 1153.3 - 20.8 * hold.y };
}

function rawHoldFromSourcePoint(point) {
  return {
    x: Math.round((point.x - 0.7) / 20.8),
    y: Math.round((1153.3 - point.y) / 20.8),
  };
}

function nearestPhysicalHoldFromSourcePoint(point, maxDistance = 28) {
  let best = null;
  let bestD = Infinity;
  for (const [key, center] of state.holdCenters) {
    const d = Math.hypot(center.x - point.x, center.y - point.y);
    if (d < bestD) {
      const [x, y] = key.split(":").map(Number);
      best = { x, y };
      bestD = d;
    }
  }
  return best && bestD <= maxDistance ? best : null;
}

function holdToPoint(hold) {
  const source = sourcePointFromHold(hold);
  const x = source.x - BOARD_CROP.x;
  const y = source.y - BOARD_CROP.y;
  if (state.view === "3d") {
    return projectHold3d(hold);
  }
  return { x, y, z: 0 };
}

function projectHold3d(hold) {
  const boardWidth = 12;
  const boardHeight = 12;
  const angle = Number.parseFloat(state.currentClimb?.angle || "50") || 50;
  const theta = (angle * Math.PI) / 180;
  const xFeet = ((hold.x - 1) / (GRID.cols - 1) - 0.5) * boardWidth;
  const yFeet = ((hold.y - 1) / (GRID.rows - 1)) * boardHeight;
  const world = { x: xFeet, y: Math.cos(theta) * yFeet, z: Math.sin(theta) * yFeet };
  const camera = { x: -15, y: 6, z: -15 };
  const target = { x: 0, y: Math.cos(theta) * boardHeight * 0.5, z: Math.sin(theta) * boardHeight * 0.5 };
  const forward = normalize({ x: target.x - camera.x, y: target.y - camera.y, z: target.z - camera.z });
  const right = normalize(cross(forward, { x: 0, y: 1, z: 0 }));
  const up = cross(right, forward);
  const rel = { x: world.x - camera.x, y: world.y - camera.y, z: world.z - camera.z };
  const cx = dot(rel, right);
  const cy = dot(rel, up);
  const cz = Math.max(0.2, dot(rel, forward));
  const focal = 980;
  return { x: boardCanvas.width / 2 + (cx / cz) * focal, y: boardCanvas.height / 2 - (cy / cz) * focal, z: cz };
}

function dot(a, b) {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

function cross(a, b) {
  return { x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x };
}

function normalize(v) {
  const len = Math.hypot(v.x, v.y, v.z) || 1;
  return { x: v.x / len, y: v.y / len, z: v.z / len };
}

function pointToHold(px, py) {
  let best = { x: 1, y: 1, d: Infinity };
  for (const key of state.validHolds) {
    const [x, y] = key.split(":").map(Number);
    const point = holdToPoint({ x, y });
    const d = Math.hypot(px - point.x, py - point.y);
    if (d < best.d) best = { x, y, d };
  }
  return best.d < 22 ? { x: best.x, y: best.y } : null;
}

function classifyPixel(r, g, b) {
  if (g > 190 && r < 150 && b < 150) return "Start";
  if (b > 145 && g > 185 && r < 150) return "Any";
  if (r > 170 && b > 145 && g < 150) return "Finish";
  if (r > 170 && g > 130 && b < 130) return "Feet";
  return null;
}

function isYellowStar(r, g, b) {
  return r > 185 && g > 145 && b < 80;
}

function isPhysicalHoldPixel(r, g, b) {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  return max > 65 && max < 210 && max - min < 55;
}

async function scanSourceClimb(climb) {
  if (state.scanCache.has(climb.id)) return state.scanCache.get(climb.id);
  if (climb.holds && Object.values(climb.holds).some((points) => points?.length)) {
    const scanned = { ...climb, stars: climb.stars ?? "Unknown", baseImage: state.templateImage };
    state.scanCache.set(climb.id, scanned);
    return scanned;
  }
  const image = await loadImage(climb.sourceImage);
  sampleCtx.clearRect(0, 0, sampleCanvas.width, sampleCanvas.height);
  sampleCtx.drawImage(image, 0, 0, sampleCanvas.width, sampleCanvas.height);
  const holds = detectColoredHoldComponents();
  const stars = climb.stars === undefined ? detectStars() : climb.stars;
  const scanned = { ...climb, holds, stars, baseImage: image };
  state.scanCache.set(climb.id, scanned);
  return scanned;
}

function detectStars() {
  const data = sampleCtx.getImageData(250, 190, 260, 70).data;
  const width = 260;
  const labels = new Uint8Array(width * 70);
  for (let i = 0; i < labels.length; i += 1) {
    const j = i * 4;
    if (isYellowStar(data[j], data[j + 1], data[j + 2])) labels[i] = 1;
  }
  return countComponents(labels, width, 70, 20, 60);
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
      const component = floodComponent(start, labels, visited, width, height, label, queue);
      if (component.count < 24 || component.width > 70 || component.height > 70) continue;
      const center = { x: component.sumX / component.count, y: component.sumY / component.count };
      const snapped = nearestPhysicalHoldFromSourcePoint(center) || rawHoldFromSourcePoint(center);
      const { x: hx, y: hy } = snapped;
      if (hx < 1 || hx > GRID.cols || hy < 1 || hy > GRID.rows || !state.validHolds.has(`${hx}:${hy}`)) continue;
      const holdType = indexType[label];
      const key = `${holdType}:${hx}:${hy}`;
      if (seenHolds.has(key)) continue;
      seenHolds.add(key);
      holds[holdType].push([hx, hy]);
    }
  }
  return holds;
}

function detectValidHoldsFromTemplate() {
  sampleCtx.clearRect(0, 0, sampleCanvas.width, sampleCanvas.height);
  sampleCtx.drawImage(state.templateImage, 0, 0, sampleCanvas.width, sampleCanvas.height);
  const width = sampleCanvas.width;
  const height = sampleCanvas.height;
  const data = sampleCtx.getImageData(0, 0, width, height).data;
  const labels = new Uint8Array(width * height);
  for (let y = 300; y < 1160; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const i = (y * width + x) * 4;
      if (isPhysicalHoldPixel(data[i], data[i + 1], data[i + 2])) labels[y * width + x] = 1;
    }
  }
  const visited = new Uint8Array(width * height);
  const queue = [];
  const holds = new Set();
  const centers = new Map();
  for (let y = 300; y < 1160; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const start = y * width + x;
      if (!labels[start] || visited[start]) continue;
      const component = floodComponent(start, labels, visited, width, height, 1, queue);
      if (component.count < 30 || component.width > 90 || component.height > 80) continue;
      const center = { x: component.sumX / component.count, y: component.sumY / component.count };
      const { x: hx, y: hy } = rawHoldFromSourcePoint(center);
      if (hx >= 1 && hx <= GRID.cols && hy >= 1 && hy <= GRID.rows) {
        const key = `${hx}:${hy}`;
        holds.add(key);
        centers.set(key, center);
      }
    }
  }
  state.validHolds = holds;
  state.holdCenters = centers;
}

function floodComponent(start, labels, visited, width, height, label, queue) {
  let minX = start % width;
  let maxX = minX;
  let minY = Math.floor(start / width);
  let maxY = minY;
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
    const neighbors = [current - 1, current + 1, current - width, current + width];
    for (const neighbor of neighbors) {
      if (neighbor < 0 || neighbor >= labels.length || visited[neighbor] || labels[neighbor] !== label) continue;
      visited[neighbor] = 1;
      queue.push(neighbor);
    }
  }
  return { count, sumX, sumY, width: maxX - minX + 1, height: maxY - minY + 1 };
}

function countComponents(labels, width, height, minCount, maxCount) {
  const visited = new Uint8Array(labels.length);
  const queue = [];
  let count = 0;
  for (let index = 0; index < labels.length; index += 1) {
    if (!labels[index] || visited[index]) continue;
    const component = floodComponent(index, labels, visited, width, height, 1, queue);
    if (component.count >= minCount && component.count <= maxCount) count += 1;
  }
  return Math.min(count, 5);
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
    id: raw.id || raw.name || "untitled",
    name: raw.name || raw.Name || raw.id || "Untitled",
    grade: raw.grade || raw.Grade || "Unknown",
    angle: raw.angle || raw.Angle || "Unknown",
    stars: raw.stars ?? "Unknown",
    source: raw.source || state.currentSource,
    matching_allowed: raw.matching_allowed ?? raw.matchingAllowed ?? true,
    ascensionist_count: raw.ascensionist_count ?? raw.ascents ?? 0,
    holds,
  };
}

function drawBoard() {
  ctx.clearRect(0, 0, boardCanvas.width, boardCanvas.height);
  ctx.fillStyle = "#050505";
  ctx.fillRect(0, 0, boardCanvas.width, boardCanvas.height);
  drawWall();
  if (state.currentClimb && state.overlayHolds) drawClimbHolds(state.currentClimb.holds);
}

function drawWall() {
  ctx.save();
  const image = state.baseImage || state.templateImage;
  if (state.view === "3d") {
    ctx.fillStyle = "#050505";
    ctx.fillRect(0, 0, boardCanvas.width, boardCanvas.height);
    ctx.beginPath();
    ctx.moveTo(12, boardCanvas.height - 12);
    ctx.lineTo(boardCanvas.width - 12, boardCanvas.height - 12);
    ctx.lineTo(boardCanvas.width - 96, 18);
    ctx.lineTo(-84, 18);
    ctx.closePath();
    ctx.clip();
    if (image) {
      ctx.setTransform(0.96, -0.08, 0.12, 0.96, -58, 92);
      drawBoardCrop(image);
      ctx.setTransform(1, 0, 0, 1, 0, 0);
    }
    ctx.strokeStyle = "#555";
    ctx.lineWidth = 2;
    ctx.stroke();
  } else if (image) {
    drawBoardCrop(image);
  }
  ctx.restore();
}

function drawBoardCrop(image) {
  ctx.drawImage(
    image,
    BOARD_CROP.x,
    BOARD_CROP.y,
    BOARD_CROP.w,
    BOARD_CROP.h,
    0,
    0,
    boardCanvas.width,
    boardCanvas.height,
  );
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
  if (state.sequence?.length) {
    ctx.font = "bold 13px Arial";
    ctx.textBaseline = "middle";
    const labelOffsets = new Map();
    for (const move of state.sequence) {
      const p = holdToPoint(move);
      const key = `${move.x}:${move.y}`;
      const offsetIndex = labelOffsets.get(key) || 0;
      labelOffsets.set(key, offsetIndex + 1);
      const label = move.label || `${move.move ?? ""}${move.hand === "left" ? "L" : "R"}`;
      ctx.lineWidth = 3;
      ctx.strokeStyle = move.hand === "left" ? "#111" : "#fff";
      ctx.fillStyle = move.hand === "left" ? "#fff" : "#111";
      ctx.strokeText(label, p.x + 18, p.y - 16 + offsetIndex * 15);
      ctx.fillText(label, p.x + 18, p.y - 16 + offsetIndex * 15);
    }
  }
  ctx.restore();
}

function drawMonkeyFrame(time) {
  animCtx.clearRect(0, 0, animationCanvas.width, animationCanvas.height);
  if (!state.betaVisible || !state.currentClimb || state.sequence.length === 0) return;
  const climbDuration = 8.2;
  const finishHoldDuration = 1.0;
  const dropDuration = 1.4;
  const cycleDuration = climbDuration + finishHoldDuration + dropDuration;
  const rawElapsed = ((time - state.animationStart) / 1000) * state.betaSpeed;
  const cycle = Math.floor(rawElapsed / cycleDuration);
  if (cycle !== state.animationCycle) {
    state.animationCycle = cycle;
    state.lastPose = null;
    state.lastPoseTime = 0;
  }
  const elapsed = rawElapsed % cycleDuration;
  const dropPhase = elapsed > climbDuration + finishHoldDuration;
  const progress = Math.min(elapsed / climbDuration, 1);
  let pose = climberPose(progress, dropPhase ? (elapsed - climbDuration - finishHoldDuration) / dropDuration : 0);
  pose = clampPoseMotion(pose, time);
  drawForceVector(pose);
  drawMonkey(pose);
}

function clampPoseMotion(pose, time) {
  if (!state.lastPose || time < state.lastPoseTime) {
    state.lastPose = pose;
    state.lastPoseTime = time;
    return pose;
  }
  const dt = Math.max(1 / 120, (time - state.lastPoseTime) / 1000);
  const maxStep = 260 * dt;
  const clamped = { ...pose };
  for (const key of ["leftHand", "rightHand", "leftFoot", "rightFoot", "hip", "shoulder", "torso", "head"]) {
    clamped[key] = clampStep(state.lastPose[key], pose[key], maxStep);
  }
  rebuildPoseKinematics(clamped);
  state.lastPose = clamped;
  state.lastPoseTime = time;
  return clamped;
}

function clampStep(previous, target, maxStep) {
  const dx = target.x - previous.x;
  const dy = target.y - previous.y;
  const d = Math.hypot(dx, dy);
  if (d <= maxStep) return target;
  return { x: previous.x + (dx / d) * maxStep, y: previous.y + (dy / d) * maxStep };
}

function climberPose(progress, dropProgress) {
  const posePath = handPosePath(progress);
  const active = posePath.active;
  const scale = climberScale();
  const dims = climberDimensions(scale);
  const handMid = { x: (active.leftHand.x + active.rightHand.x) / 2, y: (active.leftHand.y + active.rightHand.y) / 2 };
  const nextMid = posePath.nextMid || handMid;
  const moveVector = normalize2({ x: nextMid.x - handMid.x, y: nextMid.y - handMid.y });
  let hip = {
    x: handMid.x - moveVector.x * dims.height * 0.05,
    y: handMid.y + dims.height * 0.34,
  };
  const feet = betaFeet(hip, handMid, posePath.index, posePath.nextIndex, posePath.local, dims);
  const contactFeet = feet.filter((foot) => foot.contact);
  if (contactFeet.length) {
    const footMid = averagePoint(contactFeet);
    hip = {
      x: handMid.x * 0.64 + footMid.x * 0.36 - moveVector.x * dims.height * 0.04,
      y: Math.min(handMid.y + dims.height * 0.39, footMid.y - dims.height * 0.16),
    };
  }
  if (dropProgress > 0) hip.y += 0.9 * scale.heightPx * easeIn(dropProgress);
  let finalFeet = betaFeet(hip, handMid, posePath.index, posePath.nextIndex, posePath.local, dims);
  const pushPhase = Math.sin(easeInOut(posePath.local) * Math.PI);
  const torso = { x: hip.x, y: hip.y - dims.torso / 2 };
  const shoulder = { x: torso.x, y: torso.y - dims.torso / 2 };
  let leftHand = active.leftHand;
  let rightHand = active.rightHand;
  if (dropProgress > 0) {
    const release = easeInOut(dropProgress);
    leftHand = lerpPoint(leftHand, { x: shoulder.x - dims.shoulderWidth * 0.68, y: shoulder.y + dims.upperArm * 0.42 }, release);
    rightHand = lerpPoint(rightHand, { x: shoulder.x + dims.shoulderWidth * 0.68, y: shoulder.y + dims.upperArm * 0.42 }, release);
    finalFeet = [
      { point: lerpPoint(finalFeet[0].point, freeFootPoint(hip, -1, dims), release), contact: false },
      { point: lerpPoint(finalFeet[1].point, freeFootPoint(hip, 1, dims), release), contact: false },
    ];
  }
  const crossed = leftHand.x > rightHand.x;
  const twist = crossed ? Math.min(1, (leftHand.x - rightHand.x) / Math.max(1, posePath.handSpanPx)) : 0;
  const leftShoulder = { x: shoulder.x - dims.shoulderWidth / 2, y: shoulder.y };
  const rightShoulder = { x: shoulder.x + dims.shoulderWidth / 2, y: shoulder.y };
  const leftHip = { x: hip.x - dims.hipWidth / 2, y: hip.y };
  const rightHip = { x: hip.x + dims.hipWidth / 2, y: hip.y };
  const leftArm = twoBoneLimb(leftShoulder, leftHand, dims.upperArm, dims.forearm, -1, -0.18);
  const rightArm = twoBoneLimb(rightShoulder, rightHand, dims.upperArm, dims.forearm, 1, -0.18);
  const leftLeg = twoBoneLimb(leftHip, finalFeet[0].point, dims.thigh, dims.shin, 1, finalFeet[0].contact ? 0.26 - 0.22 * pushPhase : 0.02);
  const rightLeg = twoBoneLimb(rightHip, finalFeet[1].point, dims.thigh, dims.shin, -1, finalFeet[1].contact ? 0.26 - 0.22 * pushPhase : 0.02);
  const head = { x: shoulder.x, y: shoulder.y - dims.neck - dims.headRadius };
  const centerOfMass = computeCenterOfMass({ head, torso, hip, leftArm, rightArm, leftLeg, rightLeg });
  const contacts = contactForces(centerOfMass, [
    { name: "leftHand", point: leftHand, type: "hand", active: true },
    { name: "rightHand", point: rightHand, type: "hand", active: true },
    { name: "leftFoot", point: finalFeet[0].point, type: "foot", active: finalFeet[0].contact },
    { name: "rightFoot", point: finalFeet[1].point, type: "foot", active: finalFeet[1].contact },
  ], dims, moveVector);
  return {
    head,
    shoulder,
    leftShoulder,
    rightShoulder,
    torso,
    hip,
    leftHip,
    rightHip,
    leftHand,
    rightHand,
    leftFoot: finalFeet[0].point,
    rightFoot: finalFeet[1].point,
    leftArm,
    rightArm,
    leftLeg,
    rightLeg,
    centerOfMass,
    contacts,
    force: { x: (rightHand.x + leftHand.x) / 2 - hip.x, y: -0.16 * scale.heightPx },
    stroke: dims.stroke,
    headRadius: dims.headRadius,
    shoulderWidth: dims.shoulderWidth,
    hipWidth: dims.hipWidth,
    dims,
    pushPhase,
    crossed,
    twist,
  };
}

function climberDimensions(scale) {
  const height = scale.heightPx;
  const armReach = Math.min(scale.armSpanPx * 0.34, height * 0.47);
  return {
    height,
    headRadius: Math.max(13, height * 0.052),
    neck: height * 0.025,
    torso: height * 0.255,
    shoulderWidth: Math.max(34, height * 0.17),
    hipWidth: Math.max(26, height * 0.12),
    upperArm: armReach * 0.51,
    forearm: armReach * 0.49,
    thigh: height * 0.23,
    shin: height * 0.23,
    stroke: Math.max(8, height * 0.032),
  };
}

function handPosePath(progress) {
  const sequence = state.sequence || [];
  const count = Math.max(1, sequence.length - 1);
  const index = Math.min(sequence.length - 1, Math.floor(progress * count));
  const nextIndex = Math.min(sequence.length - 1, index + 1);
  const local = sequence.length <= 1 ? 0 : (progress * count) % 1;
  const current = sequence[index] || sequence[0];
  const next = sequence[nextIndex] || current;
  const currentLeft = pointFromPair(current?.left) || holdToPoint(current || { x: 18, y: 10 });
  const currentRight = pointFromPair(current?.right) || currentLeft;
  const nextLeft = pointFromPair(next?.left) || currentLeft;
  const nextRight = pointFromPair(next?.right) || currentRight;
  const leftHand = lerpPoint(currentLeft, nextLeft, local);
  const rightHand = lerpPoint(currentRight, nextRight, local);
  const nextMid = { x: (nextLeft.x + nextRight.x) / 2, y: (nextLeft.y + nextRight.y) / 2 };
  return {
    active: { leftHand, rightHand },
    index,
    nextIndex,
    move: Number(current?.move ?? index),
    nextMove: Number(next?.move ?? nextIndex),
    local,
    handSpanPx: Math.hypot(leftHand.x - rightHand.x, leftHand.y - rightHand.y),
    nextMid,
  };
}

function pointFromPair(pair) {
  if (!pair) return null;
  return holdToPoint({ x: pair[0], y: pair[1] });
}

function climberScale() {
  const heightInches = parseHeightInches(heightInput.value, unitSelect.value);
  const apeInches = parseSignedLengthInches(apeInput.value, unitSelect.value);
  const pxPerInch = (sourcePointFromHold({ x: 1, y: 1 }).y - sourcePointFromHold({ x: 1, y: GRID.rows }).y) / BOARD_SIZE_INCHES.height;
  return { heightPx: heightInches * pxPerInch, armSpanPx: (heightInches + apeInches) * pxPerInch };
}

function parseHeightInches(value, units) {
  if (units === "metric") return (Number.parseFloat(value) || 168) / 2.54;
  const feetMatch = String(value).match(/(\d+)\s*'\s*(\d+(?:\.\d+)?)?/);
  if (feetMatch) return Number(feetMatch[1]) * 12 + Number(feetMatch[2] || 0);
  return Number.parseFloat(value) || 66;
}

function parseSignedLengthInches(value, units) {
  const numeric = Number.parseFloat(String(value).replace(/[^0-9+.-]/g, ""));
  if (!Number.isFinite(numeric)) return 0;
  return units === "metric" ? numeric / 2.54 : numeric;
}

function betaFeet(hip, handMid, index, nextIndex, local, dims) {
  if (state.betaMode === "handFoot" && state.footSequence?.length && state.sequence?.length) {
    const currentMove = Number(state.sequence[Math.min(index, state.sequence.length - 1)]?.move ?? index);
    const nextMove = Number(state.sequence[Math.min(nextIndex, state.sequence.length - 1)]?.move ?? nextIndex);
    const current = footStateForMove(currentMove);
    const next = footStateForMove(nextMove) || current;
    const left = current?.left ? holdToPoint({ x: current.left[0], y: current.left[1] }) : null;
    const right = current?.right ? holdToPoint({ x: current.right[0], y: current.right[1] }) : null;
    const nextLeft = next?.left ? holdToPoint({ x: next.left[0], y: next.left[1] }) : null;
    const nextRight = next?.right ? holdToPoint({ x: next.right[0], y: next.right[1] }) : null;
    const leftFree = freeFootPoint(hip, -1, dims);
    const rightFree = freeFootPoint(hip, 1, dims);
    const leftTarget = left || nextLeft ? lerpPoint(left || leftFree, nextLeft || leftFree, easeInOut(local)) : null;
    const rightTarget = right || nextRight ? lerpPoint(right || rightFree, nextRight || rightFree, easeInOut(local)) : null;
    return resolveFootPairIntersections(
      constrainFootTarget(leftTarget, hip, handMid, -1, dims, { strictWallPosition: false, maxLegRatio: 1.35 }),
      constrainFootTarget(rightTarget, hip, handMid, 1, dims, { strictWallPosition: false, maxLegRatio: 1.35 }),
      hip,
      dims,
    );
  }
  const footHolds = [...(state.currentClimb.holds.Feet || []), ...(state.currentClimb.holds.Any || [])]
    .map(([x, y]) => holdToPoint({ x, y }))
    .filter((point) => point.y > handMid.y + dims.height * 0.1 && point.y < handMid.y + dims.height * 0.58)
    .sort((a, b) => footTargetScore(a, hip, -1, dims) - footTargetScore(b, hip, -1, dims));
  const rightFootHolds = [...footHolds].sort((a, b) => footTargetScore(a, hip, 1, dims) - footTargetScore(b, hip, 1, dims));
  return resolveFootPairIntersections(
    constrainFootTarget(footHolds[0], hip, handMid, -1, dims),
    constrainFootTarget(rightFootHolds[0], hip, handMid, 1, dims),
    hip,
    dims,
  );
}

function footStateForMove(moveNumber) {
  return (state.footSequence || []).find((step) => Number(step.move) === Number(moveNumber)) || null;
}

function freeFootPoint(hip, side, dims) {
  const rootX = hip.x + side * dims.hipWidth / 2;
  return {
    x: rootX,
    y: hip.y + (dims.thigh + dims.shin) * 0.88,
  };
}

function constrainFootTarget(target, hip, handMid, side, dims, options = {}) {
  const free = { point: freeFootPoint(hip, side, dims), contact: false };
  if (!target) return free;
  const maxLeg = dims.thigh + dims.shin;
  const maxLegRatio = Number(options.maxLegRatio || 0.98);
  const strictWallPosition = options.strictWallPosition !== false;
  const staleLow = strictWallPosition && target.y > handMid.y + dims.height * 0.6;
  const tooHigh = strictWallPosition && target.y < handMid.y + dims.height * 0.08;
  const tooFar = Math.hypot(target.x - hip.x, target.y - hip.y) > maxLeg * maxLegRatio;
  const crossedLeg = strictWallPosition && side * (target.x - hip.x) < -dims.hipWidth * 0.35;
  if (staleLow || tooHigh || tooFar || crossedLeg) return free;
  return { point: target, contact: true };
}

function footTargetScore(point, hip, side, dims) {
  const rootX = hip.x + side * dims.hipWidth / 2;
  const distance = Math.hypot(point.x - rootX, point.y - hip.y);
  const crossed = side * (point.x - hip.x) < 0 ? dims.height * 0.45 : 0;
  const straightDownBias = Math.abs(point.x - rootX) * 0.35;
  return distance + crossed + straightDownBias;
}

function resolveFootPairIntersections(leftFoot, rightFoot, hip, dims) {
  const leftHip = { x: hip.x - dims.hipWidth / 2, y: hip.y };
  const rightHip = { x: hip.x + dims.hipWidth / 2, y: hip.y };
  const leftLeg = twoBoneLimb(leftHip, leftFoot.point, dims.thigh, dims.shin, 1, leftFoot.contact ? 0.22 : 0.02);
  const rightLeg = twoBoneLimb(rightHip, rightFoot.point, dims.thigh, dims.shin, -1, rightFoot.contact ? 0.22 : 0.02);
  const intersections = countLegIntersections(leftLeg, rightLeg);
  if (!intersections) return [leftFoot, rightFoot];
  const leftFree = constrainFootTarget(null, hip, { x: hip.x, y: hip.y - dims.height * 0.2 }, -1, dims);
  const rightFree = constrainFootTarget(null, hip, { x: hip.x, y: hip.y - dims.height * 0.2 }, 1, dims);
  const leftPenalty = legIntersectionPenalty(leftFoot, -1, hip, dims, intersections);
  const rightPenalty = legIntersectionPenalty(rightFoot, 1, hip, dims, intersections);
  if (intersections > 1) return [leftFree, rightFree];
  return leftPenalty >= rightPenalty ? [leftFree, rightFoot] : [leftFoot, rightFree];
}

function legIntersectionPenalty(foot, side, hip, dims, intersections) {
  const sidePenalty = side * (foot.point.x - hip.x) < 0 ? dims.height * 0.45 : 0;
  const contactPenalty = foot.contact ? dims.height * 0.25 : 0;
  return intersections * dims.height * 0.7 + (intersections > 1 ? dims.height * 0.9 : 0) + sidePenalty + contactPenalty;
}

function drawMonkey(pose) {
  animCtx.save();
  animCtx.lineCap = "round";
  animCtx.lineJoin = "round";
  animCtx.strokeStyle = "#6f5135";
  animCtx.lineWidth = pose.stroke;
  drawLimb(pose.leftArm, pose.stroke);
  drawLimb(pose.rightArm, pose.stroke);
  drawLimb(pose.leftLeg, pose.stroke * 1.18);
  drawLimb(pose.rightLeg, pose.stroke * 1.18);
  drawShoe(pose.leftFoot, -0.25);
  drawShoe(pose.rightFoot, 0.25);
  drawShorts(pose);
  drawShirt(pose);
  drawHead(pose);
  animCtx.restore();
}

function drawHead(pose) {
  animCtx.fillStyle = "#7c5c36";
  circle(pose.head, pose.headRadius);
  if (pose.twist > 0.12) {
    animCtx.fillStyle = "#e5d0a6";
    animCtx.beginPath();
    animCtx.ellipse(pose.head.x, pose.head.y + pose.headRadius * 0.1, pose.headRadius * (0.35 + pose.twist * 0.3), pose.headRadius * 0.58, 0, 0, Math.PI * 2);
    animCtx.fill();
    animCtx.fillStyle = "#101010";
    circle({ x: pose.head.x - pose.headRadius * 0.22, y: pose.head.y - 1 }, 2.2);
    circle({ x: pose.head.x + pose.headRadius * 0.22, y: pose.head.y - 1 }, 2.2);
  } else {
    animCtx.fillStyle = "#5f4327";
    animCtx.beginPath();
    animCtx.arc(pose.head.x, pose.head.y - pose.headRadius * 0.04, pose.headRadius * 0.72, Math.PI * 0.05, Math.PI * 0.95);
    animCtx.fill();
    animCtx.strokeStyle = "#3c2b1b";
    animCtx.lineWidth = 2;
    animCtx.beginPath();
    animCtx.arc(pose.head.x, pose.head.y, pose.headRadius * 0.55, Math.PI * 0.15, Math.PI * 0.85);
    animCtx.stroke();
  }
}

function drawShirt(pose) {
  const topY = pose.shoulder.y - pose.stroke * 0.45;
  const bottomY = pose.hip.y + pose.stroke * 0.25;
  animCtx.fillStyle = "#c92f2f";
  animCtx.strokeStyle = "#6f1717";
  animCtx.lineWidth = 2;
  animCtx.beginPath();
  animCtx.moveTo(pose.shoulder.x - pose.shoulderWidth / 2, topY);
  animCtx.lineTo(pose.shoulder.x + pose.shoulderWidth / 2, topY);
  animCtx.lineTo(pose.hip.x + pose.hipWidth / 2, bottomY);
  animCtx.lineTo(pose.hip.x - pose.hipWidth / 2, bottomY);
  animCtx.closePath();
  animCtx.fill();
  animCtx.stroke();
  if (pose.twist > 0.05) {
    const frontWidth = pose.shoulderWidth * (0.25 + pose.twist * 0.55);
    animCtx.fillStyle = "#2f8bd8";
    animCtx.beginPath();
    animCtx.ellipse(pose.torso.x, (topY + bottomY) / 2, frontWidth / 2, (bottomY - topY) * 0.42, 0, 0, Math.PI * 2);
    animCtx.fill();
    animCtx.strokeStyle = "#114466";
    animCtx.stroke();
    drawBanana({ x: pose.torso.x, y: (topY + bottomY) / 2 }, Math.max(9, pose.stroke * 1.1));
  } else {
    animCtx.fillStyle = "#ff6f6f";
    animCtx.beginPath();
    animCtx.arc(pose.shoulder.x, topY + pose.stroke * 0.1, pose.stroke * 0.8, 0, Math.PI);
    animCtx.fill();
  }
}

function drawBanana(center, size) {
  animCtx.save();
  animCtx.strokeStyle = "#ffd731";
  animCtx.lineWidth = Math.max(3, size * 0.28);
  animCtx.beginPath();
  animCtx.arc(center.x, center.y, size, 0.25 * Math.PI, 0.9 * Math.PI);
  animCtx.stroke();
  animCtx.strokeStyle = "#7c5b00";
  animCtx.lineWidth = 2;
  animCtx.beginPath();
  animCtx.arc(center.x, center.y, size, 0.27 * Math.PI, 0.9 * Math.PI);
  animCtx.stroke();
  animCtx.restore();
}

function drawShoe(point, angle) {
  animCtx.save();
  animCtx.translate(point.x, point.y);
  animCtx.rotate(angle);
  animCtx.fillStyle = "#1f6fec";
  animCtx.strokeStyle = "#9fd0ff";
  animCtx.lineWidth = 2;
  animCtx.beginPath();
  animCtx.ellipse(0, 0, 14, 7, 0, 0, Math.PI * 2);
  animCtx.fill();
  animCtx.stroke();
  animCtx.fillStyle = "#0b2d66";
  animCtx.fillRect(-10, 3, 20, 3);
  animCtx.restore();
}

function drawShorts(pose) {
  animCtx.fillStyle = "#f06f2f";
  animCtx.strokeStyle = "#7a2d12";
  animCtx.lineWidth = 2;
  animCtx.beginPath();
  animCtx.moveTo(pose.hip.x - pose.hipWidth * 0.62, pose.hip.y - pose.stroke * 0.2);
  animCtx.lineTo(pose.hip.x + pose.hipWidth * 0.62, pose.hip.y - pose.stroke * 0.2);
  animCtx.lineTo(pose.hip.x + pose.hipWidth * 0.45, pose.hip.y + pose.stroke * 1.05);
  animCtx.lineTo(pose.hip.x + pose.hipWidth * 0.05, pose.hip.y + pose.stroke * 0.5);
  animCtx.lineTo(pose.hip.x - pose.hipWidth * 0.45, pose.hip.y + pose.stroke * 1.05);
  animCtx.closePath();
  animCtx.fill();
  animCtx.stroke();
}

function drawLimb(limbPose, width) {
  animCtx.beginPath();
  animCtx.lineWidth = width;
  animCtx.moveTo(limbPose.root.x, limbPose.root.y);
  animCtx.lineTo(limbPose.joint.x, limbPose.joint.y);
  animCtx.lineTo(limbPose.end.x, limbPose.end.y);
  animCtx.stroke();
  animCtx.fillStyle = "#7b5a38";
  circle(limbPose.joint, width * 0.46);
}

function circle(p, r) {
  animCtx.beginPath();
  animCtx.arc(p.x, p.y, r, 0, Math.PI * 2);
  animCtx.fill();
}

function drawForceVector(pose) {
  animCtx.save();
  animCtx.fillStyle = "#ffd731";
  circle(pose.centerOfMass, 4);
  for (const contact of pose.contacts || []) {
    const end = {
      x: contact.point.x + contact.force.x * 0.16,
      y: contact.point.y + contact.force.y * 0.16,
    };
    animCtx.strokeStyle = contact.type === "foot" ? "#2d7dff" : "#f3a21b";
    animCtx.lineWidth = 3;
    animCtx.beginPath();
    animCtx.moveTo(contact.point.x, contact.point.y);
    animCtx.lineTo(end.x, end.y);
    animCtx.stroke();
    animCtx.beginPath();
    animCtx.arc(end.x, end.y, 3, 0, Math.PI * 2);
    animCtx.fillStyle = animCtx.strokeStyle;
    animCtx.fill();
  }
  animCtx.restore();
}

function twoBoneLimb(root, end, upper, lower, side = 1, bendBias = 0) {
  const dx = end.x - root.x;
  const dy = end.y - root.y;
  const d = Math.max(1, Math.hypot(dx, dy));
  const clampedD = Math.min(d, upper + lower - 0.001);
  const along = { x: dx / d, y: dy / d };
  const perp = { x: -along.y * side, y: along.x * side };
  const a = clamp((upper * upper - lower * lower + clampedD * clampedD) / (2 * clampedD), 0, upper);
  const h = Math.sqrt(Math.max(0, upper * upper - a * a));
  const joint = {
    x: root.x + along.x * a + perp.x * (h + bendBias * upper),
    y: root.y + along.y * a + perp.y * (h + bendBias * upper),
  };
  return { root, joint, end };
}

function countLegIntersections(leftLeg, rightLeg) {
  const leftSegments = [[leftLeg.root, leftLeg.joint], [leftLeg.joint, leftLeg.end]];
  const rightSegments = [[rightLeg.root, rightLeg.joint], [rightLeg.joint, rightLeg.end]];
  let count = 0;
  for (const left of leftSegments) {
    for (const right of rightSegments) {
      if (segmentsIntersect(left[0], left[1], right[0], right[1])) count += 1;
    }
  }
  return count;
}

function segmentsIntersect(a, b, c, d) {
  const eps = 0.001;
  if (sharedEndpoint(a, b, c, d, eps)) return false;
  const o1 = orientation(a, b, c);
  const o2 = orientation(a, b, d);
  const o3 = orientation(c, d, a);
  const o4 = orientation(c, d, b);
  return o1 * o2 < -eps && o3 * o4 < -eps;
}

function sharedEndpoint(a, b, c, d, eps) {
  return samePoint(a, c, eps) || samePoint(a, d, eps) || samePoint(b, c, eps) || samePoint(b, d, eps);
}

function samePoint(a, b, eps) {
  return Math.abs(a.x - b.x) < eps && Math.abs(a.y - b.y) < eps;
}

function orientation(a, b, c) {
  return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
}

function computeCenterOfMass(parts) {
  const weighted = [
    [parts.head, 0.08],
    [parts.torso, 0.42],
    [parts.hip, 0.14],
    [midpoint(parts.leftArm.root, parts.leftArm.end), 0.07],
    [midpoint(parts.rightArm.root, parts.rightArm.end), 0.07],
    [midpoint(parts.leftLeg.root, parts.leftLeg.end), 0.11],
    [midpoint(parts.rightLeg.root, parts.rightLeg.end), 0.11],
  ];
  const total = weighted.reduce((sum, item) => sum + item[1], 0);
  return {
    x: weighted.reduce((sum, item) => sum + item[0].x * item[1], 0) / total,
    y: weighted.reduce((sum, item) => sum + item[0].y * item[1], 0) / total,
  };
}

function contactForces(centerOfMass, contacts, dims, moveVector) {
  const active = contacts.filter((contact) => contact.active);
  const total = Math.max(1, active.length);
  return active.map((contact) => {
    const toCom = { x: centerOfMass.x - contact.point.x, y: centerOfMass.y - contact.point.y };
    const verticalShare = dims.height * (contact.type === "foot" ? 0.32 : 0.22) / total;
    const drive = contact.type === "foot" ? 0.22 : 0.13;
    return {
      ...contact,
      force: {
        x: toCom.x * 0.18 - moveVector.x * dims.height * drive,
        y: Math.abs(verticalShare) + Math.max(0, toCom.y) * 0.08,
      },
    };
  });
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

function easeInOut(t) {
  const x = clamp(t, 0, 1);
  return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function normalize2(vector) {
  const length = Math.hypot(vector.x, vector.y);
  if (!length) return { x: 0, y: -1 };
  return { x: vector.x / length, y: vector.y / length };
}

function midpoint(a, b) {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

function averagePoint(points) {
  return {
    x: points.reduce((sum, point) => sum + point.point.x, 0) / points.length,
    y: points.reduce((sum, point) => sum + point.point.y, 0) / points.length,
  };
}

function rebuildPoseKinematics(pose) {
  const dims = pose.dims;
  pose.leftShoulder = { x: pose.shoulder.x - dims.shoulderWidth / 2, y: pose.shoulder.y };
  pose.rightShoulder = { x: pose.shoulder.x + dims.shoulderWidth / 2, y: pose.shoulder.y };
  pose.leftHip = { x: pose.hip.x - dims.hipWidth / 2, y: pose.hip.y };
  pose.rightHip = { x: pose.hip.x + dims.hipWidth / 2, y: pose.hip.y };
  pose.leftArm = twoBoneLimb(pose.leftShoulder, pose.leftHand, dims.upperArm, dims.forearm, -1, -0.18);
  pose.rightArm = twoBoneLimb(pose.rightShoulder, pose.rightHand, dims.upperArm, dims.forearm, 1, -0.18);
  const pushPhase = pose.pushPhase || 0;
  pose.leftLeg = twoBoneLimb(pose.leftHip, pose.leftFoot, dims.thigh, dims.shin, 1, 0.18 - 0.16 * pushPhase);
  pose.rightLeg = twoBoneLimb(pose.rightHip, pose.rightFoot, dims.thigh, dims.shin, -1, 0.18 - 0.16 * pushPhase);
  pose.centerOfMass = computeCenterOfMass(pose);
  if (pose.contacts?.length) {
    const contactPoints = { leftHand: pose.leftHand, rightHand: pose.rightHand, leftFoot: pose.leftFoot, rightFoot: pose.rightFoot };
    pose.contacts = pose.contacts.map((contact) => {
      const point = contactPoints[contact.name] || contact.point;
      const toCom = { x: pose.centerOfMass.x - point.x, y: pose.centerOfMass.y - point.y };
      return { ...contact, point, force: { x: toCom.x * 0.18, y: Math.abs(contact.force?.y || dims.height * 0.08) } };
    });
  }
}

async function requestSequence(climb) {
  const response = await fetch("/api/sequence", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      holds: climb.holds,
      grade: climb.grade,
      matching_allowed: climb.matching_allowed ?? true,
    }),
  });
  const payload = await response.json();
  state.sequence = payload.sequence || [];
  state.footSequence = payload.foot_sequence || [];
  state.sequenceMetrics = payload.metrics || null;
  renderMeta();
  drawBoard();
}

function renderMeta() {
  climbName.textContent = state.currentClimb?.name || "Untitled";
  climbMeta.textContent = `${state.currentClimb?.grade || "Unknown"} · ${state.currentClimb?.angle || "Unknown"} degrees`;
  const stars = state.currentClimb?.stars === "Unknown" ? "Unknown" : `${state.currentClimb?.stars || 0} / 5`;
  const matchingText = state.currentClimb?.matching_allowed === false ? "No matching" : "Matching allowed";
  climbDetails.innerHTML = [
    ["Source", state.currentSource === "user" ? "User set" : "Kilter data"],
    ["Stars", stars],
    ["Matching", matchingText],
    ["Approx hold spacing", `${HOLD_SPACING_INCHES.x.toFixed(2)} in x ${HOLD_SPACING_INCHES.y.toFixed(2)} in`],
  ].map(([label, value]) => `<div class="detailLine"><span>${label}</span><strong>${value}</strong></div>`).join("");
  holdCounts.innerHTML = HOLD_TYPES.map((holdType) => {
    const count = state.currentClimb?.holds?.[holdType]?.length || 0;
    return `<div class="countLine" style="border-color:${HOLD_COLORS[holdType]}">${holdType}: ${count}</div>`;
  }).join("");
  renderSequenceDetails();
}

function renderSequenceDetails() {
  if (!sequenceDetails) return;
  const metrics = state.sequenceMetrics || state.currentClimb?.sequence_metrics || {};
  const sequence = state.sequence || state.currentClimb?.hand_sequence || [];
  const metricRows = [
    ["Crosses", metrics.crosses ?? 0],
    ["Dynos", metrics.dynos ?? 0],
    ["Bumps", metrics.bumps ?? 0],
    ["Avg move distance", Number(metrics.average_move_distance || 0).toFixed(2)],
    ["Avg interhand distance", Number(metrics.average_interhand_distance || 0).toFixed(2)],
    ["Foot moves", metrics.foot_moves ?? 0],
  ].map(([label, value]) => `<div class="detailLine"><span>${label}</span><strong>${value}</strong></div>`).join("");
  const feetToDisplay = state.betaMode === "handFoot" ? state.footSequence || [] : [];
  const rows = orderedSequenceRows(sequence, feetToDisplay).slice(0, 48).map((row) => {
    if (row.kind === "foot") {
      return `<div class="detailLine"><span>${row.label}</span><strong>${row.foot} (${row.x}, ${row.y}) penalty ${Number(row.penalty || 0).toFixed(1)}</strong></div>`;
    }
    return `<div class="detailLine"><span>${row.label}</span><strong>${row.hand} (${row.x}, ${row.y}) ${row.event || ""}</strong></div>`;
  }).join("");
  sequenceDetails.innerHTML = `<h3>Sequence</h3>${metricRows}${rows}`;
}

function orderedSequenceRows(handSequence, footSequence) {
  const hands = handSequence.map((move, index) => ({
    kind: "hand",
    order: index,
    move: Number(move.move ?? index),
    sideOrder: move.hand === "left" ? 0 : 1,
    label: move.label || `${move.move ?? ""}${move.hand === "left" ? "L" : "R"}`,
    ...move,
  }));
  const feet = footSequence.flatMap((step) => (step.foot_moves || []).map((move) => ({
    kind: "foot",
    order: 1000,
    move: Number(step.move ?? String(move.label || "").match(/^(\d+)/)?.[1] ?? 0),
    sideOrder: move.foot === "left" ? 2 : 3,
    ...move,
  })));
  return [...hands, ...feet].sort((a, b) => (
    a.move - b.move
    || a.sideOrder - b.sideOrder
    || a.order - b.order
    || String(a.label).localeCompare(String(b.label))
  ));
}

async function selectClimb(value) {
  statusText.textContent = "Loading climb coordinates.";
  state.betaVisible = false;
  state.sequence = [];
  state.footSequence = [];
  state.sequenceMetrics = null;
  animCtx.clearRect(0, 0, animationCanvas.width, animationCanvas.height);
  const separator = value.indexOf(":");
  const kind = value.slice(0, separator);
  const id = value.slice(separator + 1);
  if (kind === "source") {
    const source = state.sourceClimbs.find((item) => item.id === id);
    const scanned = await scanSourceClimb(source);
    state.currentSource = scanned.source === "kilter_db" ? "kilter_db" : "kilter";
    state.currentClimb = normalizeClimb({ ...scanned, source: state.currentSource });
    state.baseImage = scanned.baseImage || state.templateImage;
    state.overlayHolds = true;
  } else {
    const saved = state.savedClimbs.find((item) => item.id === id) || state.savedClimbs[Number(id)];
    state.currentSource = "user";
    state.currentClimb = normalizeClimb({ ...saved, source: "user" });
    state.baseImage = state.templateImage;
    state.overlayHolds = true;
  }
  renderMeta();
  drawBoard();
  statusText.textContent = "Climb loaded. Use Generate beta to animate.";
}

function populateSelect() {
  const all = [
    ...state.sourceClimbs.map((climb) => ({ ...climb, source: climb.source === "kilter_db" ? "kilter" : (climb.source || "kilter"), value: `source:${climb.id}` })),
    ...state.savedClimbs.map((climb, index) => ({ ...climb, id: climb.id || String(index), source: "user", value: `saved:${climb.id || index}` })),
  ];
  const filters = state.appliedFilters;
  const filtered = all.filter((climb) => (
    (filters.source === "all" || climb.source === filters.source || (filters.source === "kilter" && climb.source === "kilter_db"))
    && angleValue(climb.angle) === Number(filters.angle)
    && gradeValue(climb.grade) >= filters.minGrade
    && gradeValue(climb.grade) <= filters.maxGrade
  ));
  filtered.sort(compareClimbs);
  state.visibleClimbs = filtered;
  climbSelect.innerHTML = filtered.map((climb) => {
    const prefix = climb.source === "user" ? "User: " : "";
    const grade = climb.grade && climb.grade !== "Unknown" ? ` (${climb.grade})` : "";
    return `<option value="${climb.value}">${prefix}${climb.name}${grade}</option>`;
  }).join("");
  const savedCount = filtered.filter((climb) => climb.source === "user").length;
  const total = (filters.source === "user" ? 0 : state.sourceTotal) + savedCount;
  availableClimbCount.textContent = `${total.toLocaleString()} climb${total === 1 ? "" : "s"}`;
  renderClimbResults(filtered);
}

function renderClimbResults(climbs) {
  if (!climbResults) return;
  if (!climbs.length) {
    climbResults.innerHTML = `<p class="emptyResults">No climbs match the current filters.</p>`;
    return;
  }
  climbResults.innerHTML = climbs.map((climb, index) => {
    const stars = Number.isFinite(numberValue(climb.stars)) ? `${Number(climb.stars).toFixed(2)} stars` : "Unknown stars";
    const ascents = Number.isFinite(numberValue(climb.ascensionist_count)) ? `${Number(climb.ascensionist_count).toLocaleString()} ascents` : "Unknown ascents";
    return `
      <button class="climbResult ${index === 0 ? "selected" : ""}" data-value="${escapeHtml(climb.value)}" type="button">
        <strong>${escapeHtml(climb.name || "Untitled")}</strong>
        <span>${escapeHtml(climb.grade || "Unknown")} · ${escapeHtml(String(climb.angle ?? "Unknown"))}° · ${stars} · ${ascents}</span>
      </button>
    `;
  }).join("");
  climbResults.querySelectorAll(".climbResult").forEach((button) => {
    button.addEventListener("click", async () => {
      climbResults.querySelectorAll(".climbResult").forEach((item) => item.classList.remove("selected"));
      button.classList.add("selected");
      climbSelect.value = button.dataset.value;
      await selectClimb(button.dataset.value);
    });
  });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  }[char]));
}

function compareClimbs(a, b) {
  const sort = state.appliedFilters.sort;
  if (sort === "gradeAsc") return gradeValue(a.grade) - gradeValue(b.grade) || a.name.localeCompare(b.name);
  if (sort === "gradeDesc") return gradeValue(b.grade) - gradeValue(a.grade) || a.name.localeCompare(b.name);
  if (sort === "ascentsAsc") return numberValue(a.ascensionist_count) - numberValue(b.ascensionist_count) || a.name.localeCompare(b.name);
  if (sort === "ascentsDesc") return numberValue(b.ascensionist_count) - numberValue(a.ascensionist_count) || a.name.localeCompare(b.name);
  if (sort === "starsAsc") return numberValue(a.stars) - numberValue(b.stars) || a.name.localeCompare(b.name);
  if (sort === "starsDesc") return numberValue(b.stars) - numberValue(a.stars) || a.name.localeCompare(b.name);
  if (sort === "source") return Number(b.source === "user") - Number(a.source === "user") || a.name.localeCompare(b.name);
  return a.name.localeCompare(b.name);
}

function gradeValue(grade) {
  const match = String(grade || "").match(/V(\d+)/i);
  return match ? Number(match[1]) : 99;
}

function angleValue(angle) {
  const numeric = Number.parseFloat(String(angle ?? "").replace("degrees", ""));
  return Number.isFinite(numeric) ? Math.round(numeric) : NaN;
}

function numberValue(value) {
  const numeric = Number.parseFloat(String(value ?? "").replace(/[^\d.+-]/g, ""));
  return Number.isFinite(numeric) ? numeric : -Infinity;
}

function updateGradeRangeLabel() {
  let minGrade = Number(gradeMinRange.value);
  let maxGrade = Number(gradeMaxRange.value);
  if (minGrade > maxGrade) {
    if (document.activeElement === gradeMinRange) {
      maxGrade = minGrade;
      gradeMaxRange.value = String(maxGrade);
    } else {
      minGrade = maxGrade;
      gradeMinRange.value = String(minGrade);
    }
  }
  gradeRangeLabel.textContent = minGrade === maxGrade ? `V${minGrade}` : `V${minGrade}-V${maxGrade}`;
}

async function applyClimbSearch() {
  updateGradeRangeLabel();
  state.searchName = "";
  state.randomGradePick = false;
  state.appliedFilters = {
    angle: angleFilter.value,
    minGrade: Number(gradeMinRange.value),
    maxGrade: Number(gradeMaxRange.value),
    source: sourceFilter.value,
    sort: sortSelect.value,
  };
  await refreshClimbs(false);
  if (climbSelect.value) {
    await selectClimb(climbSelect.value);
  } else {
    statusText.textContent = "No climbs match the current filters.";
  }
}

async function enterPage(page) {
  state.page = page;
  document.querySelectorAll(".page").forEach((item) => item.classList.toggle("active", item.id === `${page}Page`));
  document.querySelectorAll(".tabButton").forEach((item) => item.classList.toggle("selected", item.dataset.page === page));
  pageTitle.textContent = page === "browse" ? "Find a climb" : page === "set" ? "Set a climb" : "Climber beta";
  if (page === "set") {
    state.currentSource = "user";
    state.currentClimb = { name: newName.value, grade: newGrade.value, angle: newAngle.value, stars: "User set", matching_allowed: true, holds: emptyHolds() };
    state.baseImage = state.templateImage;
    state.overlayHolds = true;
    state.betaVisible = false;
    animCtx.clearRect(0, 0, animationCanvas.width, animationCanvas.height);
    renderMeta();
    drawBoard();
    statusText.textContent = "Pick a hold type, then click an actual hold on the board.";
  }
  if (page === "beta") {
    if (!state.betaVisible && state.currentClimb) await generateBeta(false);
  }
}

function addOrRemoveHold(point) {
  if (!state.validHolds.has(`${point.x}:${point.y}`)) {
    statusText.textContent = "Only actual holds on the board are clickable.";
    return;
  }
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
    matching_allowed: state.currentClimb.matching_allowed ?? true,
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
  state.currentSource = "user";
  state.currentClimb = normalizeClimb({ ...result.climb, source: "user" });
  state.sequence = result.sequence || [];
  state.footSequence = result.foot_sequence || [];
  state.sequenceMetrics = result.metrics || null;
  state.betaVisible = false;
  state.baseImage = state.templateImage;
  state.overlayHolds = true;
  await refreshClimbs(false);
  statusText.textContent = "Climb saved and displayed from coordinates.";
  renderMeta();
  drawBoard();
}

async function generateBeta(switchPage = true) {
  if (!state.currentClimb) return;
  statusText.textContent = "Generating beta animation.";
  await requestSequence(state.currentClimb);
  state.betaVisible = true;
  state.lastPose = null;
  state.lastPoseTime = 0;
  state.animationCycle = -1;
  state.animationStart = performance.now();
  if (switchPage) await enterPage("beta");
  statusText.textContent = "Generated beta is looping on the climb.";
}

async function generateClimbWithSetter(setter) {
  statusText.textContent = `Generating climb with ${setter}.`;
  const response = await fetch("/api/generate-climb", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      setter,
      grade: generatorGrade.value || newGrade.value,
      angle: generatorAngle.value || newAngle.value,
      seed: Number.parseInt(generatorSeed.value, 10),
      options: {
        hand_count: Number.parseInt(generatorHandCount.value, 10),
        foot_count: Number.parseInt(generatorFootCount.value, 10),
        hand_usage_preference: Number.parseInt(handUsagePreference.value, 10),
        foot_usage_preference: Number.parseInt(footUsagePreference.value, 10),
      },
    }),
  });
  const payload = await response.json();
  if (!response.ok) {
    statusText.textContent = payload.error || "Could not generate climb.";
    return;
  }
  state.currentSource = "user";
  state.currentClimb = normalizeClimb({ ...payload.climb, source: "user" });
  state.baseImage = state.templateImage;
  state.overlayHolds = true;
  state.betaVisible = false;
  state.sequence = payload.climb.sequence || payload.climb.hand_sequence || [];
  state.footSequence = payload.climb.foot_sequence || [];
  state.sequenceMetrics = payload.climb.sequence_metrics || null;
  newName.value = state.currentClimb.name;
  newGrade.value = state.currentClimb.grade;
  newAngle.value = state.currentClimb.angle;
  renderMeta();
  drawBoard();
  statusText.textContent = `${state.currentClimb.name} generated and ready to edit.`;
}

async function generateOutputArtifacts() {
  statusText.textContent = "Generating output artifacts.";
  const response = await fetch("/api/generate-outputs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ count: 32, trainNeural: false }),
  });
  const payload = await response.json();
  statusText.textContent = response.ok ? `Outputs generated at ${payload.manifest.generated_dir}.` : "Could not generate outputs.";
}

function loadBetaBuddyFile(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async () => {
    const image = await loadImage(String(reader.result));
    sampleCtx.clearRect(0, 0, sampleCanvas.width, sampleCanvas.height);
    sampleCtx.drawImage(image, 0, 0, sampleCanvas.width, sampleCanvas.height);
    const holds = detectColoredHoldComponents();
    state.currentSource = "user";
    state.currentClimb = normalizeClimb({
      id: "beta-buddy-upload",
      name: "Beta Buddy Upload",
      grade: "Unknown",
      angle: "50",
      stars: detectStars(),
      source: "user",
      holds,
      matching_allowed: true,
    });
    state.baseImage = image;
    state.overlayHolds = false;
    renderMeta();
    drawBoard();
    await generateBeta(false);
  };
  reader.readAsDataURL(file);
}

async function refreshClimbs(reselect = true) {
  const params = new URLSearchParams({
    angle: state.appliedFilters.angle,
    minGrade: String(state.appliedFilters.minGrade),
    maxGrade: String(state.appliedFilters.maxGrade),
    source: state.appliedFilters.source,
    sort: state.appliedFilters.sort,
    limit: "500",
  });
  if (state.searchName) params.set("name", state.searchName);
  const response = await fetch(`/api/climbs?${params.toString()}`);
  const payload = await response.json();
  state.sourceClimbs = payload.sourceClimbs || [];
  state.sourceTotal = payload.sourceTotal || state.sourceClimbs.length;
  state.savedClimbs = (payload.savedClimbs || []).map((climb, index) => ({ ...climb, id: climb.id || String(index) }));
  const previous = climbSelect.value;
  populateSelect();
  if (reselect && previous && [...climbSelect.options].some((option) => option.value === previous)) climbSelect.value = previous;
}

boardCanvas.addEventListener("click", (event) => {
  if (state.page !== "set") return;
  const rect = boardCanvas.getBoundingClientRect();
  const point = pointToHold(
    ((event.clientX - rect.left) / rect.width) * boardCanvas.width,
    ((event.clientY - rect.top) / rect.height) * boardCanvas.height,
  );
  if (point) addOrRemoveHold(point);
});

viewModes.forEach((viewMode) => {
  viewMode.addEventListener("change", () => {
    state.view = viewMode.value;
    viewModes.forEach((item) => {
      item.value = state.view;
    });
    drawBoard();
  });
});
sortSelect.addEventListener("change", updateGradeRangeLabel);
sourceFilter.addEventListener("change", updateGradeRangeLabel);
angleFilter.addEventListener("change", updateGradeRangeLabel);
gradeMinRange.addEventListener("input", updateGradeRangeLabel);
gradeMaxRange.addEventListener("input", updateGradeRangeLabel);
searchClimbsButton.addEventListener("click", applyClimbSearch);
climbSelect.addEventListener("change", () => selectClimb(climbSelect.value));
generateBetaButton.addEventListener("click", () => generateBeta(true));
setGenerateBetaButton.addEventListener("click", () => generateBeta(true));
restartBetaButton.addEventListener("click", () => generateBeta(false));
generateOutputsButton.addEventListener("click", generateOutputArtifacts);
betaBuddyUpload.addEventListener("change", () => loadBetaBuddyFile(betaBuddyUpload.files[0]));
betaModeSelect.addEventListener("change", () => {
  state.betaMode = betaModeSelect.value;
  state.lastPose = null;
  renderMeta();
});
document.querySelectorAll("[data-setter]").forEach((button) => {
  button.addEventListener("click", () => generateClimbWithSetter(button.dataset.setter));
});
speedInput.addEventListener("input", () => {
  state.betaSpeed = Number(speedInput.value);
});
unitSelect.addEventListener("change", () => {
  if (unitSelect.value === "metric") {
    heightInput.value = "168";
    apeInput.value = "+5";
  } else {
    heightInput.value = "5'6\"";
    apeInput.value = "+2\"";
  }
});
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
document.querySelectorAll(".tabButton").forEach((button) => {
  button.addEventListener("click", () => enterPage(button.dataset.page));
});

function tick(time) {
  drawMonkeyFrame(time);
  requestAnimationFrame(tick);
}

async function init() {
  state.templateImage = await loadImage("/kilter_climbs_output/output_template.png");
  state.baseImage = state.templateImage;
  detectValidHoldsFromTemplate();
  applyQueryParams();
  updateGradeRangeLabel();
  await refreshClimbs();
  if (state.randomGradePick && state.visibleClimbs.length) {
    const pick = state.visibleClimbs[Math.floor(Math.random() * state.visibleClimbs.length)];
    climbSelect.value = pick.value;
  }
  if (climbSelect.value) await selectClimb(climbSelect.value);
  if (new URLSearchParams(window.location.search).get("page") === "beta") await generateBeta(true);
  requestAnimationFrame(tick);
}

function applyQueryParams() {
  const params = new URLSearchParams(window.location.search);
  if (params.has("angle")) {
    angleFilter.value = params.get("angle");
    state.appliedFilters.angle = params.get("angle");
  }
  const grade = params.get("grade");
  if (grade) {
    const value = gradeValue(grade);
    if (value !== 99) {
      gradeMinRange.value = String(value);
      gradeMaxRange.value = String(value);
      state.appliedFilters.minGrade = value;
      state.appliedFilters.maxGrade = value;
      state.randomGradePick = true;
    }
  }
  const name = params.get("name");
  if (name) {
    state.searchName = name;
    state.randomGradePick = false;
  }
}

init().catch((error) => {
  statusText.textContent = `Failed to start: ${error.message}`;
});
