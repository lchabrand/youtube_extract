"""Download the subtitles of the selected videos, slowly and resumable: YouTube blocks fast clients with HTTP 429."""
import time


def telecharger(projet):
    projet.raw.mkdir(parents=True, exist_ok=True)
    projet.info.mkdir(parents=True, exist_ok=True)
    langue = projet.config["langue"]
    videos = projet.selection()
    absent = set()  # videos YouTube answered for, without subtitles in that language: Whisper will do them
    for attempt in range(projet.config["passages_sous_titres"]):
        missing = [v for v in videos if v.id not in absent and not projet.sous_titres(v.id)]
        if not missing:
            break
        if attempt:
            print(f"pause de {projet.config['pause_entre_passages_s'] // 60} min avant le passage {attempt + 1}", flush=True)
            time.sleep(projet.config["pause_entre_passages_s"])
        print(f"passage {attempt + 1} : {len(missing)} vidéos sans sous-titres", flush=True)
        for v in missing:
            result = projet.yt_dlp(
                "--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", f"{langue},{langue}-orig",
                "--sub-format", "json3", "--write-info-json", "--sleep-requests", "2",
                "-o", str(projet.raw / "%(id)s.%(ext)s"), "-o", "infojson:" + str(projet.info / "%(id)s.%(ext)s"),
                "--", v.id)
            if projet.sous_titres(v.id):
                status = "ok"
            elif "429" in result.stderr:
                status = "bloqué"
            elif result.returncode == 0:
                status = "aucun sous-titre, à faire avec Whisper"
                absent.add(v.id)
            else:
                status = f"erreur : {result.stderr.strip()[-200:]}"
            print(f"  {status} : {v.titre}", flush=True)
            projet.pause("pause_sous_titres_s")
    done = sum(1 for v in videos if projet.sous_titres(v.id))
    print(f"terminé : {done}/{len(videos)} vidéos ont des sous-titres", flush=True)
