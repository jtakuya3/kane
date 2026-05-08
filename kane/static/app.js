// Kane — Realtime English <-> Japanese voice translator (browser client)
// Connects to OpenAI Realtime 2 via WebRTC using an ephemeral key minted by
// the FastAPI backend (`POST /api/session`).

const TRANSLATOR_INSTRUCTIONS = `
You are an invisible real-time interpreter. The user is having a conversation
across two languages: English and Japanese. Your sole job is to translate.

CRITICAL RULES — follow them exactly:
1. Detect the language of each user utterance.
   - If the user speaks ENGLISH, respond ONLY in natural, fluent JAPANESE.
   - If the user speaks JAPANESE, respond ONLY in natural, fluent ENGLISH.
2. Output ONLY the translation. Never add commentary, greetings, prefaces,
   apologies, repetitions of the source, language labels, or quotation marks.
3. NEVER answer the content as if you were a participant. You are an
   interpreter — even questions directed at you must be translated, not
   answered.
4. Preserve the speaker's tone, register (formal/casual), and emotion.
5. Preserve numbers, dates, names, and proper nouns accurately. For Japanese
   proper nouns rendered in English, use their natural Japanese form when
   translating into Japanese.
6. Keep the translation concise and the speaking pace similar to the original.
7. If the audio is silent, unintelligible, or contains only filler sounds,
   output nothing at all. Do not invent content.
8. Do not mix languages within a single output. The output is exclusively in
   the target language.
9. When the speaker swaps languages mid-conversation, swap the target
   language accordingly without comment.
`.trim();

const $ = (id) => document.getElementById(id);
const transcriptEl = $("transcript");
const statusEl = $("status");
const talkBtn = $("talk-btn");
const muteBtn = $("mute-btn");
const endBtn = $("end-btn");
const settingsBtn = $("settings-btn");
const settingsDialog = $("settings");
const voiceSelect = $("voice-select");
const captionsToggle = $("captions-toggle");
const remoteAudio = $("remote-audio");
const modelNameEl = $("model-name");

// Restore preferences
const prefs = JSON.parse(localStorage.getItem("kane.prefs") || "{}");
if (prefs.voice) voiceSelect.value = prefs.voice;
if (typeof prefs.captions === "boolean") captionsToggle.checked = prefs.captions;
const savePrefs = () => {
  localStorage.setItem(
    "kane.prefs",
    JSON.stringify({ voice: voiceSelect.value, captions: captionsToggle.checked }),
  );
};
voiceSelect.addEventListener("change", savePrefs);
captionsToggle.addEventListener("change", () => {
  savePrefs();
  if (!captionsToggle.checked) clearPartialBubbles();
});

settingsBtn.addEventListener("click", () => settingsDialog.showModal());

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const state = {
  pc: /** @type {RTCPeerConnection|null} */ (null),
  dc: /** @type {RTCDataChannel|null} */ (null),
  micStream: /** @type {MediaStream|null} */ (null),
  active: false,
  muted: false,
  // Per-event-id partial bubbles for streaming captions
  partials: new Map(),
};

function setStatus(text, kind = "idle") {
  statusEl.textContent = text;
  statusEl.className = `status status--${kind}`;
}

function setTalkState(s) {
  talkBtn.dataset.state = s;
  if (s === "active") talkBtn.querySelector(".talk-btn__label").textContent = "STOP";
  else if (s === "connecting") talkBtn.querySelector(".talk-btn__label").textContent = "...";
  else talkBtn.querySelector(".talk-btn__label").textContent = "START";
}

// ---------------------------------------------------------------------------
// Captions
// ---------------------------------------------------------------------------
function clearHint() {
  const hint = transcriptEl.querySelector(".hint");
  if (hint) hint.remove();
}

function clearPartialBubbles() {
  for (const el of transcriptEl.querySelectorAll(".bubble--partial")) el.remove();
  state.partials.clear();
}

function appendBubble({ id, side, lang, text, partial }) {
  if (!captionsToggle.checked) return;
  clearHint();
  let el = id ? document.getElementById(id) : null;
  if (!el) {
    el = document.createElement("div");
    if (id) el.id = id;
    el.className = `bubble bubble--${side}`;
    const langEl = document.createElement("div");
    langEl.className = "bubble__lang";
    langEl.textContent = lang;
    const textEl = document.createElement("div");
    textEl.className = "bubble__text";
    el.appendChild(langEl);
    el.appendChild(textEl);
    transcriptEl.appendChild(el);
  }
  el.classList.toggle("bubble--partial", !!partial);
  el.querySelector(".bubble__text").textContent = text;
  // Auto scroll
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

// Heuristic: detect Japanese characters
function detectLangLabel(text) {
  if (/[぀-ヿ一-鿿]/.test(text)) return "JA";
  if (/[A-Za-z]/.test(text)) return "EN";
  return "—";
}

// ---------------------------------------------------------------------------
// Realtime event handler
// ---------------------------------------------------------------------------
function handleRealtimeEvent(evt) {
  // Helpful for debugging in the browser console.
  if (evt.type && !evt.type.endsWith(".delta")) {
    console.debug("[oai-event]", evt.type, evt);
  }

  switch (evt.type) {
    case "session.created":
    case "session.updated":
      // no-op
      break;

    // --- input transcription (what the user said) ----------------------
    case "conversation.item.input_audio_transcription.delta": {
      const id = `in-${evt.item_id}`;
      const prev = state.partials.get(id) || "";
      const next = prev + (evt.delta || "");
      state.partials.set(id, next);
      appendBubble({
        id,
        side: "in",
        lang: detectLangLabel(next),
        text: next,
        partial: true,
      });
      break;
    }
    case "conversation.item.input_audio_transcription.completed": {
      const id = `in-${evt.item_id}`;
      const text = (evt.transcript || state.partials.get(id) || "").trim();
      state.partials.delete(id);
      if (text) {
        appendBubble({
          id,
          side: "in",
          lang: detectLangLabel(text),
          text,
          partial: false,
        });
      } else {
        const el = document.getElementById(id);
        if (el) el.remove();
      }
      break;
    }

    // --- output transcript (the translation we hear) -------------------
    // Newer event names (Realtime 2) and older variants both handled.
    case "response.output_audio_transcript.delta":
    case "response.audio_transcript.delta": {
      const id = `out-${evt.response_id}-${evt.item_id || ""}`;
      const prev = state.partials.get(id) || "";
      const next = prev + (evt.delta || "");
      state.partials.set(id, next);
      appendBubble({
        id,
        side: "out",
        lang: detectLangLabel(next),
        text: next,
        partial: true,
      });
      setStatus("通訳中…", "speaking");
      break;
    }
    case "response.output_audio_transcript.done":
    case "response.audio_transcript.done": {
      const id = `out-${evt.response_id}-${evt.item_id || ""}`;
      const text = (evt.transcript || state.partials.get(id) || "").trim();
      state.partials.delete(id);
      if (text) {
        appendBubble({
          id,
          side: "out",
          lang: detectLangLabel(text),
          text,
          partial: false,
        });
      } else {
        const el = document.getElementById(id);
        if (el) el.remove();
      }
      break;
    }

    // --- VAD / turn signals -------------------------------------------
    case "input_audio_buffer.speech_started":
      setStatus("聞き取り中…", "listening");
      break;
    case "input_audio_buffer.speech_stopped":
      setStatus("通訳中…", "speaking");
      break;
    case "response.done":
    case "response.completed":
      if (state.active) setStatus("待機中（話してください）", "listening");
      break;

    // --- errors --------------------------------------------------------
    case "error": {
      console.error("Realtime error:", evt);
      setStatus(`エラー: ${evt.error?.message || "unknown"}`, "error");
      break;
    }
  }
}

// ---------------------------------------------------------------------------
// Connect / disconnect
// ---------------------------------------------------------------------------
async function start() {
  if (state.active) return;
  setStatus("接続中…", "connecting");
  setTalkState("connecting");
  talkBtn.disabled = true;

  try {
    // 1) Mic
    state.micStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
      video: false,
    });

    // 2) Ephemeral key
    const sessionResp = await fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ voice: voiceSelect.value }),
    });
    if (!sessionResp.ok) {
      throw new Error(`Failed to create session: ${sessionResp.status} ${await sessionResp.text()}`);
    }
    const { client_secret, model } = await sessionResp.json();
    if (!client_secret) throw new Error("No client_secret in response");
    if (model) modelNameEl.textContent = model;

    // 3) Peer connection
    const pc = new RTCPeerConnection();
    state.pc = pc;

    pc.ontrack = (e) => {
      remoteAudio.srcObject = e.streams[0];
    };
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "failed" || pc.connectionState === "disconnected") {
        setStatus("接続が切れました", "error");
        stop();
      }
    };

    // Add mic
    for (const track of state.micStream.getTracks()) {
      pc.addTrack(track, state.micStream);
    }

    // Data channel for events
    const dc = pc.createDataChannel("oai-events");
    state.dc = dc;
    dc.onopen = () => {
      // Configure session for translation duty.
      const sessionUpdate = {
        type: "session.update",
        session: {
          type: "realtime",
          instructions: TRANSLATOR_INSTRUCTIONS,
          audio: {
            input: {
              transcription: { model: "gpt-4o-mini-transcribe" },
              turn_detection: {
                type: "server_vad",
                threshold: 0.55,
                prefix_padding_ms: 250,
                silence_duration_ms: 600,
                create_response: true,
                interrupt_response: true,
              },
            },
            output: {
              voice: voiceSelect.value,
            },
          },
        },
      };
      dc.send(JSON.stringify(sessionUpdate));
    };
    dc.onmessage = (e) => {
      try {
        handleRealtimeEvent(JSON.parse(e.data));
      } catch (err) {
        console.error("Failed to parse event", err, e.data);
      }
    };

    // 4) SDP offer -> /v1/realtime/calls -> answer
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    const sdpResp = await fetch("https://api.openai.com/v1/realtime/calls", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${client_secret}`,
        "Content-Type": "application/sdp",
      },
      body: offer.sdp,
    });
    if (!sdpResp.ok) {
      throw new Error(`SDP exchange failed: ${sdpResp.status} ${await sdpResp.text()}`);
    }
    const answerSdp = await sdpResp.text();
    await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });

    state.active = true;
    setTalkState("active");
    talkBtn.disabled = false;
    muteBtn.disabled = false;
    endBtn.disabled = false;
    setStatus("接続中（話してください）", "listening");
  } catch (err) {
    console.error(err);
    setStatus(`エラー: ${err.message || err}`, "error");
    setTalkState("idle");
    talkBtn.disabled = false;
    cleanup();
  }
}

function cleanup() {
  if (state.dc) {
    try {
      state.dc.close();
    } catch {}
    state.dc = null;
  }
  if (state.pc) {
    try {
      state.pc.close();
    } catch {}
    state.pc = null;
  }
  if (state.micStream) {
    for (const t of state.micStream.getTracks()) t.stop();
    state.micStream = null;
  }
  state.active = false;
  state.muted = false;
  state.partials.clear();
  muteBtn.dataset.state = "";
  muteBtn.textContent = "🎤";
  muteBtn.disabled = true;
  endBtn.disabled = true;
  setTalkState("idle");
}

function stop() {
  cleanup();
  setStatus("待機中", "idle");
}

function toggleMute() {
  if (!state.micStream) return;
  state.muted = !state.muted;
  for (const t of state.micStream.getAudioTracks()) t.enabled = !state.muted;
  muteBtn.dataset.state = state.muted ? "muted" : "";
  muteBtn.textContent = state.muted ? "🔇" : "🎤";
}

talkBtn.addEventListener("click", () => {
  if (state.active) stop();
  else start();
});
muteBtn.addEventListener("click", toggleMute);
endBtn.addEventListener("click", stop);

// Stop the session if the user navigates away.
window.addEventListener("pagehide", cleanup);

// Hint about HTTPS requirement on insecure origins.
if (
  typeof window !== "undefined" &&
  !window.isSecureContext &&
  location.hostname !== "localhost" &&
  location.hostname !== "127.0.0.1"
) {
  setStatus("HTTPS が必要です", "error");
  talkBtn.disabled = true;
}
