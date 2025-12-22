"""File watcher for Palworld save files"""
import asyncio
from pathlib import Path
from typing import Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from backend.logging_config import get_logger

logger = get_logger(__name__)


class SaveFileHandler(FileSystemEventHandler):
    """Handles save file modification events"""
    
    def __init__(self, callback: Callable, watch_path: Path, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.callback = callback
        self.watch_path = watch_path
        self.loop = loop
        self._debounce_task: Optional[asyncio.Task] = None
        self._debounce_delay = 1.0  # Wait 1 second after last change
        self._start_time = None  # Track when watcher started
        
    def on_modified(self, event):
        """Called when a file is modified"""
        if event.is_directory:
            return
        
        # Ignore events during startup period (first 3 seconds)
        import time
        if self._start_time and (time.time() - self._start_time) < 3.0:
            return
            
        # Check if it's Level.sav or a Player file
        event_path = Path(event.src_path)
        if event_path.name == "Level.sav" or event_path.parent.name == "Players":
            logger.debug(f"📝 Detected change in {event_path.name}")
            
            # Cancel existing debounce task
            if self._debounce_task and not self._debounce_task.done():
                self._debounce_task.cancel()
            
            # Schedule task on the main event loop
            self._debounce_task = asyncio.run_coroutine_threadsafe(
                self._debounced_callback(), self.loop
            )
    
    async def _debounced_callback(self):
        """Debounced callback to avoid multiple rapid reloads"""
        try:
            await asyncio.sleep(self._debounce_delay)
            await self.callback()
        except asyncio.CancelledError:
            pass


class SaveWatcher:
    """Watches Palworld save directory for changes"""
    
    def __init__(self, save_path: Path, on_change_callback: Callable, loop: asyncio.AbstractEventLoop):
        self.save_path = save_path
        self.on_change_callback = on_change_callback
        self.loop = loop
        self.observer: Optional[Observer] = None
        self.handler: Optional[SaveFileHandler] = None
        
    def start(self):
        """Start watching the save directory"""
        if not self.save_path.exists():
            logger.warning(f"⚠️  Save path does not exist: {self.save_path}")
            return False
            
        logger.info(f"👀 Starting save file watcher on {self.save_path}")
        
        import time
        self.handler = SaveFileHandler(self.on_change_callback, self.save_path, self.loop)
        self.handler._start_time = time.time()  # Mark start time
        self.observer = Observer()
        self.observer.schedule(self.handler, str(self.save_path), recursive=True)
        self.observer.start()
        
        logger.info("✅ Save file watcher started")
        return True
    
    def stop(self):
        """Stop watching the save directory"""
        if self.observer:
            logger.info("🛑 Stopping save file watcher")
            self.observer.stop()
            self.observer.join()
            self.observer = None
            self.handler = None
