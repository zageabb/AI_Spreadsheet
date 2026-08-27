# OOXML preservation and custom Python functions

## OOXML preservation layer

When an Excel workbook is imported, `OOXMLPreservationLayer` validates the ZIP package, enforces the configured size limit, calculates a SHA-256 checksum, and embeds the original package in workbook metadata. Excel export opens that verified package as a template and applies current workbook cells, formulas, formatting, tables and validation rules in place.

This keeps supported charts, drawings, images, embedded relationships and workbook-level package content attached during normal import/edit/export workflows. The checksum and expanded-size checks reject corrupt or suspicious stored packages. Set `OOXML_PASSTHROUGH_MAX_BYTES` to control the compressed package limit; the default is 50 MiB.

The snapshot makes JSON workbook files larger because the original package is Base64 encoded. CSV imports and newly created workbooks do not carry an OOXML snapshot and are exported through the normal clean-workbook path.

## Custom Python formula editor

Open **Tools → Custom Python Functions**. Give the module a name and define one or more uppercase Python functions:

```python
def ADD_MARGIN(value, percent=10):
    return float(value) * (1 + float(percent) / 100)
```

After saving, use it immediately in a cell:

```text
=ADD_MARGIN(A1, 15)
```

The editor validates source before saving and blocks imports, file access, network/process modules, dynamic code execution, dunder access and other unsafe constructs. `math`, `statistics`, and a limited set of normal calculation built-ins are available. Modules are saved under `CUSTOM_FUNCTIONS_DIR` (`plugins/user` by default) and loaded again at startup.

Custom code still runs in the desktop application process. Only save functions you understand. Manually installed legacy files directly under `plugins/` remain trusted plugins and are not rewritten by this validator.
