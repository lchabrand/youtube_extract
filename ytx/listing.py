"""List every video of the channel tabs, then keep the ones the categories of chaine.json select."""
from collections import defaultdict

from .projet import Video, write_tsv

PRINT = "%(id)s\t%(duration)s\t%(view_count)s\t%(title)s"


def urls(source, onglets):
    """(url, tab) pairs for a channel given as @handle, UC… id or URL; a playlist or video URL is taken as is."""
    if source.startswith("http"):
        if "list=" in source or "/watch" in source or "youtu.be/" in source:
            return [(source, "playlist")]
        base = source.rstrip("/")
        for onglet in ("videos", "streams", "shorts", "featured"):
            base = base[: -len(onglet) - 1] if base.endswith("/" + onglet) else base
    elif source.startswith("UC") and len(source) == 24:
        base = f"https://www.youtube.com/channel/{source}"
    else:
        base = f"https://www.youtube.com/@{source.lstrip('@')}"
    return [(f"{base}/{onglet}", onglet) for onglet in onglets]


def number(text):
    try:
        return int(float(text))
    except ValueError:
        return 0


def lister(projet, limite=None):
    if not projet.config["sources"]:
        raise SystemExit(f"aucune source dans {projet.fichier} : ajouter par exemple \"sources\": [\"@chaine\"]")
    videos, seen = [], set()
    for source in projet.config["sources"]:
        for url, onglet in urls(source, projet.config["onglets"]):
            args = ["--flat-playlist", "--ignore-errors", "--print", PRINT]
            if limite:
                args += ["--playlist-end", str(limite)]
            result = projet.yt_dlp(*args, "--", url)
            lines = [l for l in result.stdout.splitlines() if l.count("\t") >= 3]
            if not lines:
                reason = result.stderr.strip().splitlines()[-1:] or ["vide"]
                print(f"  {source} {onglet} : aucune vidéo ({reason[0][:120]})", flush=True)
                continue
            new = 0
            for line in lines:
                video_id, duree, vues, titre = line.split("\t", 3)
                if video_id in seen:
                    continue
                seen.add(video_id)
                new += 1
                videos.append(Video(video_id, number(duree), number(vues), " ".join(titre.split()), source, onglet, None))
            print(f"  {source} {onglet} : {new} vidéos", flush=True)
    write_tsv(projet.listing_tsv, [v[:6] for v in videos])
    print(f"{len(videos)} vidéos dans data/listing.tsv")


def selectionner(projet):
    listing = projet.listing()
    if not listing:
        raise SystemExit(f"{projet.listing_tsv} vide : lancer d'abord « python3 -m ytx lister {projet.dir.name} »")
    kept, left_out = [], []
    minimum = projet.config["duree_min_s"]
    for v in listing:
        cat = projet.categorie(v.id, v.titre)
        if v.id not in projet.config["forcer"] and v.duree < minimum:
            cat = None
        (kept if cat else left_out).append(v._replace(categorie=cat))
    kept.sort(key=projet.priorite)
    write_tsv(projet.selection_tsv, kept)
    write_tsv(projet.exclues_tsv, left_out)
    groups = defaultdict(list)
    for v in kept:
        groups[v.categorie].append(v)
    for cat, group in groups.items():
        print(f"{cat}: {len(group)} vidéos, {sum(v.duree for v in group) / 3600:.1f} h")
    print(f"total : {len(kept)} vidéos, {sum(v.duree for v in kept) / 3600:.1f} h ; "
          f"{len(left_out)} écartées, listées dans data/exclues.tsv")
