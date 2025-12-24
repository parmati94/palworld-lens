"""YAML-based schema loader and field extractor"""
import os
import yaml
from typing import Any, Dict, List, Optional
from pathlib import Path


# Named transform functions
def divide_by_1000(value: Any) -> Any:
    """Convert milli-values to regular values (e.g., milli-HP to HP)"""
    if isinstance(value, (int, float)) and value > 1000:
        return int(value / 1000)
    return int(value) if isinstance(value, (int, float)) else 100


TRANSFORMS = {
    "divide_by_1000": divide_by_1000,
}


class SchemaLoader:
    """Loads and manages YAML schemas for save data extraction"""
    
    def __init__(self, schema_file: str):
        """Load schema from YAML file
        
        Args:
            schema_file: Path to YAML schema file relative to schemas directory
        """
        schema_dir = Path(__file__).parent.parent / "schemas"
        schema_path = schema_dir / schema_file
        
        with open(schema_path, 'r') as f:
            self.schema = yaml.safe_load(f)
        
        self.fields = self.schema.get('fields', {})
        self.lists = self.schema.get('lists', {})
    
    def extract_field(self, data: Dict[str, Any], field_name: str) -> Any:
        """Extract a field value from nested save data
        
        Args:
            data: Dictionary containing save data
            field_name: Name of field to extract (must be in schema)
            
        Returns:
            Extracted value or default if not found
        """
        if field_name not in self.fields:
            return None
        
        field_schema = self.fields[field_name]
        path = field_schema.get('path', [])
        default = field_schema.get('default')
        
        # Start with the top-level key
        current = data.get(field_name)
        if current is None:
            return default
        
        # Navigate through the path
        for path_key in path:
            if not isinstance(current, dict):
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
