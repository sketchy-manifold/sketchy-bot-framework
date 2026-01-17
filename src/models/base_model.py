import inspect
from typing import Dict, Any
from datetime import datetime

class BaseModel:
    """Base class for all API models."""
    
    @staticmethod
    def _convert_camel_to_snake(key: str) -> str:
        """Convert camelCase to snake_case."""
        import re
        return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', key).lower()
    
    @staticmethod
    def _convert_timestamps(data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert timestamp fields from milliseconds to datetime objects."""
        if isinstance(data, dict):
            for key, value in data.items():
                if key.endswith('Time') and isinstance(value, (int, float)):
                    data[key] = datetime.fromtimestamp(value / 1000)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseModel':
        """Create a model instance from a dictionary."""
        if not isinstance(data, dict):
            return data
        
        # Convert timestamps
        data = cls._convert_timestamps(data)
        
        # Convert camelCase to snake_case
        new_data = {}
        for key, value in data.items():
            new_key = cls._convert_camel_to_snake(key)
            new_data[new_key] = value

        # Inspect __init__ parameters
        init_params = inspect.signature(cls.__init__).parameters
        valid_keys = set(init_params) - {'self'}

        # Filter valid arguments
        filtered_args = {k: v for k, v in new_data.items() if k in valid_keys}
        extra_keys = set(new_data) - valid_keys

        if extra_keys:
            # hacky dynamic import b/c circular otherwise
            from src.logger import logger, ErrorEvent
            logger.log(ErrorEvent(
                error_type="Invalid key in obj init",
                message=f"{cls.__name__}.from_dict() got unexpected keys: {extra_keys}",
                source=__class__,
            ))
        
        return cls(**filtered_args)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the model to a dictionary."""
        return self.__dict__
