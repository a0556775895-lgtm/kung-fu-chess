import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from piece_factory import PieceFactory
from pawn import Pawn
from king import King
from queen import Queen
from rook import Rook
from bishop import Bishop
from knight import Knight
from piece import PieceColor


def test_create_white_pawn():
    assert isinstance(PieceFactory.create_piece("wP"), Pawn)


def test_create_black_pawn():
    assert isinstance(PieceFactory.create_piece("bP"), Pawn)


def test_create_king():
    assert isinstance(PieceFactory.create_piece("wK"), King)


def test_create_queen():
    assert isinstance(PieceFactory.create_piece("bQ"), Queen)


def test_create_rook():
    assert isinstance(PieceFactory.create_piece("wR"), Rook)


def test_create_bishop():
    assert isinstance(PieceFactory.create_piece("bB"), Bishop)


def test_create_knight():
    assert isinstance(PieceFactory.create_piece("wN"), Knight)


def test_piece_color():
    piece = PieceFactory.create_piece("bQ")

    assert piece.color == PieceColor.BLACK


def test_unknown_piece():
    with pytest.raises(ValueError, match="UNKNOWN_TOKEN"):
        PieceFactory.create_piece("wX")