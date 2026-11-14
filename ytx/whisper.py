"""Transcribe locally with whisper.cpp the videos without subtitles, find the transcripts stuck in loops, redo them."""
import json
import shutil
import subprocess
import time
from collections import deque

from .projet import MODELES, VAD_MODEL, WHISPER_MODEL

AUDIO_EXT = (".webm", ".m4a", ".opus", ".mp3", ".ogg")
MAX_LOOP = 0.15
MIN_DISTINCT = 12
URLS = {
    WHISPER_MODEL: f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{WHISPER_MODEL}",
    VAD_MODEL: f"https://huggingface.co/ggml-org/whisper-vad/resolve/main/{VAD_MODEL}",
}


def modele(name):
    path = MODELES / name
    if not path.exists():
        raise SystemExit(f"modèle {path} absent : lancer « python3 -m ytx modeles » (ou définir YTX_MODELES)")
    return path


def telecharger_modeles():
    MODELES.mkdir(parents=True, exist_ok=True)
    for name, url in URLS.items():
        path = MODELES / name
        if path.exists():
            print(f"déjà là : {path}")
            continue
        print(f"téléchargement de {url}", flush=True)
        partial = path.with_suffix(".part")
        subprocess.run(["curl", "-L", "--fail", "-o", str(partial), url], check=True)
        partial.rename(path)


def _audio(projet, video_id, info=False):
    found = next((p for p in projet.audio.glob(f"{video_id}.*") if p.suffix in AUDIO_EXT), None)
    if found:
        return found, ""
    args = ["-f", "bestaudio", "--no-playlist", "-o", str(projet.audio / "%(id)s.%(ext)s")]
    if info:
        args += ["--write-info-json", "-o", "infojson:" + str(projet.info / "%(id)s.%(ext)s")]
    result = projet.yt_dlp(*args, "--", video_id)
    found = next((p for p in projet.audio.glob(f"{video_id}.*") if p.suffix in AUDIO_EXT), None)
    return found, result.stderr.strip()[-200:]


def _whisper(projet, video_id, source, robust):
    """Run whisper-cli on an audio file into data/whisper/<id>.json. robust: no context carried over, voice detection."""
    wav = projet.audio / f"{video_id}.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(source), "-ar", "16000", "-ac", "1",
                    "-c:a", "pcm_s16le", str(wav)])
    cmd = ["whisper-cli", "-m", str(modele(WHISPER_MODEL)), "-l", projet.config["langue"]]
    if robust:
        cmd += ["-mc", "0", "--vad", "-vm", str(modele(VAD_MODEL))]
    if projet.config["vocabulaire"]:
        # The channel's jargon as initial prompt, so "bullish FVG" is not heard as "busy". Carried over to every
        # window, since the robust mode keeps no context.
        cmd += ["--prompt", projet.config["vocabulaire"], "--carry-initial-prompt"]
    result = subprocess.run(cmd + ["-oj", "-of", str(projet.whisper / video_id), "-f", str(wav), "-np"],
                            capture_output=True, text=True)
    wav.unlink(missing_ok=True)
    return result


def transcrire(projet):
    for d in (projet.audio, projet.whisper, projet.info):
        d.mkdir(parents=True, exist_ok=True)
    modele(WHISPER_MODEL)
    missing = [v for v in projet.selection() if not projet.sous_titres(v.id) and not projet.whisper_json(v.id)]
    print(f"{len(missing)} vidéos à transcrire avec Whisper", flush=True)
    failed = []
    for n, v in enumerate(missing, 1):
        start = time.time()
        source, error = _audio(projet, v.id, info=True)
        if source:
            result = _whisper(projet, v.id, source, robust=False)
            error = None if projet.whisper_json(v.id) else "whisper : " + result.stderr.strip()[-200:]
            if not error:
                source.unlink()
        else:
            error = "audio : " + error
        if error:
            failed.append(v.id)
            print(f"[{n}/{len(missing)}] ÉCHEC {v.titre} : {error}", flush=True)
        else:
            print(f"[{n}/{len(missing)}] ok en {time.time() - start:.0f} s : {v.titre}", flush=True)
        if n < len(missing):
            projet.pause("pause_audio_s")
    print(f"terminé : {len(missing) - len(failed)}/{len(missing)} transcrites", flush=True)
    if failed:
        print("échecs : " + " ".join(failed), flush=True)


def qualite(path):
    """(share of the duration in looping segments, distinct words per minute, minutes).

    A segment loops if its text already appeared among the 20 segments before it.
    """
    segments = json.loads(path.read_text())["transcription"]
    recent, looped, total, words = deque(maxlen=20), 0, 0, set()
    for seg in segments:
        length = seg["offsets"]["to"] - seg["offsets"]["from"]
        text = " ".join(seg["text"].lower().split())
        total += length
        if text and text in recent:
            looped += length
        recent.append(text)
        words.update(text.split())
    minutes = max(total / 60000, 1)
    return looped / max(total, 1), len(words) / minutes, minutes


def verifier(projet):
    """Write data/whisper_bad.tsv: the Whisper transcripts stuck in loops or with very few distinct words."""
    titles = {v.id: v for v in projet.selection()}
    bad, count = [], 0
    for path in sorted(projet.whisper.glob("*.json")):
        count += 1
        loop, distinct, minutes = qualite(path)
        if loop > MAX_LOOP or distinct < MIN_DISTINCT:
            v = titles.get(path.stem)
            bad.append((loop, path.stem, distinct, minutes, v.categorie if v else "?", v.titre if v else "?"))
    bad.sort(reverse=True)
    projet.whisper_bad_tsv.parent.mkdir(parents=True, exist_ok=True)
    projet.whisper_bad_tsv.write_text("".join(f"{b[1]}\n" for b in bad))
    print(f"{projet.nom} : {count} transcriptions Whisper, {len(bad)} à refaire")
    for loop, video, distinct, minutes, cat, title in bad:
        print(f"  {video}  boucle {100 * loop:3.0f} %  {distinct:5.1f} mots distincts/min  {minutes:4.0f} min  "
              f"{cat:<10} {title[:50]}")
    return [b[1] for b in bad]


def refaire(projet, ids=None):
    """Transcribe again without context and with voice detection, keeping the old result in data/whisper_old."""
    if ids is None:
        ids = projet.whisper_bad_tsv.read_text().split() if projet.whisper_bad_tsv.exists() else []
    if not ids:
        print("rien à refaire")
        return
    modele(VAD_MODEL)
    projet.audio.mkdir(parents=True, exist_ok=True)
    projet.whisper_old.mkdir(parents=True, exist_ok=True)
    for video_id in ids:
        source, error = _audio(projet, video_id)
        if not source:
            print(f"audio introuvable {video_id} : {error}", flush=True)
            continue
        current = projet.whisper / f"{video_id}.json"
        if current.exists() and not (projet.whisper_old / current.name).exists():
            shutil.copy(current, projet.whisper_old / current.name)
        result = _whisper(projet, video_id, source, robust=True)
        source.unlink(missing_ok=True)
        print(f"refait {video_id} ({'ok' if result.returncode == 0 else 'échec'})", flush=True)
