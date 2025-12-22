# Palworld Server Viewer

A lightweight, read-only viewer for Palworld save files. Built to be mobile-friendly and containerized.

## ✨ Features

- 📱 **Mobile-First Design** - Responsive UI built with Tailwind CSS
- 🔄 **Auto-Load & Reload** - Automatically loads saves on startup with manual reload button
-   **Real-Time Updates** - Auto-watch save files for live updates (toggleable)
-  👥 **Player Viewer** - View all players with stats, hunger, and SAN levels
- 🦄 **Pal Viewer** - Browse all pals with detailed stats
- 🏠 **Base Pal Monitor** - Track pals at your bases with hunger/SAN warnings
- 🏛️ **Guild Information** - View guilds and their members
- 🐳 **Containerized** - Single Docker container with nginx + FastAPI
- 🚫 **Read-Only** - No editing functionality, just viewing

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Palworld save files

### Option 1: Using Pre-built Image (Recommended)

1. **Download the docker-compose.yml:**
   ```bash
   wget https://raw.githubusercontent.com/parmati94/palworld-server-viewer/main/docker-compose.yml
   ```

2. **Configure your save path in `docker-compose.yml`:**
   ```yaml
   volumes:
     - /path/to/your/SaveGames/0/WORLD-ID:/app/saves:ro
   ```
   
   Example:
   ```yaml
   volumes:
     - /home/<user>/.gamedata/palworld/Pal/Saved/SaveGames/0/E78D2AA4834049EF90A165AE9CBB433D:/app/saves:ro
   ```

3. **Start the viewer:**
   ```bash
   docker-compose up -d
   ```
   The image will be automatically pulled from Docker Hub on first run.

4. **Access the viewer:**
   Open your browser to `http://localhost:5175`

### Option 2: Building from Source

1. **Clone the repository:**
   ```bash
   git clone https://github.com/parmati94/palworld-server-viewer.git
   cd palworld-server-viewer
   ```

2. **Build the Docker image:**
   ```bash
   docker build -t palworld-server-viewer:local .
   ```

3. **Configure your save path in `docker-compose.yml`:**
   ```yaml
   volumes:
     - /path/to/your/SaveGames/0/WORLD-ID:/app/saves:ro
   ```
   
   And update the image line to use your local build:
   ```yaml
   image: palworld-server-viewer:local
   ```

4. **Start the viewer:**
   ```bash
   docker-compose up -d
   ```

5. **Access the viewer:**
   Open your browser to `http://localhost:5175`

## 📂 Directory Structure Expected

Your mounted save directory should contain:
```
/app/saves/
├── Level.sav          (required)
├── LevelMeta.sav      (optional)
└── Players/           (required)
    ├── {player-uuid}.sav
    └── ...
```

## 🔧 Configuration

Edit `docker-compose.yml` environment variables:

```yaml
environment:
  - SAVE_MOUNT_PATH=/app/saves        # Path to mounted saves
  - ENABLE_AUTO_WATCH=true             # Enable automatic file watching for live updates on backend.  Can still be toggled on/off on UI as long as this is set to true.
  - LOG_LEVEL=INFO                     # Logging level: DEBUG, INFO, WARNING, ERROR
```

**Auto-Watch**: When enabled, the viewer automatically detects save file changes and pushes updates to the browser in real-time via Server-Sent Events (SSE). The toggle can be controlled from the frontend UI.

## 📊 Viewing Options

### Overview Tab
- World information
- Player count, pal count, guild count
- Save file details

### Players Tab
- All players with stats
- HP, hunger, and SAN levels
- Guild membership

### All Pals Tab
- Searchable list of all pals
- Level, stats, owner information
- Lucky/Shiny and Boss indicators

### Base Pals Tab
- Pals organized by guild/base
- **Hunger and SAN monitoring** (color-coded warnings)
- Health bars for each pal



## 🛠️ Development

For development, use the provided `docker-compose.dev.yml` which builds with `DEV_MODE=true` for hot-reloading:

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up --build

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Stop
docker-compose -f docker-compose.dev.yml down
```

**How it works:**
- **Build arg `DEV_MODE=true`**: Enables uvicorn's `--reload` flag for backend hot-reloading
- **Image tags**: Dev builds tag as `palworld-server-viewer:dev`, production as `palworld-server-viewer:latest`
- **Auto-watch disabled**: Set to `false` in dev to allow instant uvicorn reloads (SSE connections prevent fast reloads)
- **Frontend changes**: Instantly reflected - just refresh your browser
- **Backend changes**: Auto-reloaded by uvicorn within 1-2 seconds

No container rebuilds needed for code changes during development!

## 🐛 Troubleshooting

### Container Management
- **Stop the viewer:** `docker-compose down`
- **View logs:** `docker-compose logs -f`
- **Rebuild:** `docker-compose up -d --build`

### Save not loading?
- Check that `Level.sav` exists in the mounted directory
- Verify the path in `docker-compose.yml` is correct
- Check logs: `docker-compose logs -f`

### Container won't start?
- Ensure port 5175 is not already in use
- Check Docker logs for errors
- Verify the save directory has read permissions

### Data not updating?
- Click the green "Reload Save" button
- Check the auto-reload interval setting
- Verify the save files are being updated

## 📜 API Endpoints

- `GET /api/info` - Save file information
- `GET /api/players` - List all players
- `GET /api/guilds` - List all guilds
- `GET /api/pals` - List all pals
- `GET /api/base-pals` - Pals organized by base
- `POST /api/reload` - Reload save files
- `GET /api/watch` - Server-Sent Events stream for real-time updates
- `GET /api/watch/status` - Check auto-watch status
- `POST /api/watch/start` - Start file watcher
- `POST /api/watch/stop` - Stop file watcher
- `GET /api/health` - Health check

## 🙏 Credits

This viewer uses the [palworld-save-tools](https://github.com/oMaN-Rod/palworld-save-tools) library for parsing save files.

Based on concepts from [palworld-save-pal](https://github.com/oMaN-Rod/palworld-save-pal) but streamlined for read-only viewing.

## 📝 License

MIT License - Feel free to use and modify!

## 🔮 Future Ideas

- Export data to JSON/CSV
- Statistics and graphs
- Pal breeding calculator
- Map visualization
- Historical data tracking

---

**Note:** This is a read-only viewer. It does not modify your save files in any way.
