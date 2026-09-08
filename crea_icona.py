"""Trasforma il logo in icona per l'applicazione.

    .venv/bin/python crea_icona.py logo.png

Produce `app/risorse/Cicerone.icns` (macOS) e, se serve, `Cicerone.ico`
(Windows). Si lancia a mano quando il logo cambia: il risultato viene
versionato, cosi' chi costruisce il pacchetto non deve rifare questo passaggio.

Due ritocchi che sembrano estetici e non lo sono:

- **si ritaglia il bordo uniforme.** I generatori di immagini consegnano
  l'icona centrata dentro un rettangolo di sfondo. Lasciato com'e', nel Dock si
  vedrebbe un quadrato di colore attorno all'icona;
- **si arrotondano gli angoli in trasparenza.** macOS non ritaglia da solo:
  un'icona quadrata resta quadrata, e si nota fra le altre.

Serve Pillow, che e' una dipendenza di questo script e non dell'applicazione:
non va aggiunta a requirements.txt, o finirebbe dentro il pacchetto per niente.
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

DESTINAZIONE = Path("app/risorse")
# Le misure che macOS si aspetta dentro un .iconset.
MISURE = [
    (16, "icon_16x16.png"), (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"), (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"), (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"), (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"), (1024, "icon_512x512@2x.png"),
]
# Apple arrotonda gli angoli a circa un quinto del lato.
RAGGIO = 0.225


def ritaglia_bordo(immagine: Image.Image, tolleranza: int = 12) -> Image.Image:
    """Toglie la cornice di colore uniforme attorno al disegno."""
    grafica = immagine.convert("RGB")
    riferimento = grafica.getpixel((0, 0))

    def uguale(pixel) -> bool:
        return all(abs(a - b) <= tolleranza for a, b in zip(pixel, riferimento))

    larghezza, altezza = grafica.size
    alto, basso, sinistra, destra = 0, altezza - 1, 0, larghezza - 1
    while alto < basso and all(uguale(grafica.getpixel((x, alto))) for x in range(larghezza)):
        alto += 1
    while basso > alto and all(uguale(grafica.getpixel((x, basso))) for x in range(larghezza)):
        basso -= 1
    while sinistra < destra and all(uguale(grafica.getpixel((sinistra, y))) for y in range(alto, basso + 1)):
        sinistra += 1
    while destra > sinistra and all(uguale(grafica.getpixel((destra, y))) for y in range(alto, basso + 1)):
        destra -= 1

    if (destra - sinistra) < 16 or (basso - alto) < 16:
        return immagine          # niente bordo riconoscibile: si lascia com'e'
    return immagine.crop((sinistra, alto, destra + 1, basso + 1))


def quadra(immagine: Image.Image) -> Image.Image:
    """Rende l'immagine quadrata, centrandola senza deformarla."""
    larghezza, altezza = immagine.size
    if larghezza == altezza:
        return immagine
    lato = max(larghezza, altezza)
    tela = Image.new("RGBA", (lato, lato), (0, 0, 0, 0))
    tela.paste(immagine, ((lato - larghezza) // 2, (lato - altezza) // 2))
    return tela


def arrotonda(immagine: Image.Image) -> Image.Image:
    """Rende trasparente quello che sta fuori dagli angoli arrotondati."""
    immagine = immagine.convert("RGBA")
    lato = immagine.size[0]
    maschera = Image.new("L", (lato, lato), 0)
    ImageDraw.Draw(maschera).rounded_rectangle(
        (0, 0, lato - 1, lato - 1), radius=int(lato * RAGGIO), fill=255
    )
    ritagliata = Image.new("RGBA", (lato, lato), (0, 0, 0, 0))
    ritagliata.paste(immagine, (0, 0), maschera)
    return ritagliata


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    origine = Path(sys.argv[1])
    if not origine.exists():
        print(f"non trovo {origine}")
        return 1

    immagine = arrotonda(quadra(ritaglia_bordo(Image.open(origine))))
    immagine = immagine.resize((1024, 1024), Image.LANCZOS)
    DESTINAZIONE.mkdir(parents=True, exist_ok=True)

    cartella = DESTINAZIONE / "Cicerone.iconset"
    cartella.mkdir(exist_ok=True)
    for misura, nome in MISURE:
        immagine.resize((misura, misura), Image.LANCZOS).save(cartella / nome)

    icns = DESTINAZIONE / "Cicerone.icns"
    esito = subprocess.run(
        ["iconutil", "-c", "icns", str(cartella), "-o", str(icns)],
        capture_output=True, text=True,
    )
    if esito.returncode != 0:
        print("iconutil non ce l'ha fatta:", esito.stderr.strip())
        return 1
    for avanzo in cartella.iterdir():
        avanzo.unlink()
    cartella.rmdir()

    ico = DESTINAZIONE / "Cicerone.ico"
    immagine.save(ico, sizes=[(s, s) for s in (16, 32, 48, 64, 128, 256)])

    print(f"fatto: {icns} ({icns.stat().st_size // 1024} KB)")
    print(f"fatto: {ico} ({ico.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
