from pathlib import Path
from .state_config import StateConfig
from .. import config


class AnimationConfigLoader:
    """טוען את כל 5 קובצי ה-config.json לכל כלי, ומוודא ב-startup
    שכל next_state_when_finished מצביע ל-state קיים בפועל -
    typo נתפס כאן, לא כתקיעה חזותית בזמן ריצה."""

    def __init__(self, assets_root: Path = config.ASSETS_ROOT,
                 kinds=config.PIECE_KINDS, colors=config.PIECE_COLORS,
                 states=config.ANIMATION_STATES):
        self._assets_root = assets_root
        self._kinds = kinds
        self._colors = colors
        self._states = states

    def config_path(self, kind: str, color: str, state: str) -> Path:
        return self._assets_root / f"{kind}{color}" / "states" / state / "config.json"

    def load_all(self) -> dict[tuple[str, str, str], StateConfig]:
        configs = {}
        for kind in self._kinds:
            for color in self._colors:
                for state in self._states:
                    path = self.config_path(kind, color, state)
                    configs[(kind, color, state)] = StateConfig.load(path)
        self._validate_transitions(configs)
        return configs

    def _validate_transitions(self, configs: dict) -> None:
        valid_states = set(self._states)
        for (kind, color, state), state_config in configs.items():
            next_state = state_config.physics.next_state_when_finished
            if next_state not in valid_states:
                raise ValueError(
                    f"קונפיג לא תקין: {kind}{color}/{state}/config.json "
                    f"מצביע ל-next_state_when_finished='{next_state}' "
                    f"שאינו state קיים (states תקינים: {sorted(valid_states)})"
                )