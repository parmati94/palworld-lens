"""YAML-based schema loader - unified collection and field extraction"""
import os
import yaml
from typing import Any, Dict, List, Optional
from pathlib import Path

from backend.common.logging_config import get_logger

logger = get_logger(__name__)


# Named transform functions
def divide_by_1000(value: Any) -> Any:
    """Convert milli-values to regular values (e.g., milli-HP to HP)"""
    if isinstance(value, (int, float)) and value > 1000:
        return int(value / 1000)
    return int(value) if isinstance(value, (int, float)) else 100


TRANSFORMS = {
    "divide_by_1000": divide_by_1000,
}


class SchemaManager:
    """Singleton manager for schema loaders - caches instances to avoid reloading"""
    _instances: Dict[str, 'SchemaLoader'] = {}
    
    @classmethod
    def get(cls, schema_file: str) -> 'SchemaLoader':
        """Get or create a SchemaLoader instance for the given schema file
        
        Args:
            schema_file: Name of schema file (e.g., 'pals.yaml', 'collections.yaml')
            
        Returns:
            Cached or newly created SchemaLoader instance
        """
        if schema_file not in cls._instances:
            logger.debug(f"Loading schema: {schema_file}")
            cls._instances[schema_file] = SchemaLoader(schema_file)
        return cls._instances[schema_file]
    
    @classmethod
    def clear_cache(cls):
        """Clear all cached schema instances (useful for testing or hot-reload)"""
        logger.debug("Clearing schema cache")
        cls._instances.clear()
    
    @classmethod
    def preload_all(cls):
        """Preload all schema files on startup for consistent logging and performance
        
        Call this once during application initialization to load all schemas upfront.
        """
        schema_files = [
            "collections.yaml",
            "pals.yaml",
            "players.yaml",
            "guilds.yaml",
            "bases.yaml",
            "containers.yaml"
        ]
        
        logger.info("Preloading all schemas...")
        for schema_file in schema_files:
            cls.get(schema_file)
        logger.info(f"Successfully preloaded {len(schema_files)} schemas")


class SchemaLoader:
    """Unified schema loader for both collections and fields
    
    Handles two types of extraction:
    1. Collections: Extract multiple entities from save data (e.g., all characters)
    2. Fields: Extract individual field values from entity data (e.g., one pal's level)
    """

    
    def __init__(self, schema_file: str):
        """Load schema from YAML file
        
        Args:
            schema_file: Path to YAML schema file relative to schemas directory
        """
        schema_dir = Path(__file__).parent.parent / "schemas"
        schema_path = schema_dir / schema_file
        
        self.schema_file = schema_file
        
        logger.debug(f"Loading schema from: {schema_path}")
        with open(schema_path, 'r') as f:
            self.schema = yaml.safe_load(f)
        
        self.fields = self.schema.get('fields', {})
        self.lists = self.schema.get('lists', {})
        self.collections = self.schema.get('collections', {})
        
        logger.debug(f"Schema '{schema_file}' loaded: {len(self.fields)} fields, {len(self.lists)} lists, {len(self.collections)} collections")
    
    def extract_field(self, data: Dict[str, Any], field_name: str) -> Optional[Any]:
        """Extract a field value from nested save data
        
        Args:
            data: Dictionary containing save data
            field_name: Name of field to extract (must be in schema)
            
        Returns:
            Extracted value or default if not found, None if field not in schema
        """
        if field_name not in self.fields:
            logger.debug(f"Field '{field_name}' not found in schema '{self.schema_file}'. Available fields: {list(self.fields.keys())[:10]}")
            return None
        
        field_schema = self.fields[field_name]
        path = field_schema.get('path', [])
        default = field_schema.get('default')
        
        # Support root_key to decouple logical field name from data structure
        # If root_key is specified, start from that key and follow path
        # If not specified, the path should contain the full navigation including root
        if 'root_key' in field_schema:
            root_key = field_schema['root_key']
            current = data.get(root_key)
            if current is None:
                return default
            
            # Navigate through the path after root_key
            for path_key in path:
                if not isinstance(current, dict):
                    return default
                current = current.get(path_key)
                if current is None:
                    return default
        else:
            # No root_key: path includes everything starting from data
            current = data
            for path_key in path:
                if not isinstance(current, dict):
                    return default
                current = current.get(path_key)
                if current is None:
                    return default
                break
            current = current.get(path_key)
            if current is None:
                return default
        
        # Auto-drill through additional nested 'value' keys
        while isinstance(current, dict) and "value" in current:
            current = current["value"]
        
        # Handle enum prefix stripping
        strip_prefix = field_schema.get('strip_prefix')
        if strip_prefix and isinstance(current, str) and "::" in current:
            current = current.split("::")[-1]
        
        # Apply enum mapping if provided
        enum_map = field_schema.get('enum_map')
        if enum_map and current is not None:
            current = enum_map.get(str(current), current)
        
        # Apply named transform if provided
        transform_name = field_schema.get('transform')
        if transform_name and current is not None:
            transform_func = TRANSFORMS.get(transform_name)
            if transform_func:
                try:
                    current = transform_func(current)
                except (ValueError, TypeError):
                    return default
        
        return current if current is not None else default
    
    def extract_list(self, data: Dict[str, Any], list_name: str) -> List[Any]:
        """Extract a list from nested save data
        
        Args:
            data: Dictionary containing save data
            list_name: Name of list field to extract
            
        Returns:
            List of extracted values (or empty list if not found)
        """
        if list_name not in self.lists:
            logger.debug(f"List '{list_name}' not found in schema '{self.schema_file}'. Available lists: {list(self.lists.keys())}")
            return []
        
        list_schema = self.lists[list_name]
        path = list_schema.get('path', [])
        
        # Navigate to the list
        current = data.get(list_name)
        if current is None:
            return []
        
        for path_key in path:
            if not isinstance(current, dict):
                break
            current = current.get(path_key)
            if current is None:
                return []
        
        if not isinstance(current, list):
            return []
        
        # If list has item schema, extract structured data from each item
        item_schema = list_schema.get('items')
        if item_schema:
            results = []
            for entry in current:
                if not isinstance(entry, dict):
                    continue
                
                item_data = {}
                for field_key, field_def in item_schema.items():
                    item_value = self._extract_from_path(entry, field_def)
                    item_data[field_key] = item_value
                
                results.append(item_data)
            return results
        
        # Otherwise just return the raw list
        return current
    
    def _extract_from_path(self, data: Dict[str, Any], field_def: Dict[str, Any]) -> Any:
        """Extract value from data using field definition
        
        Args:
            data: Dictionary to extract from
            field_def: Field definition with path, strip_prefix, etc.
            
        Returns:
            Extracted value
        """
        path = field_def.get('path', [])
        default = field_def.get('default')
        
        current = data
        for path_key in path:
            if not isinstance(current, dict):
                return default
            current = current.get(path_key)
            if current is None:
                return default
        
        # Auto-drill through additional nested 'value' keys
        while isinstance(current, dict) and "value" in current:
            current = current["value"]
        
        # Handle enum prefix stripping
        strip_prefix = field_def.get('strip_prefix')
        if strip_prefix and isinstance(current, str) and "::" in current:
            current = current.split("::")[-1]
        
        return current if current is not None else default
    
    # Collection extraction methods (unified from GenericExtractor)
    
    def extract_collection(self, world_data: Dict[str, Any], collection_name: str) -> Dict[str, Dict[str, Any]]:
        """Extract a collection of entities from world save data
        
        Args:
            world_data: World save data from GVAS file
            collection_name: Name of collection to extract (must be in schema)
            
        Returns:
            Dict mapping entity IDs to their data
        """
        if collection_name not in self.collections:
            logger.debug(f"Collection '{collection_name}' not found in schema '{self.schema_file}'. Available collections: {list(self.collections.keys())}")
            return {}
        
        collection_schema = self.collections[collection_name]
        root_key = collection_schema.get('root_key')
        structure = collection_schema.get('structure', {})
        
        # Navigate to root collection
        root_data = world_data.get(root_key)
        if not isinstance(root_data, dict):
            return {}
        
        # Navigate through structure path
        current = root_data
        for path_key in structure.get('path', []):
            current = self._safe_get(current, path_key)
            if current is None:
                return {}
        
        # Should now be at a list of entries
        if structure.get('type') == 'list':
            if not isinstance(current, list):
                return {}
            
            return self._extract_list_entries(current, structure)
        
        return {}
    
    def _extract_list_entries(self, entries: List[Dict[str, Any]], structure: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Extract key-value pairs from a list of entries
        
        Args:
            entries: List of entry dictionaries to extract from
            structure: Schema structure defining item_key and item_value extraction
            
        Returns:
            Dict mapping extracted keys to extracted values
        """
        result = {}
        item_key_schema = structure.get('item_key', {})
        item_value_schema = structure.get('item_value', {})
        
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            
            # Extract key
            key = self._extract_key(entry, item_key_schema)
            if not key:
                continue
            
            # Extract value
            value = self._extract_value_from_entry(entry, item_value_schema)
            if value is not None:
                result[str(key)] = value
        
        return result
    
    def _extract_key(self, entry: Dict[str, Any], key_schema: Dict[str, Any]) -> Optional[str]:
        """Extract key from entry using schema"""
        key_type = key_schema.get('type', 'simple')
        
        if key_type == 'flexible_uuid':
            # Try dict path first, fall back to direct path
            dict_path = key_schema.get('dict_path', [])
            key_data = self._navigate_path(entry, dict_path)
            
            if key_data is None:
                # Try direct path
                direct_path = key_schema.get('direct_path', [])
                key_data = self._navigate_path(entry, direct_path)
            
            return str(key_data) if key_data else None
        
        elif key_type == 'nested_uuid':
            path = key_schema.get('path', [])
            key_data = self._navigate_path(entry, path)
            return str(key_data) if key_data else None
        
        elif key_type == 'simple':
            path = key_schema.get('path', ['key'])
            key_data = self._navigate_path(entry, path)
            return str(key_data) if key_data else None
        
        return None
    
    def _extract_value_from_entry(self, entry: Dict[str, Any], value_schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract value from entry using schema"""
        path = value_schema.get('path', [])
        return self._navigate_path(entry, path)
    
    def _navigate_path(self, data: Any, path: List[str]) -> Optional[Any]:
        """Navigate through nested dicts/lists using path"""
        current = data
        
        for key in path:
            if not isinstance(current, dict):
                return None
            
            current = self._safe_get(current, key)
            if current is None:
                return None
        
        return current
    
    def _safe_get(self, data: Any, key: str) -> Optional[Any]:
        """Safely get value from dict"""
        if not isinstance(data, dict):
            return None
        return data.get(key)
