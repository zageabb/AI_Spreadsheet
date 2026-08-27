"""Build and checksum a platform-specific desktop release directory."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "AI_Spreadsheet.spec"],
        cwd=root,
        check=True,
    )
    app_bundle = root / "dist" / "AI-Spreadsheet.app"
    release_dir = app_bundle if app_bundle.exists() else root / "dist" / "AI-Spreadsheet"
    archive = shutil.make_archive(str(root / "dist" / "AI-Spreadsheet"), "zip", release_dir)
    archive_path = Path(archive)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path = archive_path.with_suffix(f"{archive_path.suffix}.sha256")
    checksum_path.write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")
    print(f"Built {archive_path}")
    print(f"SHA-256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
