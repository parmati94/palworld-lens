# Palworld Lens

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
   wget https://raw.githubusercontent.com/parmati94/palworld-lens/main/docker-compose.yml
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

3. **Start the application:**
   ```bash
   docker-compose up -d
   ```
   The image will be automatically pulled from Docker Hub on first run.

4. **Access the application:**
   Open your browser to `http://localhost:5175`

### Option 2: Building from Source

1. **Clone the repository:**
   ```bash
   git clone https://github.com/parmati94/palworld-lens.git
   cd palworld-lens
   ```

2. **Build the Docker image:**
   ```bash
   docker build -t palworld-lens:local .
   ```

3. **Configure your save path in `docker-compose.yml`:**
   ```yaml
   volumes:
     - /path/to/your/SaveGames/0/WORLD-ID:/app/saves:ro
   ```
   
   And update the image line to use your local build:
   ```yaml
   image: palworld-lens:local
   ```

4. **Start the application:**
   ```bash
   docker-compose up -d
   ```

5. **Access the application:**
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
  - TZ=America/New_York                # Your local timezone (e.g., America/Los_Angeles, Europe/London, Asia/Tokyo, etc.)
  
  # Authentication (optional - default is disabled)
  - ENABLE_LOGIN=false                 # Set to true to require login
  - USERNAME=admin                     # Login username (only used if ENABLE_LOGIN=true)
  - PASSWORD=changeme                  # Login password (only used if ENABLE_LOGIN=true)
  - SESSION_SECRET=your-secret-here    # Secret key for session tokens (generate a random string)
```

**Auto-Watch**: When enabled, the viewer automatically detects save file changes and pushes updates to the browser in real-time via Server-Sent Events (SSE). The toggle can be controlled from the frontend UI.

**Authentication**: When `ENABLE_LOGIN=true`, users must login before accessing the application. This is a simple single-user authentication system. Sessions last 7 days.

## 📊 Viewing Options

### Overview Tab
- World information
- Player count, pal count, guild count
- Save file details

### Players Tab
- All players with stats
- HP, hunger, and SAN levels
- Guild membership

### Pals Tab
- Searchable list of all pals
- Level, stats, owner information
- Lucky/Shiny and Boss indicators

### Bases Tab
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
- **Image tags**: Dev builds tag as `palworld-lens:dev`, production as `palworld-lens:latest`
- **Auto-watch disabled**: Set to `false` in dev to allow instant uvicorn reloads (SSE connections prevent fast reloads)
- **Frontend changes**: Instantly reflected - just refresh your browser
- **Backend changes**: Auto-reloaded by uvicorn within 1-2 seconds

## 📜 API Endpoints

### Core Endpoints
- `GET /api/health` - Health check for container monitoring
- `GET /api/info` - Save file information and metadata
- `POST /api/reload` - Manually reload save files
- `GET /api/reload` - Same as POST (for convenience)

### Data Endpoints
- `GET /api/players` - List all players with stats
- `GET /api/guilds` - List all guilds
- `GET /api/pals` - List all pals (non-player characters)

### Auto-Watch Endpoints
- `GET /api/watch` - Server-Sent Events stream for real-time updates
- `GET /api/watch/status` - Check if auto-watch is currently active
- `POST /api/watch/start` - Start automatic file watcher
- `POST /api/watch/stop` - Stop automatic file watcher

### Authentication Endpoints
- `GET /api/auth/status` - Check if authentication is enabled and if user is logged in
- `POST /api/auth/login` - Login with username and password
- `POST /api/auth/logout` - Logout and clear session

### Debug Endpoints
Various debug endpoints available for development:
- `/api/debug/world-keys` - Inspect world data structure
- `/api/debug/base-camps` - View base camp data
- `/api/debug/char-containers` - Character container inspection
- `/api/debug/player-mapping` - Player UID mappings
- And more...

## 🙏 Credits

This application uses the [palworld-save-tools](https://github.com/oMaN-Rod/palworld-save-tools) library for parsing save files.

Based on concepts from [palworld-save-pal](https://github.com/oMaN-Rod/palworld-save-pal) but streamlined for read-only viewing.

## 📝 License

MIT License - Feel free to use and modify!

**Note:** This is a read-only viewer. It does not modify your save files in any way.

---

## 📁 Project Structure

```
palworld-lens/
│
├── backend/                        # Python FastAPI backend
│   ├── main.py                    # FastAPI app, API endpoints, SSE handling
│   │
│   ├── common/                    # Shared configuration and utilities
│   │   ├── config.py             # Environment configuration
│   │   ├── constants.py          # App-wide constants
│   │   └── logging_config.py     # Colored logging setup
│   │
│   ├── models/                    # Pydantic data models
│   │   └── models.py             # PalInfo, PlayerInfo, GuildInfo schemas
│   │
│   ├── parser/                    # Save file parsing module
│   │   ├── __init__.py           # SaveFileParser class (main orchestrator)
│   │   │
│   │   ├── builders/             # Build model objects from raw data
│   │   │   ├── pals.py          # Build PalInfo from character data
│   │   │   ├── players.py       # Build PlayerInfo from player data
│   │   │   └── guilds.py        # Build GuildInfo from guild data
│   │   │
│   │   ├── extractors/          # Extract raw data from save structures
│   │   │   ├── characters.py    # Get character save parameter map
│   │   │   ├── guilds.py        # Get guild group data
│   │   │   └── bases.py         # Get base camp assignments
│   │   │
│   │   ├── loader/              # Load game data and save files
│   │   │   ├── data_loader.py   # Load JSON game data (names, stats, skills)
│   │   │   └── gvas_handler.py  # GVAS file decompression and parsing
│   │   │
│   │   ├── schemas/             # YAML field extraction schemas
│   │   │   ├── pals.yaml        # Pal character field definitions
│   │   │   ├── players.yaml     # Player character field definitions
│   │   │   └── guilds.yaml      # Guild field definitions
│   │   │
│   │   └── utils/               # Parser utility functions
│   │       ├── schema_loader.py # YAML schema parser and field extractor
│   │       ├── helpers.py       # Basic value extraction helpers
│   │       ├── mappers.py       # Map IDs to display names
│   │       ├── stats.py         # Calculate pal/player stats
│   │       └── relationships.py # Build pal-to-owner mappings
│   │
│   └── utils/                    # Backend utilities
│       └── watcher.py            # File system watcher for auto-reload
│
├── data/                          # Game data and localization
│
├── frontend/                      # Static web frontend
│   ├── index.html                # Main SPA page
│   ├── js/
│   │   ├── app.js               # Main app logic, API calls, rendering
│   │   └── utils.js             # Utility functions (formatting, etc.)
│   └── img/
│       └── favicon/             # App icons
│
├── supervisor/                    # Supervisor config for multi-process container
│   ├── supervisord.conf          # Production config (backend + nginx)
│   └── supervisord.dev.conf      # Dev config (hot-reload enabled)
│
├── docker-compose.yml             # Production compose file
├── docker-compose.dev.yml         # Development compose file (hot-reload)
├── Dockerfile                     # Multi-stage container build
├── nginx.conf                     # Nginx reverse proxy config (internal container routing)
├── requirements.txt               # Python dependencies
```
