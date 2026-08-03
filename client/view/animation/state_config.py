import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PhysicsConfig:
    speed_m_per_sec: float
    next_state_when_finished: str


@dataclass(frozen=True)
class GraphicsConfig:
    frames_per_sec: int
    is_loop: bool


@dataclass(frozen=True)
class StateConfig:
    physics: PhysicsConfig
    graphics: GraphicsConfig

    @staticmethod
    def load(config_path: Path) -> "StateConfig":
        """Load a StateConfig (physics + graphics settings) from a config.json file."""
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        return StateConfig(
            physics=PhysicsConfig(**data["physics"]),
            graphics=GraphicsConfig(**data["graphics"]),
        )