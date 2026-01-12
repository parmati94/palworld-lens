"""Application startup and lifecycle management"""
import asyncio
import tempfile
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from backend.common.logging_config import get_logger
from backend.common.config import config, Config
from backend.parser import parser
from backend.utils.watcher import SaveWatcher
from backend.utils.remote_loader import RemoteSaveLoader, RemoteSavePoller

logger = get_logger(__name__)

# Global state
watcher: Optional[SaveWatcher] = None
remote_loader: Optional[RemoteSaveLoader] = None
remote_poller: Optional[RemoteSavePoller] = None
sse_clients: list[asyncio.Queue] = []
watch_active: bool = False
remote_mode: bool = False


async def reload_and_notify(skip_if_no_clients: bool = False):
    """Shared helper to reload save and notify SSE clients
    
    Args:
        skip_if_no_clients: If True, skip reload when no SSE clients connected
    """
    if skip_if_no_clients and not sse_clients:
        logger.debug("🔇 Skipping reload - no active clients")
        return False
    
    logger.info("🔄 Reloading save...")
    if parser.reload():
        logger.info("✅ Save reloaded successfully")
        # Notify all SSE clients
        for client_queue in sse_clients:
            try:
                client_queue.put_nowait({"event": "reload"})
            except asyncio.QueueFull:
                pass  # Skip if queue is full
        return True
    else:
        logger.error("❌ Failed to reload save")
        return False


@asynccontextmanager
async def lifespan(app):
    """Application lifecycle events - startup and shutdown"""
    global watcher, remote_loader, remote_poller, watch_active, remote_mode
    
    logger.info("🚀 Starting Palworld Lens")
    
    # Check if remote save mode is enabled
    if config.REMOTE_SAVE_ENABLED:
        logger.info("🌐 Remote save mode enabled")
        remote_mode = True
        
        # Validate remote configuration
        if not all([config.REMOTE_HOST, config.REMOTE_USER, config.REMOTE_PASSWORD, config.REMOTE_PATH]):
            logger.error("❌ Remote save configuration incomplete! Required: REMOTE_HOST, REMOTE_USER, REMOTE_PASSWORD, REMOTE_PATH")
            logger.warning("⚠️  Falling back to local mode")
            remote_mode = False
        else:
            protocol = config.get_remote_protocol()
            logger.info(f"📡 Remote config: {protocol.upper()}://{config.REMOTE_USER}@{config.REMOTE_HOST}:{config.REMOTE_PORT}{config.REMOTE_PATH}")
            logger.info(f"⏰ Poll interval: {config.REMOTE_POLL_INTERVAL}s")
            
            # Create temporary directory for downloaded saves
            temp_dir = Path(tempfile.gettempdir()) / "palworld-lens-remote"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Override save mount path to use temp directory (update class variable)
            Config.SAVE_MOUNT_PATH = str(temp_dir)
            logger.info(f"📂 Using temporary directory: {temp_dir}")
            logger.warning(f"⚠️  Ignoring any bind-mounted volumes - remote mode active")
            
            # Initialize remote loader
            remote_loader = RemoteSaveLoader(
                protocol=protocol,
                host=config.REMOTE_HOST,
                port=config.REMOTE_PORT,
                username=config.REMOTE_USER,
                password=config.REMOTE_PASSWORD,
                remote_path=config.REMOTE_PATH,
                local_temp_dir=temp_dir,
                key_path=config.REMOTE_KEY_PATH,
                key_passphrase=config.REMOTE_KEY_PASSPHRASE
            )
            
            # Try initial download
            logger.info("⬇️  Performing initial save download...")
            if remote_loader.download():
                logger.info("✅ Initial download successful")
                if parser.load():
                    logger.info("✅ Save loaded successfully")
                else:
                    logger.warning("⚠️  Failed to load downloaded save")
            else:
                logger.error("❌ Initial download failed")
            
            # Start remote poller
            async def on_remote_save_change():
                """Callback when remote save is downloaded"""
                # In remote mode, always reload (user explicitly enabled polling)
                await reload_and_notify(skip_if_no_clients=False)
            
            # Only start polling if interval is configured (> 0)
            if config.REMOTE_POLL_INTERVAL > 0:
                loop = asyncio.get_event_loop()
                remote_poller = RemoteSavePoller(
                    remote_loader=remote_loader,
                    poll_interval=config.REMOTE_POLL_INTERVAL,
                    on_change_callback=on_remote_save_change,
                    loop=loop
                )
                
                if remote_poller.start():
                    watch_active = True
                    logger.info("✅ Remote polling started (auto-watch enabled)")
            else:
                logger.info("⏸️  Remote polling disabled (REMOTE_POLL_INTERVAL=0) - manual reload only")
                watch_active = False
    
    # Local mode (original behavior)
    if not remote_mode:
        logger.info(f"📂 Save mount path: {config.SAVE_MOUNT_PATH}")
        
        # Try to load save on startup
        if config.get_level_sav_path():
            logger.info("🔍 Found save files, attempting auto-load...")
            if parser.load():
                logger.info("✅ Save loaded successfully on startup")
            else:
                logger.warning("⚠️  Failed to auto-load save")
        else:
            logger.warning("⚠️  No save files found in mounted directory")
        
        # Start file watcher if enabled
        if config.ENABLE_AUTO_WATCH:
            async def on_save_change():
                """Callback when save file changes"""
                # Only reload if there are active SSE clients
                await reload_and_notify(skip_if_no_clients=True)
            
            # Get the current event loop to pass to watcher
            loop = asyncio.get_event_loop()
            watcher = SaveWatcher(config.get_save_path(), on_save_change, loop)
            if watcher.start():
                watch_active = True
        else:
            logger.info("⏸️  Auto-watch disabled (ENABLE_AUTO_WATCH=false)")
    
    yield
    
    # Cleanup
    if watcher:
        watcher.stop()
    
    if remote_poller:
        await remote_poller.stop()
    
    logger.info("👋 Shutting down Palworld Lens")
