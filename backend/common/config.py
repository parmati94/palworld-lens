"""Configuration management"""
import os
from pathlib import Path
from typing import Optional, Literal

class Config:
    """Application configuration"""
    
    # Save file paths
    SAVE_MOUNT_PATH: str = os.getenv("SAVE_MOUNT_PATH", "/app/saves")
    
    # Auto-watch settings
    ENABLE_AUTO_WATCH: bool = os.getenv("ENABLE_AUTO_WATCH", "true").lower() in ("true", "1", "yes")
    
    # Remote save settings
    REMOTE_SAVE_ENABLED: bool = os.getenv("REMOTE_SAVE_ENABLED", "false").lower() in ("true", "1", "yes")
    REMOTE_HOST: str = os.getenv("REMOTE_HOST", "")
    REMOTE_PORT: int = int(os.getenv("REMOTE_PORT", "22"))
    REMOTE_USER: str = os.getenv("REMOTE_USER", "")
    REMOTE_PASSWORD: str = os.getenv("REMOTE_PASSWORD", "")
    REMOTE_KEY_PATH: str = os.getenv("REMOTE_KEY_PATH", "/app/.ssh/id_rsa")  # SSH private key path
    REMOTE_KEY_PASSPHRASE: str = os.getenv("REMOTE_KEY_PASSPHRASE", "")  # Optional passphrase for encrypted keys
    REMOTE_PATH: str = os.getenv("REMOTE_PATH", "")
    REMOTE_POLL_INTERVAL: int = int(os.getenv("REMOTE_POLL_INTERVAL", "60"))  # seconds
    
    @classmethod
    def get_remote_protocol(cls) -> Literal["sftp", "ftp"]:
        """Determine protocol from port: 22=SFTP, 21=FTP, default=SFTP"""
        return "ftp" if cls.REMOTE_PORT == 21 else "sftp"
    
    # Authentication settings
    ENABLE_LOGIN: bool = os.getenv("ENABLE_LOGIN", "false").lower() in ("true", "1", "yes")
    USERNAME: str = os.getenv("USERNAME", "admin")
    PASSWORD: str = os.getenv("PASSWORD", "admin")
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "change-me-in-production-please")
    
    # RCON settings
    RCON_HOST: str = os.getenv("RCON_HOST", "")
    RCON_PORT: int = int(os.getenv("RCON_PORT", "8212"))
    RCON_PASSWORD: str = os.getenv("RCON_PASSWORD", "")
    
    # Data paths
    DATA_PATH: Path = Path(__file__).parent.parent.parent / "data"
    
    @classmethod
    def get_save_path(cls) -> Path:
        """Get the path to mounted save directory"""
        return Path(cls.SAVE_MOUNT_PATH)
    
    @classmethod
    def get_level_sav_path(cls) -> Optional[Path]:
        """Get path to Level.sav file"""
        save_path = cls.get_save_path()
        level_sav = save_path / "Level.sav"
        if level_sav.exists():
            return level_sav
        return None
    
    @classmethod
    def get_players_dir(cls) -> Optional[Path]:
        """Get path to Players directory"""
        save_path = cls.get_save_path()
        players_dir = save_path / "Players"
        if players_dir.exists() and players_dir.is_dir():
            return players_dir
        return None

config = Config()
