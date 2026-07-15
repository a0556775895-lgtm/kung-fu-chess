from dataclasses import dataclass
from ..img import Img
from ..pieces.piece_loader import PieceLoader
from .animation_config_loader import AnimationConfigLoader
from .state_config import StateConfig
from .. import config


@dataclass(frozen=True)
class AnimationClip:
    frames: list[Img]
    state_config: StateConfig


class AnimationLibrary:
    def __init__(self, geometry, piece_loader: PieceLoader = None,
                 config_loader: AnimationConfigLoader = None,
                 kinds=config.PIECE_KINDS, colors=config.PIECE_COLORS,
                 states=config.ANIMATION_STATES):
        """Wire up geometry, piece/config loaders, and the kinds/colors/states to build clips for; starts with no clips loaded."""
        self._geometry = geometry
        self._kinds = kinds
        self._colors = colors
        self._states = states
        self._piece_loader = piece_loader or PieceLoader()
        self._config_loader = config_loader or AnimationConfigLoader(
            kinds=kinds, colors=colors, states=states
        )
        self._clips: dict[tuple[str, str, str], AnimationClip] = {}

    def load(self) -> None:
        """Load state configs and build every (kind, color, state) animation clip's frames."""
        state_configs = self._config_loader.load_all()
        cell_size = (self._geometry.cell_w, self._geometry.cell_h)

        self._clips = {}
        for (kind, color, state), state_config in state_configs.items():
            frame_count = self._piece_loader.count_frames(kind, color, state)
            frames = [
                self._piece_loader.load_frame(kind, color, state, i, cell_size)
                for i in range(1, frame_count + 1)
            ]
            self._clips[(kind, color, state)] = AnimationClip(frames, state_config)

    def reload(self) -> None:
        """Reload all animation clips from disk."""
        self.load()

    def get_clip(self, kind: str, color: str, state: str) -> AnimationClip:
        """Return the loaded AnimationClip for the given piece kind, color, and state."""
        return self._clips[(kind, color, state)]