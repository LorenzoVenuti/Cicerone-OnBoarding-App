"""Automated tests on where the program reads and where it writes.

Getting these paths wrong does not show in development: it is discovered on the
computer of whoever uses the program, when the archive ends up somewhere that
disappears at the first update. Hence the tests.
"""

import unittest
from pathlib import Path
from unittest.mock import patch

from app import paths

RADICE = Path(__file__).resolve().parent.parent


class DataFolderTests(unittest.TestCase):
    """`data_folder` must never end up inside the bundle."""

    def test_in_development_data_stays_in_the_project_folder(self) -> None:
        with patch.object(paths, "FROZEN", False):
            self.assertEqual(paths.data_folder(), RADICE)

    def test_packaged_on_macos_data_goes_to_application_support(self) -> None:
        eseguibile = "/Applications/Cicerone.app/Contents/MacOS/Cicerone"
        with patch.object(paths, "FROZEN", True), \
             patch.object(paths.sys, "platform", "darwin"), \
             patch.object(paths.sys, "executable", eseguibile):
            atteso = Path.home() / "Library" / "Application Support" / "Cicerone"
            self.assertEqual(paths.data_folder(), atteso)

    def test_on_macos_it_never_writes_inside_the_bundle(self) -> None:
        """The regression that matters: data inside the .app would vanish."""
        eseguibile = "/Applications/Cicerone.app/Contents/MacOS/Cicerone"
        with patch.object(paths, "FROZEN", True), \
             patch.object(paths.sys, "platform", "darwin"), \
             patch.object(paths.sys, "executable", eseguibile):
            self.assertNotIn(".app/", str(paths.data_folder()))

    def test_packaged_on_windows_data_stays_next_to_the_exe(self) -> None:
        """On Windows the archive is already there: moving it would abandon it."""
        eseguibile = str(Path("/opt/piano/Cicerone.exe"))
        with patch.object(paths, "FROZEN", True), \
             patch.object(paths.sys, "platform", "win32"), \
             patch.object(paths.sys, "executable", eseguibile):
            self.assertEqual(
                paths.data_folder(), Path(eseguibile).resolve().parent
            )


class ResourceFolderTests(unittest.TestCase):
    def test_in_development_resources_live_in_the_project(self) -> None:
        with patch.object(paths, "FROZEN", False):
            self.assertEqual(paths.resource_folder(), RADICE)
            self.assertTrue((paths.resource_folder() / "app" / "web").is_dir())


if __name__ == "__main__":
    unittest.main()
