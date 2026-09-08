"""Test automatici su dove il programma legge e dove scrive.

Sbagliare questi percorsi non si vede in sviluppo: si scopre solo sul computer
di chi usa il programma, quando l'archivio finisce in un posto che sparisce al
primo aggiornamento. Da qui i test.
"""

import unittest
from pathlib import Path
from unittest.mock import patch

from app import percorsi

RADICE = Path(__file__).resolve().parent.parent


class CartellaDatiTests(unittest.TestCase):
    """`cartella_dati` non deve mai finire dentro il pacchetto."""

    def test_in_sviluppo_resta_nella_cartella_del_progetto(self) -> None:
        with patch.object(percorsi, "IMPACCHETTATO", False):
            self.assertEqual(percorsi.cartella_dati(), RADICE)

    def test_su_mac_impacchettato_va_in_application_support(self) -> None:
        eseguibile = "/Applications/Cicerone.app/Contents/MacOS/Cicerone"
        with patch.object(percorsi, "IMPACCHETTATO", True), \
             patch.object(percorsi.sys, "platform", "darwin"), \
             patch.object(percorsi.sys, "executable", eseguibile):
            atteso = Path.home() / "Library" / "Application Support" / "Cicerone"
            self.assertEqual(percorsi.cartella_dati(), atteso)

    def test_su_mac_non_scrive_mai_dentro_il_bundle(self) -> None:
        """La regressione che conta: i dati dentro il .app sparirebbero."""
        eseguibile = "/Applications/Cicerone.app/Contents/MacOS/Cicerone"
        with patch.object(percorsi, "IMPACCHETTATO", True), \
             patch.object(percorsi.sys, "platform", "darwin"), \
             patch.object(percorsi.sys, "executable", eseguibile):
            self.assertNotIn(".app/", str(percorsi.cartella_dati()))

    def test_su_windows_impacchettato_resta_accanto_all_eseguibile(self) -> None:
        """Su Windows l'archivio e' gia' li': spostarlo lo abbandonerebbe."""
        eseguibile = str(Path("/opt/piano/Cicerone.exe"))
        with patch.object(percorsi, "IMPACCHETTATO", True), \
             patch.object(percorsi.sys, "platform", "win32"), \
             patch.object(percorsi.sys, "executable", eseguibile):
            self.assertEqual(
                percorsi.cartella_dati(), Path(eseguibile).resolve().parent
            )


class CartellaRisorseTests(unittest.TestCase):
    def test_in_sviluppo_le_risorse_stanno_nel_progetto(self) -> None:
        with patch.object(percorsi, "IMPACCHETTATO", False):
            self.assertEqual(percorsi.cartella_risorse(), RADICE)
            self.assertTrue((percorsi.cartella_risorse() / "app" / "web").is_dir())


if __name__ == "__main__":
    unittest.main()
