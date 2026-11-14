"""Optional, macOS only: download each video without sound and read the text on screen every few seconds.

For channels that show what they say (charts, slides, code). One JSON line per frame in data/ocr/<id>.jsonl, with the
text and its box in pixels. The OCR is the local Vision framework; nothing leaves the machine.
"""
import json
import platform
import subprocess
import tempfile
import time
from pathlib import Path

from .projet import ROOT

SWIFT = Path(__file__).resolve().parent / "ocr.swift"
BINARY = ROOT / "build" / "ocr_bin"
BATCH = 50


def ocr_binary():
    if platform.system() != "Darwin":
        raise SystemExit("l'OCR utilise le framework Vision de macOS : commande indisponible sur ce système")
    if not BINARY.exists() or BINARY.stat().st_mtime < SWIFT.stat().st_mtime:
        BINARY.parent.mkdir(parents=True, exist_ok=True)
        print("compilation de ocr.swift", flush=True)
        subprocess.run(["swiftc", "-O", str(SWIFT), "-o", str(BINARY)], check=True)
    return BINARY


def scan(path, out, step):
    """OCR one frame every `step` seconds of a video file into out. Returns the number of frames."""
    binary = ocr_binary()
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(path), "-vf", f"fps=1/{step}",
                        "-q:v", "2", f"{tmp}/%06d.jpg"], check=True)
        frames = sorted(Path(tmp).glob("*.jpg"))
        partial = out.with_suffix(".part")
        with partial.open("w") as f:
            for i in range(0, len(frames), BATCH):
                result = subprocess.run([str(binary), *map(str, frames[i:i + BATCH])], capture_output=True, text=True)
                for line in result.stdout.splitlines():
                    d = json.loads(line)
                    d["s"] = (int(Path(d.pop("file")).stem) - 1) * step
                    d["items"] = [x for x in d["items"] if x["t"].strip()]
                    f.write(json.dumps(d, ensure_ascii=False) + "\n")
        partial.rename(out)
    return len(frames)


def images(projet, garder=None):
    """For each selected video without OCR, in priority order: download, read, then delete the video unless kept."""
    garder = projet.config["garder_videos"] if garder is None else garder
    ocr_binary()
    projet.video.mkdir(parents=True, exist_ok=True)
    projet.ocr.mkdir(parents=True, exist_ok=True)
    todo = [v for v in projet.selection() if not (projet.ocr / f"{v.id}.jsonl").exists()]
    print(f"{len(todo)} vidéos à lire", flush=True)
    for n, v in enumerate(todo, 1):
        path = projet.fichier_video(v.id)
        if not path:
            result = projet.yt_dlp("-f", "bv*[height<=1080][ext=mp4]/bv*[height<=1080]", "--no-playlist",
                                   "-o", str(projet.video / "%(id)s.%(ext)s"), "--", v.id)
            path = projet.fichier_video(v.id)
            if not path:
                print(f"[{n}/{len(todo)}] ÉCHEC {v.titre[:60]} : {result.stderr.strip()[-160:]}", flush=True)
                continue
            projet.pause("pause_videos_s")
        start = time.time()
        frames = scan(path, projet.ocr / f"{v.id}.jsonl", projet.config["ocr_toutes_les_s"])
        if not garder:
            path.unlink()
        print(f"[{n}/{len(todo)}] {v.categorie} {v.titre[:55]} : {frames} images en {time.time() - start:.0f} s",
              flush=True)
