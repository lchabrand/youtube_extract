"""Turn the subtitles (or the Whisper output) into readable transcripts/<id>.md, timestamped every minute or so."""
import json

from .projet import hms

BLOCK_MS = 60_000


def segments(projet, video_id):
    """(start_ms, text) from the YouTube subtitles, or from Whisper for the videos that have none."""
    subs = projet.sous_titres(video_id)
    if subs:
        for event in json.loads(subs.read_text()).get("events", []):
            yield event.get("tStartMs", 0), "".join(s.get("utf8", "") for s in event.get("segs", []))
    else:
        for seg in json.loads(projet.whisper_json(video_id).read_text())["transcription"]:
            yield seg["offsets"]["from"], seg["text"]


def blocks(projet, video_id):
    current_start, words = None, []
    for start, text in segments(projet, video_id):
        text = text.strip()
        if not text:
            continue
        if current_start is None:
            current_start = start
        elif start - current_start >= BLOCK_MS:
            yield current_start, " ".join(words)
            current_start, words = start, []
        words.append(" ".join(text.split()))
    if words:
        yield current_start, " ".join(words)


def construire(projet):
    projet.transcripts.mkdir(parents=True, exist_ok=True)
    videos = projet.selection()
    done, total_words, missing = 0, 0, []
    for v in videos:
        has_subs = projet.sous_titres(v.id) is not None
        if not has_subs and not projet.whisper_json(v.id):
            missing.append(v.id)
            continue
        url = f"https://www.youtube.com/watch?v={v.id}"
        lines = [f"# {v.titre}", "", f"- Categorie : {v.categorie}", f"- Duree : {v.duree // 60} min",
                 f"- Source : {'sous-titres YouTube' if has_subs else 'Whisper'}", f"- Lien : {url}",
                 f"- Chaine : {v.chaine}", ""]
        words = 0
        for start, text in blocks(projet, v.id):
            lines.append(f"[{hms(start // 1000)}]({url}&t={start // 1000}s) {text}\n")
            words += len(text.split())
        (projet.transcripts / f"{v.id}.md").write_text("\n".join(lines))
        done += 1
        total_words += words
        ratio = words / max(v.duree, 1) * 60
        print(f"{words:6d} mots  {ratio:4.0f} m/min  {v.titre[:70]}")
    print(f"{done}/{len(videos)} transcriptions, {total_words} mots")
    if missing:
        print(f"{len(missing)} sans sous-titres ni Whisper : lancer « python3 -m ytx whisper {projet.dir.name} »")
