# Palworld Lens

Palworld Lens reads your Palworld world save and shows what's going on in it from a browser, phone included: what every pal at every base is doing, who's online, where things spawn, what you can breed. I built it for my own server so I could check on our bases without logging in, and it grew from there.

It only reads the save. It never writes to it.

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

## What's in it

- **Bases** - every pal's hunger and status, storage, and what each base is working on
- **Pals** - every pal on the server, filterable by element, job, passive or owner
- **Players** - who's online, when they were last seen, and their inventory
- **Map** - bases, players and landmarks, and search a pal to see where it spawns
- **Paldeck** - every species, plus a per-player tracker of what's still worth catching
- **Breeding** - what two pals make, and the shortest route to one you don't have
- **Best workers** - the best pal for a job, from what you own, can catch or can breed

It can also update live as the game saves, pull the save over SFTP/FTP, and show server info over RCON.

## Getting started

You need Docker and access to your world's save folder: the one with `Level.sav` and a `Players/` folder in it.

1. Download the compose file:
   ```bash
   wget https://raw.githubusercontent.com/parmati94/palworld-lens/main/docker-compose.yml
   ```

2. Point it at your save folder:
   ```yaml
   volumes:
     - /path/to/your/SaveGames/0/WORLD-ID:/app/saves:ro
   ```

3. Start it and open `http://localhost:5175`:
   ```bash
   docker-compose up -d
   ```

If your server is hosted somewhere you can't mount a folder from, see "Loading the save from another machine" below.

To build it yourself instead, clone the repo, run `docker build -t palworld-lens:local .`, and set `image: palworld-lens:local` in the compose file.

## Settings

Everything is an environment variable in `docker-compose.yml`. Only the save folder is required.

```yaml
environment:
  - SAVE_MOUNT_PATH=/app/saves   # where the save folder is mounted
  - ENABLE_AUTO_WATCH=true       # update the page when the game saves
  - TZ=America/New_York          # your timezone
  - LOG_LEVEL=INFO
```

**App data.** Mount a folder here to keep custom base names and last-seen times.

```yaml
  - APP_STATE_PATH=/app/state
```

**Login.** Off by default.

```yaml
  - ENABLE_LOGIN=true
  - USERNAME=admin
  - PASSWORD=changeme
  - SESSION_SECRET=some-long-random-string
```

**Server info and online status.** Checks the player list once a minute for who's online and last seen.

```yaml
  - RCON_HOST=your-server-ip
  - RCON_PORT=8212
  - RCON_PASSWORD=your-admin-password
```

**Loading the save from another machine.** For hosted servers: downloads the save over SFTP (port 22) or FTP (port 21) instead of reading a mounted folder.

```yaml
  - REMOTE_SAVE_ENABLED=true
  - REMOTE_HOST=your-server-ip
  - REMOTE_PORT=22
  - REMOTE_USER=username
  - REMOTE_PASSWORD=password            # not needed if you use a key
  - REMOTE_KEY_PATH=/app/.ssh/id_rsa    # SFTP key, tried before the password
  - REMOTE_KEY_PASSPHRASE=              # if the key has one
  - REMOTE_PATH=/path/to/saves
  - REMOTE_POLL_INTERVAL=60             # seconds between checks
```

To use an SSH key, mount it too: `- ~/.ssh/id_rsa:/app/.ssh/id_rsa:ro`.

### A note on security

The login is meant for a home network. Keep it on your LAN or behind a VPN or reverse proxy rather than opening the port to the internet; it shows everyone's location, inventory and bases.

## Development

`docker-compose.dev.yml` runs the backend with auto-reload:

```bash
docker-compose -f docker-compose.dev.yml up --build
```

Backend changes reload within a couple of seconds. For frontend changes, run `npm run build` in `frontend/` and refresh. Auto-watch is off in dev mode, because open live-update connections slow down the reloader.

### Tests

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest                       # backend
python scripts/datagen/validate.py --skip-tiles  # game data, icons and map objects line up
cd frontend && node --test 'tests/*.test.mjs'    # frontend logic
cd frontend && npm run test:e2e                  # smoke tests against a running dev instance
```

The first three run in CI on every pull request.

### API

The UI is built entirely on a JSON API under `/api/`, so you can use it for your own scripts too. The main endpoints are `/api/players`, `/api/guilds`, `/api/pals`, `/api/base-containers`, `/api/activity`, `/api/paldeck`, `/api/map-objects` and `/api/spawns`. `/api/watch` is a live stream of save changes.

### Game data

The tables in `data/json` come from [palworld-save-pal](https://github.com/oMaN-Rod/palworld-save-pal). Icons, map tiles, spawn zones and the rest are pulled from the game files. [`scripts/datagen/README.md`](scripts/datagen/README.md) explains how to update them after a patch.

## Thanks

Save parsing comes from [palworld-save-tools](https://github.com/oMaN-Rod/palworld-save-tools). Game data and plenty of ideas come from [palworld-save-pal](https://github.com/oMaN-Rod/palworld-save-pal).

## License

The code is [MIT](LICENSE). The game data tables from palworld-save-pal are GPL v3, like that project; [`data/json/NOTICE.md`](data/json/NOTICE.md) lists which files those are.

Palworld and its names, images, icons and map art are © Pocketpair, Inc. This project is free and follows Pocketpair's [guidelines for derivative works](https://www.pocketpair.jp/guidelines-derivativework).
