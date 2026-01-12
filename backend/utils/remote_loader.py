"""Remote save file loader for SFTP/FTP"""
import asyncio
import ftplib
import tempfile
from pathlib import Path
from typing import Optional, Callable, Literal
import shutil
from backend.common.logging_config import get_logger

logger = get_logger(__name__)

# Import paramiko conditionally (will be available after install)
try:
    import paramiko
    SFTP_AVAILABLE = True
except ImportError:
    SFTP_AVAILABLE = False
    logger.warning("⚠️  paramiko not installed - SFTP support disabled")


class RemoteSaveLoader:
    """Handles downloading save files from remote SFTP/FTP servers"""
    
    def __init__(
        self,
        protocol: Literal["sftp", "ftp"],
        host: str,
        port: int,
        username: str,
        password: str,
        remote_path: str,
        local_temp_dir: Path,
        key_path: Optional[str] = None,
        key_passphrase: Optional[str] = None
    ):
        self.protocol = protocol.lower()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_path = key_path
        self.key_passphrase = key_passphrase
        self.remote_path = remote_path
        self.local_temp_dir = Path(local_temp_dir)
        
        # Ensure local temp directory exists
        self.local_temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine auth method for logging
        auth_method = "key" if key_path and Path(key_path).exists() else "password"
        logger.info(f"🌐 RemoteSaveLoader initialized: {protocol}://{username}@{host}:{port}{remote_path} (auth: {auth_method})")
    
    def _download_via_sftp(self) -> bool:
        """Download save files via SFTP"""
        if not SFTP_AVAILABLE:
            logger.error("❌ SFTP not available - paramiko not installed")
            return False
        
        try:
            logger.debug(f"📡 Connecting to SFTP {self.host}:{self.port}")
            
            # Create SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Prepare connection parameters
            connect_kwargs = {
                'hostname': self.host,
                'port': self.port,
                'username': self.username,
                'timeout': 10
            }
            
            # Try key authentication first if key path provided
            key_path = Path(self.key_path) if self.key_path else None
            if key_path and key_path.exists():
                try:
                    logger.debug(f"🔑 Attempting SSH key authentication: {key_path}")
                    connect_kwargs['key_filename'] = str(key_path)
                    if self.key_passphrase:
                        connect_kwargs['passphrase'] = self.key_passphrase
                    # Don't set password - force key auth
                    ssh.connect(**connect_kwargs)
                    logger.info("✅ Connected using SSH key authentication")
                except (paramiko.AuthenticationException, paramiko.SSHException) as e:
                    logger.warning(f"⚠️ Key authentication failed: {e}")
                    # Fall back to password auth if key fails and password provided
                    if self.password:
                        logger.debug("🔄 Falling back to password authentication")
                        connect_kwargs.pop('key_filename', None)
                        connect_kwargs.pop('passphrase', None)
                        connect_kwargs['password'] = self.password
                        ssh.connect(**connect_kwargs)
                        logger.info("✅ Connected using password authentication (fallback)")
                    else:
                        raise
            elif self.password:
                # Use password authentication
                logger.debug("🔐 Using password authentication")
                connect_kwargs['password'] = self.password
                ssh.connect(**connect_kwargs)
                logger.info("✅ Connected using password authentication")
            else:
                raise ValueError("No authentication method available (no key or password)")
            
            # Open SFTP session
            sftp = ssh.open_sftp()
            
            # Change to remote directory
            try:
                sftp.chdir(self.remote_path)
            except IOError as e:
                logger.error(f"❌ Remote path not found: {self.remote_path}")
                sftp.close()
                ssh.close()
                return False
            
            # Download Level.sav (use relative path after chdir)
            local_level = self.local_temp_dir / "Level.sav"
            
            try:
                sftp.get("Level.sav", str(local_level))
                logger.debug(f"✅ Downloaded Level.sav")
            except FileNotFoundError:
                logger.error(f"❌ Level.sav not found on remote server")
                sftp.close()
                ssh.close()
                return False
            
            # Download LevelMeta.sav (optional)
            local_meta = self.local_temp_dir / "LevelMeta.sav"
            
            try:
                sftp.get("LevelMeta.sav", str(local_meta))
                logger.debug(f"✅ Downloaded LevelMeta.sav")
            except FileNotFoundError:
                logger.debug(f"ℹ️  LevelMeta.sav not found (optional)")
            
            # Download Players directory
            players_local = self.local_temp_dir / "Players"
            
            # Clean and recreate local Players directory
            if players_local.exists():
                shutil.rmtree(players_local)
            players_local.mkdir()
            
            try:
                # List files in remote Players directory (relative to current dir)
                player_files = sftp.listdir("Players")
                
                # Download each player file
                for filename in player_files:
                    if filename.endswith('.sav'):
                        remote_file = f"Players/{filename}"
                        local_file = players_local / filename
                        sftp.get(remote_file, str(local_file))
                        logger.debug(f"✅ Downloaded player: {filename}")
                
                logger.info(f"✅ Downloaded {len(player_files)} player files")
            except FileNotFoundError:
                logger.warning(f"⚠️  Players directory not found on remote server")
            
            # Close connections
            sftp.close()
            ssh.close()
            
            logger.info(f"✅ Successfully downloaded saves from SFTP")
            return True
            
        except paramiko.AuthenticationException:
            logger.error(f"❌ SFTP authentication failed for {self.username}@{self.host}")
            return False
        except paramiko.SSHException as e:
            logger.error(f"❌ SFTP SSH error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ SFTP error: {e}")
            return False
    
    def _download_via_ftp(self) -> bool:
        """Download save files via FTP (with TLS support)"""
        try:
            logger.debug(f"📡 Connecting to FTP {self.host}:{self.port}")
            
            # Try FTPS (FTP with TLS) first, fall back to plain FTP
            ftp = None
            try:
                # Try secure FTP first
                ftp = ftplib.FTP_TLS()
                ftp.connect(self.host, self.port, timeout=10)
                ftp.login(self.username, self.password)
                ftp.prot_p()  # Enable secure data connection
                logger.debug("✅ Connected using FTPS (FTP with TLS)")
            except (ftplib.error_perm, AttributeError, Exception) as e:
                logger.debug(f"FTPS failed ({e}), trying plain FTP...")
                # Fall back to plain FTP
                if ftp:
                    try:
                        ftp.quit()
                    except:
                        pass
                ftp = ftplib.FTP()
                ftp.connect(self.host, self.port, timeout=10)
                ftp.login(self.username, self.password)
                logger.debug("✅ Connected using plain FTP")
            
            # Change to remote directory
            try:
                ftp.cwd(self.remote_path)
            except ftplib.error_perm:
                logger.error(f"❌ Remote path not found: {self.remote_path}")
                ftp.quit()
                return False
            
            # Download Level.sav
            local_level = self.local_temp_dir / "Level.sav"
            
            try:
                with open(local_level, 'wb') as f:
                    ftp.retrbinary('RETR Level.sav', f.write)
                logger.debug(f"✅ Downloaded Level.sav")
            except ftplib.error_perm:
                logger.error(f"❌ Level.sav not found on remote server")
                ftp.quit()
                return False
            
            # Download LevelMeta.sav (optional)
            local_meta = self.local_temp_dir / "LevelMeta.sav"
            
            try:
                with open(local_meta, 'wb') as f:
                    ftp.retrbinary('RETR LevelMeta.sav', f.write)
                logger.debug(f"✅ Downloaded LevelMeta.sav")
            except ftplib.error_perm:
                logger.debug(f"ℹ️  LevelMeta.sav not found (optional)")
            
            # Download Players directory
            players_local = self.local_temp_dir / "Players"
            
            # Clean and recreate local Players directory
            if players_local.exists():
                shutil.rmtree(players_local)
            players_local.mkdir()
            
            try:
                # Change to Players directory
                ftp.cwd('Players')
                
                # List files
                player_files = []
                ftp.retrlines('NLST', player_files.append)
                
                # Download each player file
                for filename in player_files:
                    if filename.endswith('.sav'):
                        local_file = players_local / filename
                        with open(local_file, 'wb') as f:
                            ftp.retrbinary(f'RETR {filename}', f.write)
                        logger.debug(f"✅ Downloaded player: {filename}")
                
                logger.info(f"✅ Downloaded {len(player_files)} player files")
            except ftplib.error_perm:
                logger.warning(f"⚠️  Players directory not found on remote server")
            
            # Close connection
            ftp.quit()
            
            logger.info(f"✅ Successfully downloaded saves from FTP")
            return True
            
        except ftplib.error_perm as e:
            logger.error(f"❌ FTP authentication or permission error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ FTP error: {e}")
            return False
    
    def download(self) -> bool:
        """Download save files from remote server"""
        logger.info(f"⬇️  Downloading saves from {self.protocol.upper()} server...")
        
        if self.protocol == "sftp":
            return self._download_via_sftp()
        elif self.protocol == "ftp":
            return self._download_via_ftp()
        else:
            logger.error(f"❌ Unsupported protocol: {self.protocol}")
            return False
    
    def get_local_save_path(self) -> Path:
        """Get the local temporary directory where saves are downloaded"""
        return self.local_temp_dir


class RemoteSavePoller:
    """Polls remote server periodically for save file updates"""
    
    def __init__(
        self,
        remote_loader: RemoteSaveLoader,
        poll_interval: int,
        on_change_callback: Callable,
        loop: asyncio.AbstractEventLoop
    ):
        self.remote_loader = remote_loader
        self.poll_interval = poll_interval  # seconds
        self.on_change_callback = on_change_callback
        self.loop = loop
        self._task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"⏰ RemoteSavePoller initialized: {poll_interval}s interval")
    
    async def _poll_loop(self):
        """Main polling loop"""
        while self._running:
            try:
                logger.debug(f"🔄 Polling remote saves...")
                
                # Download files (runs in executor to avoid blocking)
                success = await self.loop.run_in_executor(None, self.remote_loader.download)
                
                if success:
                    # Notify callback of change
                    await self.on_change_callback()
                else:
                    logger.warning(f"⚠️  Failed to download remote saves")
                
            except Exception as e:
                logger.error(f"❌ Error in polling loop: {e}")
            
            # Wait for next poll interval
            await asyncio.sleep(self.poll_interval)
    
    def start(self) -> bool:
        """Start polling"""
        if self._running:
            logger.warning("⚠️  Poller already running")
            return False
        
        logger.info(f"▶️  Starting remote save polling (every {self.poll_interval}s)")
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        return True
    
    async def stop(self):
        """Stop polling"""
        if not self._running:
            return
        
        logger.info("⏹️  Stopping remote save polling")
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def poll_now(self):
        """Trigger an immediate poll (for manual reload)"""
        logger.info("🔄 Manual poll triggered")
        
        try:
            success = await self.loop.run_in_executor(None, self.remote_loader.download)
            
            if success and self.on_change_callback:
                # Trigger callback to reload parser and notify clients
                await self.on_change_callback()
                return True
            else:
                logger.warning(f"⚠️  Manual poll failed")
                return False
        except Exception as e:
            logger.error(f"❌ Error in manual poll: {e}")
            return False
