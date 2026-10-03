# Palworld Lens

A lightweight, read-only viewer for Palworld save files. Built to be mobile-friendly and containerized.

*Unofficial fan project, not affiliated with or endorsed by Pocketpair.*

<div align="center">
  <img src=".github/screenshots/overview.png" alt="Overview tab" width="32%"/>
  <img src=".github/screenshots/players.png" alt="Players tab" width="32%"/>
  <img src=".github/screenshots/pals.png" alt="Pals tab" width="32%"/>
  <br/>
  <img src=".github/screenshots/bases.png" alt="Bases tab" width="32%"/>
  <img src=".github/screenshots/activity.png" alt="Base activity" width="32%"/>
  <img src=".github/screenshots/map.png" alt="Map tab" width="32%"/>
  <br/>
  <img src=".github/screenshots/paldeck.png" alt="Paldeck as a player's capture bonus tracker" width="32%"/>
  <img src=".github/screenshots/breeding.png" alt="Breeding calculator" width="32%"/>
  <img src=".github/screenshots/workers.png" alt="Best workers" width="32%"/>
</div>

## ✨ Features

- 👥 **Players** - Every player with level, HP, hunger, SAN, guild, party, and who is online or when they were last seen; open one for their inventory, stats and records
- 🦄 **Pals** - Every pal on the server with stats, skills, work suitabilities and owner. One search box; element, work, passive and owner filters are added as chips
- 📖 **Paldeck** - Every species the game numbers: elements, work levels, partner skill, where it spawns (with a jump to the map), how you get the ones nothing spawns (meteor events, raid eggs, the World Tree bosses), what it drops, what it learns, how to breed it, and who on the server has one. Pick a player and the deck becomes their capture bonus tracker: what the next catch pays and which species are still worth catching
- 🏠 **Bases** - Guilds and their bases with every pal's status, hunger and SAN, the food bowls and storage chests (searchable across a guild), and what the base is doing as of the last save: machines with their order and progress, crops, eggs, stations and ranches with who is on them, expeditions and lab research
- 🗺️ **Map** - The world map with bases and players live from the save, plus the game's landmarks as toggleable layers: syndicate towers, watchtowers, fast travel statues, dungeons and alpha pals. Search a species and every wild spawner that rolls it lights up, sized to its real radius, with level range and night-only zones
- 🧬 **Breeding** - What two pals make, every pair that makes a pal, and which of *your* pals fit (with the passives you want). Can't breed it yet? The route planner draws the shortest chain from what you own
- ⭐ **Best workers** - The best pal for a job: who on the server already has it, what you could catch at your level, and what you could breed from your own pals
- 🔄 **Live** - Loads on startup, reloads on demand, and can watch the save directory and push updates to the browser as the game autosaves
- 🌐 **Remote saves** - Poll a remote SFTP/FTP server for the save instead of mounting it
- 🖥️ **Server Info** - Online players, uptime, performance and settings over RCON (optional)
- 🐳 **Containerized** - Single Docker container with nginx + FastAPI. Read-only: it never writes to your save

## 🚀 Quick Start

1. Download the compose file:
   ```bash
   wget https://raw.githubusercontent.com/parmati94/palworld-lens/main/docker-compose.yml
   ```

2. Point it at your world's save directory (the folder holding `Level.sav` and `Players/`):
   ```yaml
   volumes:
     - /path/to/your/SaveGames/0/WORLD-ID:/app/saves:ro
   ```

3. Start it, then open `http://localhost:5175`:
   ```bash
   docker-compose up -d
   ```

To build from source instead, clone the repo, `docker build -t palworld-lens:local .`, and set `image: palworld-lens:local` in the compose file.

## 🔧 Configuration

Everything is an environment variable in `docker-compose.yml`:

```yaml
environment:
  - SAVE_MOUNT_PATH=/app/saves        # Path to mounted saves (local mode only)
  - APP_STATE_PATH=/app/state         # Writable dir for app-owned state (custom base names, last seen); mount a volume there or renaming stays off
  - ENABLE_AUTO_WATCH=true             # Watch the save directory and push updates to the browser; can still be toggled off in the UI
  - LOG_LEVEL=INFO                     # DEBUG, INFO, WARNING, ERROR
  - TZ=America/New_York                # Your local timezone

  # Authentication (optional - default is disabled)
  - ENABLE_LOGIN=false                 # Set to true to require login (single user, sessions last 7 days)
  - USERNAME=admin
  - PASSWORD=changeme
  - SESSION_SECRET=your-secret-here    # Secret key for session tokens (generate a random string)

  # Server Info over RCON (optional). Also turns on online status and "last seen": the backend
  # asks the server's REST API for the player list once a minute and keeps one time per player
  # in APP_STATE_PATH/presence.json
  - RCON_HOST=your-palworld-server-ip
  - RCON_PORT=8212
  - RCON_PASSWORD=your_admin_password

  # Remote save loading (optional - replaces the local mount and ENABLE_AUTO_WATCH)
  - REMOTE_SAVE_ENABLED=false
  - REMOTE_HOST=your-server-ip
  - REMOTE_PORT=22                     # 22 for SFTP, 21 for FTP (protocol follows the port)
  - REMOTE_USER=username
  - REMOTE_PASSWORD=password           # Optional if using an SSH key
  - REMOTE_KEY_PATH=/app/.ssh/id_rsa   # SFTP: mount your key here (tried before the password)
  - REMOTE_KEY_PASSPHRASE=             # For encrypted keys
  - REMOTE_PATH=/path/to/saves
  - REMOTE_POLL_INTERVAL=60            # Seconds between polls (0 disables toggling)
```

For SFTP with a key, also mount it: `- ~/.ssh/id_rsa:/app/.ssh/id_rsa:ro`.

### 🔒 Security

The login is a single user set by environment variables, meant for a home network. Keep the app on your LAN, or put it behind a VPN or a reverse proxy with its own authentication, rather than forwarding the port to the internet. Even with login off it never writes to your save, but it does show every player's position, inventory and base.

## 📜 API

Everything the UI shows comes from `/api/*`, served from a snapshot built once per save load. The main ones:

- `GET /api/players`, `/api/guilds`, `/api/pals`, `/api/base-containers`, `/api/activity` - the save as the tabs show it
- `GET /api/paldeck`, `/api/paldeck/{species_id}` - every species, and one in full
- `GET /api/map-objects`, `/api/spawns` - landmarks and wild spawn zones for the map
- `GET /api/breeding/child|parents|partners|route`, `/api/workers` - the Tools tab
- `GET /api/watch` - Server-Sent Events stream of save changes
- `GET /api/health`, `/api/info`, `POST /api/reload`

## 🛠️ Development

`docker-compose.dev.yml` builds with `DEV_MODE=true`, which gives the backend uvicorn's `--reload` and turns auto-watch off (SSE connections keep uvicorn from reloading quickly):

```bash
docker-compose -f docker-compose.dev.yml up --build
```

Backend changes reload within a couple of seconds. Frontend changes need `npm run build` in `frontend/` and a browser refresh. `data/` is bind-mounted read-only, so game data edits show on the next backend reload.

### Tests

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest                       # backend: id resolution, stats, schemas, shipped data
python scripts/datagen/validate.py --skip-tiles  # shipped data ↔ icons ↔ map objects coverage
cd frontend && node --test 'tests/*.test.mjs'    # projection, reference-data lookups, paging
cd frontend && npm run test:e2e                  # smoke tests against a running dev instance
```

The first three run in CI on every pull request (`.github/workflows/ci.yml`).

### Game data

`data/json` is synced from [palworld-save-pal](https://github.com/oMaN-Rod/palworld-save-pal); icons, map tiles, spawn zones and the other pak-derived tables come from the game files. The list of tables the app ships is `backend/common/game_tables.py`, and the app refuses to start if a required one is missing. See [`scripts/datagen/README.md`](scripts/datagen/README.md) for the one-command update.

## 🙏 Credits

Save parsing by [palworld-save-tools](https://github.com/oMaN-Rod/palworld-save-tools); game data and many ideas from [palworld-save-pal](https://github.com/oMaN-Rod/palworld-save-pal).

## 📝 License

The code is [MIT](LICENSE). The game data tables synced from palworld-save-pal are GPL v3, as that project is; [`data/json/NOTICE.md`](data/json/NOTICE.md) lists which files those are.

Palworld and its names, images, icons and map art are © Pocketpair, Inc. This project is free and shared under Pocketpair's [guidelines for derivative works](https://www.pocketpair.jp/guidelines-derivativework).
