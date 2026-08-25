"""Workbook file conversion helpers for Excel and CSV formats.

This module intentionally keeps conversion logic separate from the spreadsheet
engine and storage adapters.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from openpyxl import Workbook as OpenPyxlWorkbook
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from app.models.workbook import Workbook


_INVALID_SHEET_CHARS = set('[]:*?/\\')


class WorkbookConversionError(Exception):
    """Raised when workbook conversion fails."""


class WorkbookFileConverter:
    """Import/export workbook files using practical compatibility rules."""

    def import_xlsx(self, path: str) -> Workbook:
        """Import an `.xlsx` file into the app workbook model."""
        file_path = Path(path)
        try:
            formulas_wb = load_workbook(filename=file_path, data_only=False)
            values_wb = load_workbook(filename=file_path, data_only=True)
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise WorkbookConversionError(f"Failed to read Excel file: {path}") from exc

        workbook = Workbook(name=file_path.stem or "Imported Workbook")
        workbook.sheets = []

        for sheet_index, source_sheet in enumerate(formulas_wb.worksheets):
            imported_sheet = workbook.add_sheet(source_sheet.title)
            imported_sheet.metadata["freeze_panes"] = str(source_sheet.freeze_panes) if source_sheet.freeze_panes else None
            imported_sheet.metadata["merged_ranges"] = [str(item) for item in source_sheet.merged_cells.ranges]
            imported_sheet.metadata["auto_filter"] = source_sheet.auto_filter.ref
            imported_sheet.metadata["column_widths"] = {
                key: value.width for key, value in source_sheet.column_dimensions.items() if value.width is not None
            }
            imported_sheet.metadata["row_heights"] = {
                str(key): value.height for key, value in source_sheet.row_dimensions.items() if value.height is not None
            }
            value_sheet = values_wb.worksheets[sheet_index] if sheet_index < len(values_wb.worksheets) else None

            max_row = source_sheet.max_row or 0
            max_col = source_sheet.max_column or 0

            for row in range(1, max_row + 1):
                for col in range(1, max_col + 1):
                    excel_cell = source_sheet.cell(row=row, column=col)
                    value_cell = value_sheet.cell(row=row, column=col) if value_sheet is not None else None
                    address = f"{get_column_letter(col)}{row}"

                    formatting = self._extract_formatting(excel_cell)
                    has_content = excel_cell.value is not None
                    if not has_content and not formatting:
                        continue

                    model_cell = imported_sheet.get_cell(address)
                    if isinstance(excel_cell.value, str) and excel_cell.value.startswith("="):
                        model_cell.formula = excel_cell.value
                        model_cell.value = value_cell.value if value_cell is not None else None
                    else:
                        model_cell.value = excel_cell.value
                        model_cell.formula = None

                    if formatting:
                        model_cell.formatting = formatting

        if not workbook.sheets:
            workbook.add_sheet("Sheet1")
        workbook.active_sheet_index = 0
        return workbook

    def export_xlsx(self, path: str, workbook: Workbook) -> None:
        """Export app workbook model data to `.xlsx`."""
        file_path = Path(path)
        try:
            target = OpenPyxlWorkbook()
            default_sheet = target.active
            target.remove(default_sheet)

            existing_names: set[str] = set()
            for sheet in workbook.sheets:
                sheet_name = self._make_unique_sheet_name(sheet.name or "Sheet", existing_names)
                existing_names.add(sheet_name)
                target_sheet = target.create_sheet(title=sheet_name)

                freeze_panes = sheet.metadata.get("freeze_panes")
                if freeze_panes:
                    target_sheet.freeze_panes = freeze_panes
                for merged_range in sheet.metadata.get("merged_ranges", []):
                    target_sheet.merge_cells(str(merged_range))
                if sheet.metadata.get("auto_filter"):
                    target_sheet.auto_filter.ref = str(sheet.metadata["auto_filter"])
                for column, width in sheet.metadata.get("column_widths", {}).items():
                    target_sheet.column_dimensions[str(column)].width = float(width)
                for row, height in sheet.metadata.get("row_heights", {}).items():
                    target_sheet.row_dimensions[int(row)].height = float(height)

                for address, cell in sheet.cells.items():
                    target_cell = target_sheet[address]
                    if cell.formula:
                        target_cell.value = cell.formula
                    else:
                        target_cell.value = cell.value
                    self._apply_formatting(target_cell, cell.formatting)

            if not workbook.sheets:
                target.create_sheet(title="Sheet1")

            target.save(file_path)
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise WorkbookConversionError(f"Failed to write Excel file: {path}") from exc

    def import_csv(self, path: str) -> Workbook:
        """Import a `.csv` file as a single-sheet workbook."""
        file_path = Path(path)
        workbook = Workbook(name=file_path.stem or "Imported CSV")
        workbook.sheets = []
        sheet = workbook.add_sheet(file_path.stem[:31] or "Sheet1")

        try:
            with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle)
                for row_index, row_values in enumerate(reader, start=1):
                    for col_index, raw_value in enumerate(row_values, start=1):
                        if raw_value == "":
                            continue
                        address = f"{get_column_letter(col_index)}{row_index}"
                        cell = sheet.get_cell(address)
                        if raw_value.startswith("="):
                            cell.formula = raw_value
                            cell.value = None
                        else:
                            cell.value = self._infer_scalar(raw_value)
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise WorkbookConversionError(f"Failed to read CSV file: {path}") from exc

        return workbook

    def export_csv(self, path: str, workbook: Workbook, sheet_index: int = 0) -> None:
        """Export a worksheet to `.csv`.

        CSV is single-sheet only; by default the active/first sheet is exported.
        """
        if not workbook.sheets:
            raise WorkbookConversionError("Cannot export CSV from an empty workbook")

        normalized_index = max(0, min(sheet_index, len(workbook.sheets) - 1))
        sheet = workbook.sheets[normalized_index]
        if not sheet.cells:
            Path(path).write_text("", encoding="utf-8")
            return

        max_row = 0
        max_col = 0
        for address in sheet.cells:
            row, col = self._address_to_row_col(address)
            max_row = max(max_row, row)
            max_col = max(max_col, col)

        try:
            with Path(path).open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                for row_index in range(1, max_row + 1):
                    row_values: list[Any] = []
                    for col_index in range(1, max_col + 1):
                        address = f"{get_column_letter(col_index)}{row_index}"
                        cell = sheet.cells.get(address)
                        if cell is None:
                            row_values.append("")
                        elif cell.formula:
                            row_values.append(cell.formula)
                        elif cell.value is None:
                            row_values.append("")
                        else:
                            row_values.append(cell.value)
                    writer.writerow(row_values)
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise WorkbookConversionError(f"Failed to write CSV file: {path}") from exc

    @staticmethod
    def _extract_formatting(excel_cell) -> dict[str, Any]:
        formatting: dict[str, Any] = {}

        if excel_cell.number_format and excel_cell.number_format != "General":
            formatting["number_format"] = excel_cell.number_format

        font = excel_cell.font
        if font is not None:
            if font.bold:
                formatting["bold"] = True
            if font.italic:
                formatting["italic"] = True
            if font.underline and font.underline != "none":
                formatting["underline"] = True
            color = getattr(font, "color", None)
            rgb = getattr(color, "rgb", None)
            if isinstance(rgb, str) and rgb:
                formatting["font_color"] = rgb

        fill = excel_cell.fill
        if fill is not None and getattr(fill, "fill_type", None) == "solid":
            fg_color = getattr(fill, "fgColor", None)
            fg_rgb = getattr(fg_color, "rgb", None)
            if isinstance(fg_rgb, str) and fg_rgb:
                formatting["fill_color"] = fg_rgb

        alignment = excel_cell.alignment
        if alignment is not None:
            if alignment.horizontal:
                formatting["horizontal_align"] = alignment.horizontal
            if alignment.vertical:
                formatting["vertical_align"] = alignment.vertical
            if alignment.wrap_text:
                formatting["wrap_text"] = True

        return formatting

    @staticmethod
    def _apply_formatting(target_cell, formatting: dict[str, Any]) -> None:
        if not formatting:
            return

        target_cell.number_format = str(formatting.get("number_format", target_cell.number_format))

        has_font_updates = any(
            key in formatting for key in ("bold", "italic", "underline", "font_color")
        )
        if has_font_updates:
            color_value = formatting.get("font_color")
            target_cell.font = Font(
                bold=bool(formatting.get("bold", False)),
                italic=bool(formatting.get("italic", False)),
                underline="single" if formatting.get("underline") else None,
                color=color_value if isinstance(color_value, str) else None,
            )

        fill_color = formatting.get("fill_color")
        if isinstance(fill_color, str) and fill_color:
            target_cell.fill = PatternFill(fill_type="solid", fgColor=fill_color)

        has_alignment_updates = any(
            key in formatting for key in ("horizontal_align", "vertical_align", "wrap_text")
        )
        if has_alignment_updates:
            target_cell.alignment = Alignment(
                horizontal=formatting.get("horizontal_align"),
                vertical=formatting.get("vertical_align"),
                wrap_text=bool(formatting.get("wrap_text", False)),
            )

    @staticmethod
    def _address_to_row_col(address: str) -> tuple[int, int]:
        letters = ""
        digits = ""
        for char in address.upper():
            if char.isalpha():
                letters += char
            elif char.isdigit():
                digits += char

        row = int(digits) if digits else 1
        col = 0
        for char in letters:
            col = col * 26 + (ord(char) - ord("A") + 1)
        return row, max(1, col)

    @staticmethod
    def _infer_scalar(raw_value: str) -> Any:
        text = raw_value.strip()
        if text == "":
            return ""

        lower = text.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False

        try:
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                return int(text)
            return float(text)
        except ValueError:
            return raw_value

    @staticmethod
    def _make_unique_sheet_name(candidate: str, existing_names: set[str]) -> str:
        sanitized = "".join("_" if char in _INVALID_SHEET_CHARS else char for char in candidate).strip()
        if not sanitized:
            sanitized = "Sheet"
        base = sanitized[:31]
        if base not in existing_names:
            return base

        suffix = 2
        while True:
            suffix_text = f" ({suffix})"
            trimmed = base[: max(1, 31 - len(suffix_text))]
            attempt = f"{trimmed}{suffix_text}"
            if attempt not in existing_names:
                return attempt
            suffix += 1
