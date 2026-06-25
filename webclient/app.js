// Realtime test client for the Ensight AI chat + voice WebSockets.
// Served same-origin from the backend at /demo, so REST + WS use location.

const $ = (id) => document.getElementById(id);
const httpBase = location.origin;
const wsBase = (location.protocol === "https:" ? "wss://" : "ws://") + location.host;

let token = null;
let capability = null;

function log(el, msg, cls) {
  const line = document.createElement("div");
  if (cls) line.className = cls;
  line.textContent = msg;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
  return line;
}

// --- 1. Session -----------------------------------------------------------
$("createSession").onclick = async () => {
  const public_key = $("publicKey").value.trim();
  const visitor_id = $("visitorId").value.trim() || null;
  if (!public_key) return alert("Enter a public key");

  $("sessionStatus").textContent = "creating...";
  try {
    const res = await fetch(`${httpBase}/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ public_key, visitor_id }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const data = await res.json();
    token = data.access_token;
    capability = data.capability;
    $("sessionStatus").textContent = `ready · ${capability} · convo ${data.conversation_id.slice(0, 8)}`;
    $("sessionStatus").className = "pill ok";

    const canChat = capability === "chat" || capability === "both";
    const canVoice = capability === "voice" || capability === "both";
    $("connectChat").disabled = !canChat;
    $("connectVoice").disabled = !canVoice;
  } catch (e) {
    $("sessionStatus").textContent = "error: " + e.message;
    $("sessionStatus").className = "pill err";
  }
};

// --- 2. Chat --------------------------------------------------------------
let chatWs = null;
let currentLine = null;

$("connectChat").onclick = () => {
  chatWs = new WebSocket(`${wsBase}/ws/chat?token=${encodeURIComponent(token)}`);
  chatWs.onopen = () => {
    $("chatState").textContent = "connected";
    $("chatState").className = "pill ok";
    $("chatInput").disabled = false;
    $("sendChat").disabled = false;
  };
  chatWs.onclose = () => {
    $("chatState").textContent = "disconnected";
    $("chatState").className = "pill";
    $("chatInput").disabled = true;
    $("sendChat").disabled = true;
  };
  chatWs.onerror = () => log($("chatLog"), "[ws error]", "err");
  chatWs.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "token") {
      if (!currentLine) currentLine = log($("chatLog"), "bot: ");
      currentLine.textContent += msg.data;
    } else if (msg.type === "done") {
      currentLine = null;
      log($("chatLog"), `[done · lang=${msg.language}]`);
    } else if (msg.type === "error") {
      log($("chatLog"), "error: " + msg.detail, "err");
    }
  };
};

function sendChat() {
  const text = $("chatInput").value.trim();
  if (!text || !chatWs) return;
  log($("chatLog"), "you: " + text);
  currentLine = null;
  chatWs.send(JSON.stringify({ question: text }));
  $("chatInput").value = "";
}
$("sendChat").onclick = sendChat;
$("chatInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendChat();
});

// --- 3. Voice -------------------------------------------------------------
let voiceWs = null;
let mediaRecorder = null;
let recordedChunks = [];
const audioQueue = [];
let playing = false;

function enqueueAudio(arrayBuffer) {
  audioQueue.push(new Blob([arrayBuffer], { type: "audio/mpeg" }));
  if (!playing) playNext();
}
function playNext() {
  if (!audioQueue.length) {
    playing = false;
    return;
  }
  playing = true;
  const url = URL.createObjectURL(audioQueue.shift());
  const audio = new Audio(url);
  audio.onended = () => {
    URL.revokeObjectURL(url);
    playNext();
  };
  audio.play().catch(() => playNext());
}

$("connectVoice").onclick = () => {
  voiceWs = new WebSocket(`${wsBase}/ws/voice?token=${encodeURIComponent(token)}`);
  voiceWs.binaryType = "arraybuffer";
  voiceWs.onopen = () => {
    $("voiceState").textContent = "connected";
    $("voiceState").className = "pill ok";
    $("recordBtn").disabled = false;
  };
  voiceWs.onclose = () => {
    $("voiceState").textContent = "disconnected";
    $("voiceState").className = "pill";
    $("recordBtn").disabled = true;
  };
  voiceWs.onerror = () => log($("voiceLog"), "[ws error]", "err");
  voiceWs.onmessage = (ev) => {
    if (ev.data instanceof ArrayBuffer) {
      enqueueAudio(ev.data); // a spoken sentence
      return;
    }
    const msg = JSON.parse(ev.data);
    if (msg.type === "transcript") log($("voiceLog"), "you (heard): " + msg.text);
    else if (msg.type === "token") {
      if (!currentLine) currentLine = log($("voiceLog"), "bot: ");
      currentLine.textContent += msg.data;
    } else if (msg.type === "done") {
      currentLine = null;
      log($("voiceLog"), `[done · lang=${msg.language}]`);
    } else if (msg.type === "error") {
      log($("voiceLog"), "error: " + msg.detail, "err");
    }
  };
};

async function startRecording() {
  if (!voiceWs || voiceWs.readyState !== WebSocket.OPEN) return;
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  recordedChunks = [];
  mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size) recordedChunks.push(e.data);
  };
  mediaRecorder.onstop = async () => {
    stream.getTracks().forEach((t) => t.stop());
    const blob = new Blob(recordedChunks, { type: "audio/webm" });
    const buf = await blob.arrayBuffer();
    voiceWs.send(buf); // whole utterance as one binary message
    voiceWs.send(JSON.stringify({ type: "end" }));
    currentLine = null;
  };
  mediaRecorder.start();
  $("recordBtn").textContent = "● recording…";
}
function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") mediaRecorder.stop();
  $("recordBtn").textContent = "● Hold to record";
}

const recBtn = $("recordBtn");
recBtn.addEventListener("mousedown", startRecording);
recBtn.addEventListener("mouseup", stopRecording);
recBtn.addEventListener("mouseleave", stopRecording);
recBtn.addEventListener("touchstart", (e) => { e.preventDefault(); startRecording(); });
recBtn.addEventListener("touchend", (e) => { e.preventDefault(); stopRecording(); });
