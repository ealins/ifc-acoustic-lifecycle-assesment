from __future__ import annotations

import json
import re
from pathlib import Path

from .export import finalize_package
from .models import FairAcousticPackage


class PackageRepository:
    """Filesystem persistence for generated FAIR packages and their source assets."""

    def __init__(self, root: str | Path = "packages"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _folder(self, package_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", package_id):
            raise ValueError("Unsafe package identifier")
        return self.root / package_id

    def save(self, package: FairAcousticPackage) -> Path:
        finalize_package(package)
        folder = self._folder(package.package_id)
        folder.mkdir(parents=True, exist_ok=True)
        for name, content in package.assets.items():
            if Path(name).name != name:
                raise ValueError(f"Package asset must be a filename, not a path: {name}")
            (folder / name).write_bytes(content)
        (folder / "package.json").write_text(
            json.dumps(package.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return folder

    def load(self, package_id: str) -> FairAcousticPackage:
        folder = self._folder(package_id)
        payload = json.loads((folder / "package.json").read_text(encoding="utf-8"))
        package = FairAcousticPackage.from_dict(payload)
        package.assets = {
            path.name: path.read_bytes()
            for path in folder.iterdir()
            if path.is_file() and path.name != "package.json"
        }
        return package

    def list_packages(self) -> list[FairAcousticPackage]:
        packages: list[FairAcousticPackage] = []
        for folder in self.root.iterdir():
            if folder.is_dir() and (folder / "package.json").exists():
                try:
                    packages.append(self.load(folder.name))
                except Exception:
                    continue
        return sorted(packages, key=lambda package: package.created, reverse=True)

    def delete(self, package_id: str) -> None:
        folder = self._folder(package_id)
        if not folder.exists():
            return
        for path in folder.iterdir():
            if path.is_file():
                path.unlink()
        folder.rmdir()
