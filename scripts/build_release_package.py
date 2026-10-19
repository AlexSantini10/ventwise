"""Build the distributable VentWise integration ZIP package."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


_ROOT_FILES = ("README.md", "LICENSE", "NOTICE", "hacs.json")


def _package_files(source_path: Path) -> list[tuple[Path, Path]]:
    """Return source and archive paths for every distributable file."""
    integration_path = source_path / "custom_components" / "ventwise"
    if not integration_path.is_dir():
        msg = f"VentWise integration directory not found: {integration_path}"
        raise FileNotFoundError(msg)

    files = [
        (path, path.relative_to(integration_path))
        for path in integration_path.rglob("*")
        if path.is_file()
        and path.name != ".gitkeep"
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    ]

    for name in _ROOT_FILES:
        path = source_path / name
        if not path.is_file():
            msg = f"Required release file not found: {path}"
            raise FileNotFoundError(msg)
        files.append((path, Path(name)))

    return sorted(files, key=lambda item: item[1].as_posix())


def build_package(source_path: Path, output_path: Path) -> None:
    """Create a release ZIP from *source_path* at *output_path*."""
    source_path = source_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        for source, archive_path in _package_files(source_path):
            archive.write(source, archive_path.as_posix())


def main() -> None:
    """Parse command-line arguments and build the package."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-path",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root to package (default: this script's repository).",
    )
    parser.add_argument(
        "--output-path",
        required=True,
        type=Path,
        help="Destination ZIP path.",
    )
    arguments = parser.parse_args()
    build_package(arguments.source_path, arguments.output_path)


if __name__ == "__main__":
    main()
