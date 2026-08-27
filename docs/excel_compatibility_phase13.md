# Phase 13 Excel compatibility

## Named ranges

Use **Data → Named Ranges** (`Ctrl+F3`) to create or remove workbook- and worksheet-scoped names. Names can refer to a cell or rectangular range and are available to formulas, for example `=SUM(SalesValues)`. Named ranges participate in dependency recalculation and are imported from and exported to XLSX.

## Conditional formatting

Select a range and use **Format → Conditional Formatting**. The first editable rules support equal/not-equal, greater/less comparisons and between. Matching fill, font colour and bold styling render in the desktop grid and export as native Excel conditional formatting. Clearing rules is undoable.

Imported conditional-format types that the app cannot edit remain in the preserved OOXML template. They are not silently rewritten into a less capable rule.

## Charts

Select a rectangular table containing a header row, category column and one or more numeric series, then use **Data → Create Chart** (`Alt+F1`). Phase 13 creates column, line and pie chart definitions. Charts are stored in worksheet metadata and exported as native Excel charts; unsupported imported drawings and chart parts remain protected by the OOXML preservation layer.

## Added formulas

- Statistical: `MEDIAN`, `PRODUCT`, `STDEV.S`, `STDEV.P`, `VAR.S`, `VAR.P`, `LARGE`, `SMALL`, `RANK.EQ`
- Rounding: `ROUNDUP`, `ROUNDDOWN`, `CEILING`, `FLOOR`
- Text: `FIND`, `SEARCH`, `REPLACE`, `VALUE`
- Dates: `WEEKDAY`, `NETWORKDAYS`

The formula registry accepts both Excel dotted names such as `STDEV.S` and Python-friendly underscore aliases such as `STDEV_S`.
