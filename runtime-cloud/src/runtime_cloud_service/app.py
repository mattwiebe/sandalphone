from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .bot_manager import InMemoryBotManager
from .config import load_runtime_cloud_config
from .tokens import issue_room_participant_token, issue_trusted_leg_token


app = FastAPI(title="Levi Runtime Cloud")


def _create_bot(room_name: str, trusted_identity: str):
    from .trusted_leg_bot import TrustedLegBotConfig, TrustedLegPipecatBot

    config = load_runtime_cloud_config()
    return TrustedLegPipecatBot(
        livekit_url=config.livekit_url,
        api_key=config.livekit_api_key,
        api_secret=config.livekit_api_secret,
        config=TrustedLegBotConfig(
            room_name=room_name,
            trusted_identity=trusted_identity,
        ),
    )


app.state.bot_manager = InMemoryBotManager(_create_bot)


class TrustedTokenRequest(BaseModel):
    room_name: str
    identity: str
    name: str | None = None


class BotStartRequest(BaseModel):
    room_name: str
    trusted_identity: str


@app.get("/health")
def health() -> dict[str, str]:
    config = load_runtime_cloud_config()
    missing = [
        key
        for key, value in {
            "LIVEKIT_URL": config.livekit_url,
            "LIVEKIT_API_KEY": config.livekit_api_key,
            "LIVEKIT_API_SECRET": config.livekit_api_secret,
        }.items()
        if not value
    ]
    return {
        "status": "healthy" if not missing else "degraded",
        "missing": ",".join(missing),
    }


@app.post("/tokens/trusted")
def trusted_token(request: TrustedTokenRequest) -> dict[str, str]:
    config = load_runtime_cloud_config()
    if not config.livekit_api_key or not config.livekit_api_secret:
        raise HTTPException(status_code=503, detail="LiveKit credentials not configured")

    token = issue_trusted_leg_token(
        config=config,
        room_name=request.room_name,
        identity=request.identity,
        name=request.name,
    )
    return {
        "token": token,
        "room_name": request.room_name,
        "identity": request.identity,
        "livekit_url": config.livekit_url,
    }


@app.post("/trusted/credentials")
def trusted_credentials(request: TrustedTokenRequest) -> dict[str, str]:
    config = load_runtime_cloud_config()
    if not config.livekit_api_key or not config.livekit_api_secret:
        raise HTTPException(status_code=503, detail="LiveKit credentials not configured")

    token = issue_trusted_leg_token(
        config=config,
        room_name=request.room_name,
        identity=request.identity,
        name=request.name,
    )
    return {
        "serverUrl": config.livekit_url,
        "roomName": request.room_name,
        "participantName": request.name or request.identity,
        "participantIdentity": request.identity,
        "participantToken": token,
    }


@app.post("/caller/credentials")
def caller_credentials(request: TrustedTokenRequest) -> dict[str, str]:
    config = load_runtime_cloud_config()
    if not config.livekit_api_key or not config.livekit_api_secret:
        raise HTTPException(status_code=503, detail="LiveKit credentials not configured")

    token = issue_room_participant_token(
        config=config,
        room_name=request.room_name,
        identity=request.identity,
        name=request.name,
    )
    return {
        "serverUrl": config.livekit_url,
        "roomName": request.room_name,
        "participantName": request.name or request.identity,
        "participantIdentity": request.identity,
        "participantToken": token,
    }


@app.get("/trusted", response_class=HTMLResponse)
def trusted_page() -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Levi Trusted Leg</title>
    <style>
      :root {
        color-scheme: light;
        font-family: ui-sans-serif, system-ui, sans-serif;
        background: #f3efe6;
        color: #1c1917;
      }
      body {
        margin: 0;
        min-height: 100vh;
        background:
          radial-gradient(circle at top, rgba(245, 158, 11, 0.18), transparent 36%),
          linear-gradient(180deg, #f8f3ea 0%, #efe6d7 100%);
      }
      main {
        max-width: 760px;
        margin: 0 auto;
        padding: 32px 20px 48px;
      }
      .card {
        background: rgba(255, 251, 235, 0.84);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(120, 53, 15, 0.12);
        border-radius: 24px;
        padding: 24px;
        box-shadow: 0 24px 60px rgba(120, 53, 15, 0.12);
      }
      h1 {
        font-size: clamp(2rem, 4vw, 3rem);
        margin: 0 0 8px;
      }
      p {
        line-height: 1.5;
      }
      form {
        display: grid;
        gap: 14px;
        margin-top: 20px;
      }
      label {
        display: grid;
        gap: 6px;
        font-size: 0.92rem;
        font-weight: 600;
      }
      input {
        border: 1px solid rgba(120, 53, 15, 0.18);
        border-radius: 14px;
        padding: 12px 14px;
        font: inherit;
        background: #fffdf8;
      }
      .actions {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }
      button {
        border: 0;
        border-radius: 999px;
        padding: 12px 18px;
        font: inherit;
        font-weight: 700;
        cursor: pointer;
      }
      button[type="submit"] {
        background: #0f766e;
        color: white;
      }
      button[data-leave] {
        background: #e7e5e4;
        color: #1c1917;
      }
      #status {
        margin-top: 18px;
        padding: 12px 14px;
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.72);
        font-size: 0.95rem;
      }
      #participants {
        margin-top: 18px;
        padding-left: 20px;
      }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/livekit-client@2.15.6/dist/livekit-client.umd.min.js"></script>
  </head>
  <body>
    <main>
      <div class="card">
        <h1>Trusted Leg</h1>
        <p>Join the LiveKit room for private translated audio. Use headphones or earbuds so the caller never hears the trusted-leg mix.</p>
        <form id="join-form">
          <label>
            Room
            <input id="room" name="room" value="call-main" />
          </label>
          <label>
            Identity
            <input id="identity" name="identity" value="trusted-matt" />
          </label>
          <label>
            Name
            <input id="name" name="name" value="Matt" />
          </label>
          <div class="actions">
            <button type="submit">Join Room</button>
            <button type="button" data-leave>Leave</button>
          </div>
        </form>
        <div id="status">Idle.</div>
        <ul id="participants"></ul>
      </div>
    </main>
    <script>
      const statusEl = document.getElementById("status");
      const participantsEl = document.getElementById("participants");
      const form = document.getElementById("join-form");
      const leaveButton = document.querySelector("[data-leave]");
      let room;

      function setStatus(message) {
        statusEl.textContent = message;
      }

      function renderParticipants() {
        if (!room) {
          participantsEl.innerHTML = "";
          return;
        }
        const items = [...room.remoteParticipants.values()].map((participant) => {
          return `<li>${participant.identity}</li>`;
        });
        participantsEl.innerHTML = items.join("");
      }

      function attachAudio(track) {
        const element = track.attach();
        element.autoplay = true;
        element.playsInline = true;
        document.body.appendChild(element);
      }

      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        setStatus("Requesting LiveKit token...");
        if (room) {
          await room.disconnect();
        }

        const payload = {
          room_name: document.getElementById("room").value,
          identity: document.getElementById("identity").value,
          name: document.getElementById("name").value,
        };
        const response = await fetch("/trusted/credentials", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const credentials = await response.json();
        room = new LivekitClient.Room();
        room.on(LivekitClient.RoomEvent.TrackSubscribed, (track) => {
          if (track.kind === "audio") {
            attachAudio(track);
          }
        });
        room.on(LivekitClient.RoomEvent.ParticipantConnected, renderParticipants);
        room.on(LivekitClient.RoomEvent.ParticipantDisconnected, renderParticipants);
        room.on(LivekitClient.RoomEvent.Disconnected, () => {
          setStatus("Disconnected.");
          renderParticipants();
        });

        await room.connect(credentials.serverUrl, credentials.participantToken);
        renderParticipants();
        setStatus(`Connected to ${credentials.roomName} as ${credentials.participantIdentity}.`);
      });

      leaveButton.addEventListener("click", async () => {
        if (room) {
          await room.disconnect();
          room = null;
        }
        setStatus("Disconnected.");
        renderParticipants();
      });
    </script>
  </body>
</html>"""


@app.get("/caller", response_class=HTMLResponse)
def caller_page() -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Levi Caller Simulator</title>
    <style>
      :root {
        color-scheme: light;
        font-family: ui-sans-serif, system-ui, sans-serif;
        background: #eef6ff;
        color: #0f172a;
      }
      body {
        margin: 0;
        min-height: 100vh;
        background:
          radial-gradient(circle at top, rgba(14, 165, 233, 0.2), transparent 34%),
          linear-gradient(180deg, #f7fbff 0%, #dbeafe 100%);
      }
      main {
        max-width: 760px;
        margin: 0 auto;
        padding: 32px 20px 48px;
      }
      .card {
        background: rgba(239, 246, 255, 0.9);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(30, 64, 175, 0.14);
        border-radius: 24px;
        padding: 24px;
        box-shadow: 0 24px 60px rgba(30, 64, 175, 0.14);
      }
      h1 {
        font-size: clamp(2rem, 4vw, 3rem);
        margin: 0 0 8px;
      }
      p {
        line-height: 1.5;
      }
      form {
        display: grid;
        gap: 14px;
        margin-top: 20px;
      }
      label {
        display: grid;
        gap: 6px;
        font-size: 0.92rem;
        font-weight: 600;
      }
      input {
        border: 1px solid rgba(30, 64, 175, 0.18);
        border-radius: 14px;
        padding: 12px 14px;
        font: inherit;
        background: #fff;
      }
      .actions {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }
      button {
        border: 0;
        border-radius: 999px;
        padding: 12px 18px;
        font: inherit;
        font-weight: 700;
        cursor: pointer;
      }
      button[type="submit"] {
        background: #1d4ed8;
        color: white;
      }
      button[data-leave] {
        background: #dbeafe;
        color: #0f172a;
      }
      #status {
        margin-top: 18px;
        padding: 12px 14px;
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.8);
        font-size: 0.95rem;
      }
      #participants {
        margin-top: 18px;
        padding-left: 20px;
      }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/livekit-client@2.15.6/dist/livekit-client.umd.min.js"></script>
  </head>
  <body>
    <main>
      <div class="card">
        <h1>Caller Simulator</h1>
        <p>Use this page instead of Twilio to act like the incoming caller. It joins the LiveKit room, publishes your microphone, and lets the trusted leg hear translated audio without PSTN charges.</p>
        <form id="join-form">
          <label>
            Room
            <input id="room" name="room" value="call-main" />
          </label>
          <label>
            Identity
            <input id="identity" name="identity" value="web-caller" />
          </label>
          <label>
            Name
            <input id="name" name="name" value="Web Caller" />
          </label>
          <div class="actions">
            <button type="submit">Join As Caller</button>
            <button type="button" data-leave>Leave</button>
          </div>
        </form>
        <div id="status">Idle.</div>
        <ul id="participants"></ul>
      </div>
    </main>
    <script>
      const statusEl = document.getElementById("status");
      const participantsEl = document.getElementById("participants");
      const form = document.getElementById("join-form");
      const leaveButton = document.querySelector("[data-leave]");
      let room;

      function setStatus(message) {
        statusEl.textContent = message;
      }

      function renderParticipants() {
        if (!room) {
          participantsEl.innerHTML = "";
          return;
        }
        const names = [room.localParticipant.identity, ...[...room.remoteParticipants.values()].map((participant) => participant.identity)];
        participantsEl.innerHTML = names.map((name) => `<li>${name}</li>`).join("");
      }

      async function leaveRoom() {
        if (room) {
          await room.disconnect();
          room = null;
        }
        setStatus("Disconnected.");
        renderParticipants();
      }

      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        await leaveRoom();
        setStatus("Requesting LiveKit token...");

        const payload = {
          room_name: document.getElementById("room").value,
          identity: document.getElementById("identity").value,
          name: document.getElementById("name").value,
        };
        const response = await fetch("/caller/credentials", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const credentials = await response.json();
        room = new LivekitClient.Room({
          adaptiveStream: true,
          dynacast: true,
        });
        room.on(LivekitClient.RoomEvent.ParticipantConnected, renderParticipants);
        room.on(LivekitClient.RoomEvent.ParticipantDisconnected, renderParticipants);
        room.on(LivekitClient.RoomEvent.Disconnected, () => {
          setStatus("Disconnected.");
          renderParticipants();
        });

        await room.connect(credentials.serverUrl, credentials.participantToken);
        await room.localParticipant.enableCameraAndMicrophone(false, true);
        renderParticipants();
        setStatus(`Connected to ${credentials.roomName} as ${credentials.participantIdentity}. Mic is live.`);
      });

      leaveButton.addEventListener("click", leaveRoom);
    </script>
  </body>
</html>"""


@app.post("/bot/start")
async def start_bot(request: BotStartRequest) -> dict[str, object]:
    config = load_runtime_cloud_config()
    if not config.livekit_api_key or not config.livekit_api_secret:
        raise HTTPException(status_code=503, detail="LiveKit credentials not configured")

    status = await app.state.bot_manager.start(
        room_name=request.room_name,
        trusted_identity=request.trusted_identity,
    )
    return {
        "room_name": status.room_name,
        "trusted_identity": status.trusted_identity,
        "running": status.running,
    }


@app.get("/bot/status")
def bot_status() -> dict[str, object]:
    return {"bots": app.state.bot_manager.status()}
