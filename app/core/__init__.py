"""Core spreadsheet primitives shared by UI, engine, and file services."""

from app.core.coordinates import CellAddress, CellRange, column_index_to_label, column_label_to_index

__all__ = ["CellAddress", "CellRange", "column_index_to_label", "column_label_to_index"]
