# Скрипт для сихронизации GitHub и CodeBerg

from dataclasses import dataclass, fields
from enum import Enum
import json

class Constants(Enum):
    CONFIG_PATH = "config.json"
    REPOS_DIR = "./repos"
    
def main():
    try:
        config = load_config()
        print(config)
    except Exception as e:
        print(e)

class TypeCheckMixin:
    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if not isinstance(value, field.type):
                raise TypeError(f"incorrect field '{field.name}' type")

@dataclass
class GitHubConfig(TypeCheckMixin):
    token: str

@dataclass
class CodeBergConfig(TypeCheckMixin):
    token: str

@dataclass
class AppConfig(TypeCheckMixin):
    github: GitHubConfig
    codeberg: CodeBergConfig

def load_config() -> AppConfig:
    try:
        with open(Constants.CONFIG_PATH.value, 'r') as f:        
            # raw data
            data = json.load(f)
            github_data = data["github"]
            codeberg_data = data["codeberg"]

            # configs
            github_config = GitHubConfig(**github_data)
            codeberg_config = CodeBergConfig(**codeberg_data)
            app_config = AppConfig(github_config, codeberg_config)
            
            return app_config
    except FileNotFoundError as e:
        raise RuntimeError(f"not found file '{Constants.CONFIG_PATH.value}'") from e
    except json.JSONDecodeError as e:
        raise RuntimeError("invalid json format") from e
    except (KeyError, TypeError) as e:
        raise RuntimeError("invalid json structure") from e

if __name__ == "__main__":
    main()