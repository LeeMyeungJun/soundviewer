/* All URLs are relative so the viewer also works under /repository-name/. */
const catalog = globalThis.SOUND_CATALOG;
const $ = (id) => document.getElementById(id);
const cards = $("cards");
const viewer = $("viewer");
const player = $("player");
let selected = null;
let openingButton = null;

function renderCards(category) {
  cards.replaceChildren();
  const items = catalog.filter((item) => category === "전체" || item.category === category);
  $("item-count").textContent = items.length;
  for (const item of items) {
    const button = document.createElement("button");
    button.className = "card";
    button.dataset.id = item.id;
    button.setAttribute("aria-label", `${item.name} 큰 그림 보기`);
    const image = document.createElement("img");
    image.src = item.image;
    image.alt = "";
    image.width = 400;
    image.height = 400;
    image.decoding = "async";
    const content = document.createElement("span");
    content.className = "card-content";
    const title = document.createElement("span");
    title.className = "card-title";
    title.textContent = item.name;
    const english = document.createElement("span");
    english.className = "card-english";
    english.textContent = item.english;
    title.append(english);
    const symbol = document.createElement("span");
    symbol.className = "card-symbol";
    symbol.textContent = "＋";
    symbol.setAttribute("aria-hidden", "true");
    content.append(title, symbol);
    button.append(image, content);
    button.addEventListener("click", () => openItem(item, button));
    cards.append(button);
  }
}

document.querySelectorAll(".filter").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".filter").forEach((filter) => {
      const active = filter === button;
      filter.classList.toggle("active", active);
      filter.setAttribute("aria-pressed", String(active));
    });
    renderCards(button.dataset.category);
  });
});

function updatePlayback() {
  const playing = !player.paused && !player.ended;
  $("play").replaceChildren();
  const icon = document.createElement("span");
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = playing ? "Ⅱ" : "▶";
  $("play").append(icon, " 듣기");
  $("play").setAttribute("aria-pressed", String(playing));
  $("play").setAttribute("aria-label", playing ? "소리 일시정지" : "소리 듣기");
}

function openItem(item, button) {
  selected = item;
  openingButton = button;
  $("viewer-image").src = item.image;
  $("viewer-image").alt = item.name + " 그림";
  $("viewer-title").textContent = item.name;
  player.src = item.audio;
  player.loop = $("repeat").getAttribute("aria-pressed") === "true";
  $("play-status").classList.add("sr-only");
  $("play-status").textContent = "재생 버튼을 눌러 소리를 들어 보세요.";
  updatePlayback();
  viewer.showModal();
}

$("close-viewer").addEventListener("click", () => viewer.close());
viewer.addEventListener("click", (event) => {
  const box = viewer.getBoundingClientRect();
  if (event.target === viewer && (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom)) viewer.close();
});
viewer.addEventListener("close", () => {
  player.pause();
  player.removeAttribute("src");
  player.load();
  openingButton?.focus();
});
$("play").addEventListener("click", () => {
  $("play-status").classList.add("sr-only");
  if (!player.paused) {
    player.pause();
    $("play-status").textContent = "잠시 멈췄어요.";
    return;
  }
  $("play-status").textContent = "소리를 준비하고 있어요…";
  // Call play directly in the tap handler to preserve Safari's user gesture.
  player.play().catch(() => {
    if (!viewer.open) return;
    if (player.error) $("play-status").textContent = "소리를 불러오지 못했어요. 인터넷 연결 후 다시 시도해 주세요.";
    else if (player.paused) $("play-status").textContent = "재생 버튼을 다시 눌러 주세요.";
    $("play-status").classList.remove("sr-only");
  });
});
$("repeat").addEventListener("click", () => {
  player.loop = !player.loop;
  $("repeat").setAttribute("aria-pressed", String(player.loop));
});
for (const event of ["play", "pause", "ended", "emptied"]) player.addEventListener(event, updatePlayback);
player.addEventListener("playing", () => { $("play-status").textContent = `${selected.name} 소리를 듣고 있어요.`; });
player.addEventListener("ended", () => { $("play-status").textContent = "한 번 더 들어 볼까요?"; });
player.addEventListener("error", () => {
  if (viewer.open) {
    $("play-status").textContent = "소리를 불러오지 못했어요. 인터넷 연결 후 다시 시도해 주세요.";
    $("play-status").classList.remove("sr-only");
  }
});
document.addEventListener("visibilitychange", () => {
  if (document.hidden) player.pause();
});

let cacheWorker;
function showCacheState(state) {
  $("cache-title").textContent = state.complete ? "오프라인 사용 준비 완료" : state.error ? "아직 저장하지 못한 파일이 있어요" : "그림과 소리를 기기에 저장하고 있어요";
  $("cache-detail").textContent = state.complete ? "모든 그림과 소리가 저장됐어요. 인터넷 없이도 다시 보고 들을 수 있어요." : state.error ? `저장 ${state.done}/${state.total}개 · 인터넷 연결과 기기 저장 공간을 확인한 뒤 다시 시도해 주세요.` : `저장 ${state.done}/${state.total}개 · 처음 한 번만 내려받아요. 이 화면을 열어 두세요.`;
  $("cache-progress").max = state.total || 1;
  $("cache-progress").value = state.done || 0;
  $("cache-progress").hidden = !!state.complete;
  $("cache-retry").hidden = !state.error;
}
function startCaching() {
  $("cache-retry").hidden = true;
  cacheWorker?.postMessage({ type: "CACHE_ALL" });
}
async function registerOffline() {
  if (!("serviceWorker" in navigator) || !window.isSecureContext) {
    $("cache-title").textContent = "이 환경에서는 오프라인 저장을 사용할 수 없어요";
    $("cache-detail").textContent = "Safari 또는 Chrome에서 HTTPS 사이트 주소로 접속해 주세요.";
    $("cache-progress").hidden = true;
    return;
  }
  navigator.serviceWorker.addEventListener("message", (event) => {
    if (event.data?.type === "CACHE_PROGRESS") showCacheState(event.data);
  });
  try {
    const registration = await navigator.serviceWorker.register("./sw.js", { updateViaCache: "none" });
    // ready never rejects if installation fails, so watch the worker state instead.
    const installing = registration.installing || registration.waiting;
    if (installing) await new Promise((resolve, reject) => {
      const check = () => {
        if (installing.state === "activated") {
          installing.removeEventListener("statechange", check);
          resolve();
        } else if (installing.state === "redundant") {
          installing.removeEventListener("statechange", check);
          if (registration.active) resolve();
          else reject(new Error("Offline installation failed"));
        }
      };
      installing.addEventListener("statechange", check);
      check();
    });
    cacheWorker = registration.active;
    if (!cacheWorker) throw new Error("No active offline worker");
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      cacheWorker = navigator.serviceWorker.controller;
      startCaching();
    });
    startCaching();
    // This is a best-effort request; the browser decides whether storage persists.
    if (navigator.storage?.persist) navigator.storage.persist().catch(() => {});
  } catch {
    $("cache-title").textContent = "오프라인 저장을 시작하지 못했어요";
    $("cache-detail").textContent = "인터넷에 연결한 뒤 다시 저장해 주세요. 현재 열려 있는 그림과 소리는 사용할 수 있어요.";
    $("cache-progress").hidden = true;
    $("cache-retry").hidden = false;
  }
}
$("cache-retry").addEventListener("click", () => cacheWorker ? startCaching() : registerOffline());
window.addEventListener("online", () => { if (cacheWorker) startCaching(); });
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && cacheWorker) startCaching();
});
renderCards("전체");
registerOffline();
