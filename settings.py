"""User settings and configuration for TokenLords Bot."""
import json
import os

DEFAULT_SETTINGS = {
    "battle": {
        "enabled": False,
        "min_energy": 5,
        "hp_limit_percent": 20,
        "skill_priority": ["Attack", "none", "none", "none", "none", "none"],
        "skills_validated": False,
        "last_skill_names": []
    },
    "chests": {
        "enabled": False,
        "min_bronze": 0,
        "selected": {
            "Resource": [],
            "Armory": []
        }
    },
    "business": {
        "enabled": False,
        "auto_bronze": False,
        "auto_materials": False,
        "bronze_interval_min": 30,
        "materials_interval_min": 30
    },
    "general": {
        "auto_sync": False,
        "sync_interval_sec": 30,
        "theme": "dark"
    }
}

SETTINGS_FILE = "bot_settings.json"


class Settings:
    """Persistent user settings."""
    
    def __init__(self):
        self._data = self._load()
    
    def _load(self):
        """Load settings from file or create defaults."""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    data = json.load(f)
                    # Merge with defaults to handle new fields
                    return self._merge_defaults(data, DEFAULT_SETTINGS)
            except Exception as e:
                print(f"Error loading settings: {e}")
                return DEFAULT_SETTINGS.copy()
        return DEFAULT_SETTINGS.copy()
    
    def _merge_defaults(self, data, defaults):
        """Recursively merge defaults into loaded data."""
        result = defaults.copy()
        for key, value in data.items():
            if key in result:
                if isinstance(value, dict) and isinstance(result[key], dict):
                    result[key] = self._merge_defaults(value, result[key])
                else:
                    result[key] = value
            else:
                result[key] = value
        return result
    
    def save(self):
        """Save settings to file."""
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def get(self, path, default=None):
        """Get setting by dot path (e.g., 'battle.min_energy')."""
        keys = path.split('.')
        value = self._data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def set(self, path, value):
        """Set setting by dot path."""
        keys = path.split('.')
        target = self._data
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        target[keys[-1]] = value
        self.save()
    
    @property
    def battle_enabled(self):
        return self._data.get('battle', {}).get('enabled', False)
    
    @battle_enabled.setter
    def battle_enabled(self, value):
        self._data['battle']['enabled'] = value
        self.save()
    
    @property
    def chests_enabled(self):
        return self._data.get('chests', {}).get('enabled', False)
    
    @chests_enabled.setter
    def chests_enabled(self, value):
        self._data['chests']['enabled'] = value
        self.save()
    
    @property
    def business_enabled(self):
        return self._data.get('business', {}).get('enabled', False)
    
    @business_enabled.setter
    def business_enabled(self, value):
        self._data['business']['enabled'] = value
        self.save()
