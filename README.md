# Palworld Save Viewer

A lightweight, read-only viewer for Palworld save files. Built to be mobile-friendly and containerized.

## ✨ Features

- 📱 **Mobile-First Design** - Responsive UI built with Tailwind CSS
- 🔄 **Auto-Load & Reload** - Automatically loads saves on startup with manual reload button
- 👥 **Player Viewer** - View all players with stats, hunger, and SAN levels
- 🦄 **Pal Viewer** - Browse all pals with detailed stats
- 🏠 **Base Pal Monitor** - Track pals at your bases with hunger/SAN warnings
- 🏛️ **Guild Information** - View guilds and their members
- 🐳 **Containerized** - Single Docker container with nginx + FastAPI
- 🚫 **Read-Only** - No editing functionality, just viewing

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Palworld save files

### Setup

1. **Clone or navigate to the directory:**
   ```bash
   cd /path/to/palworld-server-viewer
   ```

2. **Configure your save path in `docker-compose.yml`:**
   ```yaml
   volumes:
     - /path/to/your/SaveGames/0/WORLD-ID:/app/saves:ro
   ```
   
   Example:
   ```yaml
   volumes:
     - /home/paul/.gamedata/palworld/Pal/Saved/SaveGames/0/E78D2AA4834049EF90A165AE9CBB433D:/app/saves:ro
   ```

3. **Start the viewer:**
   ```bash
   chmod +x start.sh
   ./start.sh
   ```
   
   Or manually:
   ```bash
   docker-compose up -d --build
   ```

4. **Access the viewer:**
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
  - PORT=8000                          # Backend port (internal)
  - AUTO_RELOAD_INTERVAL=30            # Auto-reload interval in seconds
```

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

### Guilds Tab
- Guild information
- Member lists

## 🛠️ Development

### Local Development (without Docker)

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   export SAVE_MOUNT_PATH=/path/to/saves
   ```

3. **Run the backend:**
   ```bash
   python -m uvicorn backend.main:app --reload --port 8000
   ```

4. **Serve frontend:**
   Open `frontend/index.html` in a browser, or use a simple HTTP server:
   ```bash
   cd frontend
   python -m http.server 8080
   ```

## 🐛 Troubleshooting

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
- `GET /api/health` - Health check

## 🙏 Credits

This viewer uses the [palworld-save-tools](https://github.com/oMaN-Rod/palworld-save-tools) library for parsing save files.

Based on concepts from [palworld-save-pal](https://github.com/oMaN-Rod/palworld-save-pal) but streamlined for read-only viewing.

## 📝 License

MIT License - Feel free to use and modify!

## 🔮 Future Ideas

- WebSocket support for live updates
- Export data to JSON/CSV
- Statistics and graphs
- Pal breeding calculator
- Map visualization

---

**Note:** This is a read-only viewer. It does not modify your save files in any way.
