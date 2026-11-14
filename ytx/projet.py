"""A channel project: its chaine.json, the folders the pipeline writes to, and the video listings."""
import json
import os
import random
import re
import subprocess
import time
from collections import namedtuple
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAINES = ROOT / "chaines"
MODELES = Path(os.environ.get("YTX_MODELES", ROOT / "modeles"))
WHISPER_MODEL = "ggml-large-v3-turbo-q5_0.bin"
VAD_MODEL = "ggml-silero-v5.1.2.bin"

DEFAUTS = {
    "nom": None,
    "sources": [],
    "onglets": ["videos", "streams"],
    "langue": "en",
    "vocabulaire": "",
    "duree_min_s": 120,
    "categories": [],
    "defaut": "formation",
    "forcer": {},
    "cookies_navigateur": None,
    "pause_sous_titres_s": [35, 60],
    "passages_sous_titres": 4,
    "pause_entre_passages_s": 1800,
    "pause_audio_s": [20, 40],
    "pause_videos_s": [10, 25],
    "ocr_toutes_les_s": 10,
    "garder_videos": False,
}

# listing.tsv: everything the channel tabs list. selection.tsv: what the categories keep, in the same columns plus
# the category, which is what every later step reads.
Video = namedtuple("Video", "id duree vues titre chaine onglet categorie")


class Projet:
    def __init__(self, nom):
        path = Path(nom)
        self.dir = path if (path / "chaine.json").exists() else CHAINES / nom
        self.fichier = self.dir / "chaine.json"
        if not self.fichier.exists():
            raise SystemExit(f"{self.fichier} introuvable. Créer la chaîne : python3 -m ytx nouvelle {path.name} @chaine")
        self.config = {**DEFAUTS, **json.loads(self.fichier.read_text())}
        self.nom = self.config["nom"] or self.dir.name
        self.data = self.dir / "data"
        self.raw = self.data / "raw"
        self.audio = self.data / "audio"
        self.whisper = self.data / "whisper"
        self.whisper_old = self.data / "whisper_old"
        self.info = self.data / "info"
        self.video = self.data / "video"
        self.ocr = self.data / "ocr"
        self.transcripts = self.dir / "transcripts"
        self.fiches = self.dir / "fiches"
        self.listing_tsv = self.data / "listing.tsv"
        self.selection_tsv = self.data / "selection.tsv"
        self.exclues_tsv = self.data / "exclues.tsv"
        self.whisper_bad_tsv = self.data / "whisper_bad.tsv"
        self.chronologie_tsv = self.data / "chronologie.tsv"
        self.affirmations_tsv = self.data / "affirmations.tsv"
        self._categories = [(c["nom"], re.compile(c["motif"], re.I), c.get("exclure", False))
                            for c in self.config["categories"]]

    # Selection ---------------------------------------------------------------------------------------------------

    def categorie(self, video_id, titre):
        """Category of a title, or None when it is left out. A forced value wins, then the first matching pattern."""
        forced = self.config["forcer"]
        if video_id in forced:
            return forced[video_id]
        for nom, motif, exclure in self._categories:
            if motif.search(titre):
                return None if exclure else nom
        return self.config["defaut"]

    def priorite(self, video):
        """Sort key: categories in their config order, the default one last, shortest videos first."""
        noms = [c["nom"] for c in self.config["categories"] if not c.get("exclure")]
        rang = noms.index(video.categorie) if video.categorie in noms else len(noms)
        return rang, video.duree

    def listing(self):
        return _read(self.listing_tsv)

    def selection(self):
        if not self.selection_tsv.exists():
            raise SystemExit(f"{self.selection_tsv} absent : lancer d'abord « python3 -m ytx selectionner {self.dir.name} »")
        return _read(self.selection_tsv)

    # Files -------------------------------------------------------------------------------------------------------

    def sous_titres(self, video_id):
        """The subtitle file of a video, manual or automatic, in the channel language, or None."""
        langue = self.config["langue"]
        for name in (f"{video_id}.{langue}.json3", f"{video_id}.{langue}-orig.json3"):
            if (self.raw / name).exists():
                return self.raw / name
        return next(iter(sorted(self.raw.glob(f"{video_id}.{langue}*.json3"))), None)

    def whisper_json(self, video_id):
        path = self.whisper / f"{video_id}.json"
        return path if path.exists() else None

    def date(self, video_id):
        """Upload date YYYY-MM-DD from data/info/<id>.info.json, written with the subtitles or the audio; else ''."""
        path = self.info / f"{video_id}.info.json"
        if not path.exists():
            return ""
        day = json.loads(path.read_text()).get("upload_date") or ""
        return f"{day[:4]}-{day[4:6]}-{day[6:]}" if len(day) == 8 else ""

    def chronologie(self):
        """The selection in upload order, undated videos last."""
        return sorted(self.selection(), key=lambda v: (self.date(v.id) or "9999", v.id))

    def fichier_video(self, video_id):
        return next((p for p in (self.video / f"{video_id}.mp4", self.video / f"{video_id}.webm") if p.exists()), None)

    # yt-dlp ------------------------------------------------------------------------------------------------------

    def yt_dlp(self, *args):
        cmd = ["yt-dlp"]
        if self.config["cookies_navigateur"]:
            cmd += ["--cookies-from-browser", self.config["cookies_navigateur"]]
        return subprocess.run(cmd + list(args), capture_output=True, text=True)

    def pause(self, cle):
        time.sleep(random.uniform(*self.config[cle]))


def write_tsv(path, videos):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join("\t".join(str(x if x is not None else "") for x in v) + "\n" for v in videos))


def _read(path):
    if not path.exists():
        return []
    videos = []
    for line in path.read_text().splitlines():
        row = line.split("\t")
        row += [""] * (len(Video._fields) - len(row))
        videos.append(Video(row[0], int(row[1] or 0), int(row[2] or 0), row[3], row[4], row[5], row[6] or None))
    return videos


def hms(seconds):
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
