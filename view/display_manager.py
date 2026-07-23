import cv2

from boardio.standard_opening import create_standard_board
from engine.game_engine import GameEngine
from input.board_mapper import BoardMapper
from input.controller import Controller

from .geometry import BoardGeometry
from .background.background_loader import BackgroundLoader
from .board.board_loader import BoardLoader
from .board.board_renderer import BoardRenderer
from .animation.animation_library import AnimationLibrary
from .animation.piece_animator import PieceAnimator
from .pieces.piece_renderer import PieceRenderer
from .selection.highlight_loader import HighlightLoader          # חדש
from .selection.selection_renderer import SelectionRenderer      # חדש
from .hud.score.score_renderer import ScoreRenderer
from .hud.moves_log.moves_log_data import MovesLogData
from .hud.moves_log.moves_log_renderer import MovesLogRenderer
from .game_over.game_over_renderer import GameOverRenderer
from .audio.sound_player import SoundPlayer
from .input.mouse_command_extractor import MouseCommandExtractor
from .input.commands import GameCommandSender
from . import config

WINDOW_NAME = "KungFu Chess"


class DisplayManager:
    """Own the OpenCV presentation while receiving state from injected services."""

    def __init__(
        self,
        board=None,
        game_engine=None,
        *,
        game_updater=None,
        event_source=None,
        starts_game=None,
    ):
        """Build local mode by default, or use an injected local/remote game source."""
        local_mode = board is None and game_engine is None
        if local_mode:
            board = create_standard_board()
            game_engine = GameEngine(board)
        elif board is None or game_engine is None:
            raise ValueError("BOARD_AND_GAME_ENGINE_REQUIRED")

        if game_updater is None:
            if not local_mode:
                raise ValueError("GAME_UPDATER_REQUIRED")
            game_updater = game_engine.wait

        if event_source is None:
            if not local_mode:
                raise ValueError("EVENT_SOURCE_REQUIRED")
            event_source = game_engine

        self._board = board
        self._game_engine = game_engine
        self._game_updater = game_updater
        self._event_source = event_source
        self._starts_game = local_mode if starts_game is None else starts_game

        self._geometry = BoardGeometry()
        self._background_loader = BackgroundLoader(self._geometry)
        self._board_loader = BoardLoader(self._geometry)
        self._animation_library = AnimationLibrary(self._geometry)
        self._highlight_loader = HighlightLoader(self._geometry)        # חדש
        self._game_over_renderer = GameOverRenderer(self._geometry)

        for loader in (self._background_loader, self._board_loader, self._animation_library,
                       self._highlight_loader, self._game_over_renderer):
            loader.load()

        self._board_renderer = BoardRenderer(self._board_loader, self._geometry)
        self._piece_animator = PieceAnimator(self._animation_library, self._geometry)
        self._piece_renderer = PieceRenderer(self._animation_library, self._piece_animator)
        self._selection_renderer = SelectionRenderer(self._highlight_loader, self._geometry)  # חדש
        self._score_renderer = ScoreRenderer(self._geometry)
        self._moves_log_data = MovesLogData()
        self._moves_log_renderer = MovesLogRenderer(self._moves_log_data, self._geometry)

        self._renderers = [self._board_renderer, self._selection_renderer, self._piece_renderer,
                            self._score_renderer, self._moves_log_renderer,
                            self._game_over_renderer]

        self._observer_cancellations = [
            self._event_source.subscribe(self._piece_animator),
            self._event_source.subscribe(self._moves_log_data),
        ]
        self._sound_player = SoundPlayer(self._event_source.bus)

        self._board_mapper = BoardMapper(
            self._geometry.rows, self._geometry.cols, cell_size=self._geometry.cell_w
        )
        self._controller = Controller(self._board, self._game_engine, self._board_mapper)
        self._extractor = MouseCommandExtractor(self._board_mapper, self._geometry)
        self._command_sender = GameCommandSender(self._controller, self._game_engine)

        cv2.namedWindow(WINDOW_NAME)
        cv2.setMouseCallback(WINDOW_NAME, self._on_mouse)

    def _on_mouse(self, event, x, y, flags, param):
        command = None
        if event == cv2.EVENT_LBUTTONDOWN:
            command = self._extractor.extract_left_click(x, y)
        elif event == cv2.EVENT_RBUTTONDOWN:
            command = self._extractor.extract_right_click(x, y)

        if command is not None:
            self._command_sender.send(command)

    def update(self, dt_ms: int) -> None:
        """Advance presentation time and ask the injected source for fresh game state."""
        self._moves_log_data.tick(dt_ms)
        self._game_updater(dt_ms)
        snapshot = self._game_engine.snapshot(self._controller.selected_position)
        self._piece_animator.update(dt_ms, snapshot)
        self._last_snapshot = snapshot

    def render(self):
        canvas = self._background_loader.fresh_canvas()
        for renderer in self._renderers:
            renderer.render(canvas, self._last_snapshot)
        return canvas

    def run(self):
        """Run the window loop until Escape, then release presentation resources."""
        if self._starts_game:
            self._game_engine.start_game()
        last_time = cv2.getTickCount()
        tick_freq = cv2.getTickFrequency()

        try:
            while True:
                now = cv2.getTickCount()
                dt_ms = int((now - last_time) / tick_freq * 1000)
                last_time = now
                dt_ms = min(dt_ms, config.MAX_DT_MS)

                self.update(dt_ms)
                canvas = self.render()

                cv2.imshow(WINDOW_NAME, canvas.img)
                key = cv2.waitKey(config.FRAME_DELAY_MS)
                if key == 27:  # Esc
                    break
        finally:
            for cancel in self._observer_cancellations:
                cancel()
            self._sound_player.close()
            cv2.destroyAllWindows()
