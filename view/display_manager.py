import cv2

from boardio.board_parser import BoardParser
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
from .hud.score.score_data import ScoreData
from .hud.score.score_renderer import ScoreRenderer
from .hud.moves_log.moves_log_data import MovesLogData
from .hud.moves_log.moves_log_renderer import MovesLogRenderer
from .input.mouse_command_extractor import MouseCommandExtractor
from .input.commands import LocalCommandSender
from . import config

STANDARD_OPENING = [
    "bR bN bB bQ bK bB bN bR",
    "bP bP bP bP bP bP bP bP",
    ".  .  .  .  .  .  .  .",
    ".  .  .  .  .  .  .  .",
    ".  .  .  .  .  .  .  .",
    ".  .  .  .  .  .  .  .",
    "wP wP wP wP wP wP wP wP",
    "wR wN wB wQ wK wB wN wR",
]

WINDOW_NAME = "KungFu Chess"


class DisplayManager:
    def __init__(self):
        self._board = BoardParser.parse(STANDARD_OPENING)
        self._game_engine = GameEngine(self._board)

        self._geometry = BoardGeometry()
        self._background_loader = BackgroundLoader(self._geometry)
        self._board_loader = BoardLoader(self._geometry)
        self._animation_library = AnimationLibrary(self._geometry)
        self._highlight_loader = HighlightLoader(self._geometry)        # חדש

        for loader in (self._background_loader, self._board_loader, self._animation_library,
                       self._highlight_loader):                          # עודכן - נוסף highlight_loader
            loader.load()

        self._board_renderer = BoardRenderer(self._board_loader, self._geometry)
        self._piece_animator = PieceAnimator(self._animation_library, self._geometry)
        self._piece_renderer = PieceRenderer(self._animation_library, self._piece_animator)
        self._selection_renderer = SelectionRenderer(self._highlight_loader, self._geometry)  # חדש
        self._score_data = ScoreData()
        self._score_renderer = ScoreRenderer(self._score_data, self._geometry)
        self._moves_log_data = MovesLogData()
        self._moves_log_renderer = MovesLogRenderer(self._moves_log_data, self._geometry)

        self._renderers = [self._board_renderer, self._selection_renderer, self._piece_renderer,
                            self._score_renderer, self._moves_log_renderer]

        self._game_engine.subscribe(self._piece_animator)
        self._game_engine.subscribe(self._score_data)
        self._game_engine.subscribe(self._moves_log_data)

        self._board_mapper = BoardMapper(
            self._geometry.rows, self._geometry.cols, cell_size=self._geometry.cell_w
        )
        self._controller = Controller(self._board, self._game_engine, self._board_mapper)
        self._extractor = MouseCommandExtractor(self._board_mapper, self._geometry)
        self._command_sender = LocalCommandSender(self._controller, self._game_engine)

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
        self._moves_log_data.tick(dt_ms)  # advance before wait() so on_arrival timestamps this frame correctly
        self._game_engine.wait(dt_ms)
        snapshot = self._game_engine.snapshot(self._controller.selected_position)
        self._piece_animator.update(dt_ms, snapshot)
        self._last_snapshot = snapshot

    def render(self):
        canvas = self._background_loader.fresh_canvas()
        for renderer in self._renderers:
            renderer.render(canvas, self._last_snapshot)
        return canvas

    def run(self):
        last_time = cv2.getTickCount()
        tick_freq = cv2.getTickFrequency()

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

        cv2.destroyAllWindows()