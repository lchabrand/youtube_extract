"""python3 -m ytx <commande> <chaine> : extraire les transcriptions d'une chaîne YouTube. Aide : python3 -m ytx -h"""
import argparse
import json
import shutil
import sys

from . import images, listing, sous_titres, transcriptions, whisper
from .projet import CHAINES, Projet

EXEMPLE = CHAINES / "exemple" / "chaine.json"
OUTILS = {
    "lister": ["yt-dlp"],
    "sous-titres": ["yt-dlp"],
    "whisper": ["yt-dlp", "ffmpeg", "whisper-cli"],
    "refaire-whisper": ["yt-dlp", "ffmpeg", "whisper-cli"],
    "images": ["yt-dlp", "ffmpeg", "swiftc"],
    "tout": ["yt-dlp", "ffmpeg", "whisper-cli"],
    "modeles": ["curl"],
}


def nouvelle(args):
    target = CHAINES / args.nom
    if (target / "chaine.json").exists():
        raise SystemExit(f"{target / 'chaine.json'} existe déjà")
    config = json.loads(EXEMPLE.read_text())
    config["nom"] = args.nom
    config["sources"] = args.sources
    if args.langue:
        config["langue"] = args.langue
    target.mkdir(parents=True)
    (target / "chaine.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    print(f"créé {target / 'chaine.json'}. Ensuite :\n"
          f"  python3 -m ytx lister {args.nom}\n"
          f"  ajuster \"categories\" dans chaine.json, puis python3 -m ytx selectionner {args.nom}\n"
          f"  python3 -m ytx tout {args.nom}")


def statut(projet):
    sel = projet.selection() if projet.selection_tsv.exists() else []
    subs = sum(1 for v in sel if projet.sous_titres(v.id))
    whisp = sum(1 for v in sel if not projet.sous_titres(v.id) and projet.whisper_json(v.id))
    bad = projet.whisper_bad_tsv.read_text().split() if projet.whisper_bad_tsv.exists() else []
    rows = [
        ("listées", len(projet.listing())),
        ("sélectionnées", len(sel)),
        ("avec sous-titres YouTube", subs),
        ("transcrites par Whisper", whisp),
        ("encore sans texte", len(sel) - subs - whisp),
        ("Whisper à refaire", len(bad)),
        ("transcriptions", sum(1 for v in sel if (projet.transcripts / f"{v.id}.md").exists())),
        ("lues à l'écran (OCR)", sum(1 for v in sel if (projet.ocr / f"{v.id}.jsonl").exists())),
        ("fiches", sum(1 for v in sel if (projet.fiches / f"{v.id}.md").exists())),
    ]
    print(f"{projet.nom} ({projet.dir})")
    for label, n in rows:
        print(f"  {n:5d}  {label}")


def tout(projet, args):
    if args.relister or not projet.listing_tsv.exists():
        listing.lister(projet, args.limite)
    listing.selectionner(projet)
    sous_titres.telecharger(projet)
    whisper.transcrire(projet)
    bad = whisper.verifier(projet)
    if bad:
        whisper.refaire(projet, bad)
        whisper.verifier(projet)
    transcriptions.construire(projet)
    statut(projet)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m ytx", description=__doc__)
    sub = parser.add_subparsers(dest="commande", required=True, metavar="commande")

    p = sub.add_parser("nouvelle", help="créer chaines/<nom>/chaine.json")
    p.add_argument("nom")
    p.add_argument("sources", nargs="+", help="@handle, identifiant UC…, URL de chaîne ou de playlist")
    p.add_argument("--langue", help="langue des vidéos (en, fr…), par défaut celle de l'exemple")
    p.set_defaults(run=nouvelle, projet=False)

    sub.add_parser("modeles", help="télécharger les modèles Whisper (~550 Mo) dans modeles/").set_defaults(
        run=lambda a: whisper.telecharger_modeles(), projet=False)

    def command(name, help, run, **extra):
        p = sub.add_parser(name, help=help)
        p.add_argument("chaine", help="nom du dossier dans chaines/, ou chemin d'un dossier avec chaine.json")
        for flag, kw in extra.items():
            p.add_argument(flag, **kw)
        p.set_defaults(run=run, projet=True)

    limite = {"help": "ne lister que les N premières vidéos de chaque onglet (pour essayer)", "type": int}
    command("lister", "lister toutes les vidéos des onglets", lambda pr, a: listing.lister(pr, a.limite),
            **{"--limite": limite})
    command("selectionner", "classer les titres selon les catégories", lambda pr, a: listing.selectionner(pr))
    command("sous-titres", "télécharger les sous-titres", lambda pr, a: sous_titres.telecharger(pr))
    command("whisper", "transcrire les vidéos sans sous-titres", lambda pr, a: whisper.transcrire(pr))
    command("verifier-whisper", "repérer les transcriptions Whisper qui bouclent", lambda pr, a: whisper.verifier(pr))
    command("refaire-whisper", "refaire celles de data/whisper_bad.tsv, ou les identifiants donnés",
            lambda pr, a: whisper.refaire(pr, a.ids or None), ids={"nargs": "*", "help": "identifiants de vidéos"})
    command("transcriptions", "écrire transcripts/<id>.md", lambda pr, a: transcriptions.construire(pr))
    command("images", "macOS : télécharger les vidéos et lire le texte à l'écran",
            lambda pr, a: images.images(pr, a.garder_videos or None),
            **{"--garder-videos": {"action": "store_true", "help": "ne pas effacer les vidéos après lecture"}})
    command("statut", "où en est chaque étape", lambda pr, a: statut(pr))
    command("tout", "lister, sélectionner, sous-titres, Whisper, vérification, transcriptions", tout,
            **{"--relister": {"action": "store_true", "help": "refaire le listing même s'il existe"},
               "--limite": limite})

    args = parser.parse_args(argv)
    for tool in OUTILS.get(args.commande, ()):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} introuvable : voir « Installation » dans README.md")
    if args.projet:
        args.run(Projet(args.chaine), args)
    else:
        args.run(args)


if __name__ == "__main__":
    sys.exit(main())
