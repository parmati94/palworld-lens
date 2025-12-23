"""Helper utilities for parsing Palworld save data"""
from typing import Any, Optional, Dict


def get_val(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely extract value from Palworld data structure.
    
    Palworld data can be nested like: {'value': {'value': 34}} or {'value': 34}
    This helper handles both cases and returns the actual value.
    
    Args:
        data: Dictionary containing Palworld save data
        key: Key to extract value for
        default: Default value if key not found or value is None
        
    Returns:
        The extracted value, or default if not found
    """
    val = data.get(key)
    if val is None:
        return default
        
    # Extract value if it's a dict
    if isinstance(val, dict) and "value" in val:
        val = val["value"]
        # Sometimes it's double-nested
        if isinstance(val, dict) and "value" in val:
            val = val["value"]
    
    return val if val is not None else default
