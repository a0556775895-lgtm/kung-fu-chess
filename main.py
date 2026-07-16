import logging

from view.display_manager import DisplayManager

if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(
        filename="game.log",
        filemode="w",
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    DisplayManager().run()