"""Check the fiches against the transcripts, and merge their claims into one register.

A fiche is fiches/<id>.md for reading, plus fiches/<id>.json with one claim per entry (format in prompts/fiche.md).
The check is mechanical: every timestamp must exist in the transcript, and every quote of the JSON must be found,
word for word or nearly, in the minute it cites or the next one. A claim that fails is not used.
"""
import json
import re
from collections import defaultdict

LINK = re.compile(r"watch\?v=([\w-]{11})&t=(\d+)s")
BLOCK = re.compile(r"^\[(\d+):(\d\d):(\d\d)\]\(")
TYPES = {"regle", "definition", "chiffre", "exemple", "trade", "limite"}
STATUTS = {"nouveau", "repete", "precise", "contredit"}
NEAR = 0.8  # share of the quote's words found in the window for an approximate match


def normalize(text):
    return " ".join(re.sub(r"[^\w]+", " ", text.lower()).split())


def blocks(projet, video_id):
    """[(start_s, text)] of a transcript, or None if there is none."""
    path = projet.transcripts / f"{video_id}.md"
    if not path.exists():
        return None
    out = []
    for line in path.read_text().splitlines():
        m = BLOCK.match(line)
        if m:
            h, mn, s = map(int, m.groups())
            out.append((h * 3600 + mn * 60 + s, line.split(") ", 1)[1] if ") " in line else ""))
    return out


def window(bl, t):
    """Text of the block containing t and the one after, since a sentence can straddle two blocks."""
    i = max((k for k, (start, _) in enumerate(bl) if start <= t), default=None)
    if i is None or t > bl[-1][0] + 120:
        return None
    return " ".join(text for _, text in bl[i:i + 2])


def match(quote, text):
    """'exacte', 'approchée' or 'introuvable'."""
    q, t = normalize(quote), normalize(text)
    if q and q in t:
        return "exacte"
    words = [w for w in q.split() if len(w) > 2]
    if words and sum(w in set(t.split()) for w in words) / len(words) >= NEAR:
        return "approchée"
    return "introuvable"


def verifier(projet):
    """Write data/verif_fiches.tsv and print the problems. Returns the number of errors."""
    cache, problems, counts = {}, [], defaultdict(int)

    def bl(video_id):
        if video_id not in cache:
            cache[video_id] = blocks(projet, video_id)
        return cache[video_id]

    for md in sorted(projet.fiches.glob("*.md")):
        video = md.stem
        if bl(video) is None:
            problems.append((video, "md", "", "erreur", "pas de transcription pour cette fiche"))
            continue
        for linked, t in LINK.findall(md.read_text()):
            counts["liens"] += 1
            b = bl(linked)
            if b is None:
                problems.append((video, "md", t, "erreur", f"lien vers {linked}, sans transcription"))
            elif window(b, int(t)) is None:
                problems.append((video, "md", t, "erreur", "horodatage hors de la vidéo"))
        js = md.with_suffix(".json")
        if not js.exists():
            problems.append((video, "json", "", "erreur", "fiche JSON absente"))
            continue
        try:
            claims = json.loads(js.read_text())["affirmations"]
        except (ValueError, KeyError) as e:
            problems.append((video, "json", "", "erreur", f"JSON illisible : {e}"))
            continue
        for n, c in enumerate(claims):
            counts["affirmations"] += 1
            where = f"#{n} t={c.get('t')}"
            for field, allowed in (("type", TYPES), ("statut", STATUTS)):
                if c.get(field) not in allowed:
                    problems.append((video, "json", where, "erreur", f"{field} « {c.get(field)} » inconnu"))
            if not c.get("cle"):
                problems.append((video, "json", where, "erreur", "cle vide"))
            text = window(bl(video), int(c.get("t", -1))) if isinstance(c.get("t"), int) else None
            if text is None:
                problems.append((video, "json", where, "erreur", "horodatage hors de la vidéo"))
                continue
            result = match(c.get("citation", ""), text)
            counts[result] += 1
            if result != "exacte":
                problems.append((video, "json", where, "erreur" if result == "introuvable" else "à revoir",
                                 f"citation {result} : « {c.get('citation', '')[:80]} »"))
    projet.data.mkdir(parents=True, exist_ok=True)
    (projet.data / "verif_fiches.tsv").write_text("".join("\t".join(map(str, p)) + "\n" for p in problems))
    errors = sum(1 for p in problems if p[3] == "erreur")
    print(f"{counts['liens']} liens, {counts['affirmations']} affirmations : {counts['exacte']} citations exactes, "
          f"{counts['approchée']} approchées, {counts['introuvable']} introuvables ; {errors} erreurs")
    for p in problems[:40]:
        print("  " + "  ".join(map(str, p)))
    if len(problems) > 40:
        print(f"  … {len(problems) - 40} de plus dans data/verif_fiches.tsv")
    return errors


def registre(projet):
    """Merge the JSON fiches into data/affirmations.tsv and count, per key, the distinct videos (data/cles.tsv)."""
    verdicts = {}
    if (projet.data / "verif_fiches.tsv").exists():
        for line in (projet.data / "verif_fiches.tsv").read_text().splitlines():
            video, kind, where, level, _ = line.split("\t", 4)
            if kind == "json" and where.startswith("#"):
                key = (video, int(where[1:].split()[0]))
                if verdicts.get(key) != "erreur":
                    verdicts[key] = level
    rows, by_key = [], defaultdict(list)
    for js in sorted(projet.fiches.glob("*.json")):
        date = projet.date(js.stem)
        for n, c in enumerate(json.loads(js.read_text()).get("affirmations", [])):
            check = verdicts.get((js.stem, n), "ok")
            rows.append((date, js.stem, c.get("t"), c.get("type"), c.get("cle"), c.get("statut"), c.get("renvoi") or "",
                         check, " ".join(str(c.get("texte", "")).split()), " ".join(str(c.get("citation", "")).split())))
            if check != "erreur":
                by_key[c.get("cle")].append((date, js.stem, c.get("statut"), c.get("texte", "")))
    rows.sort(key=lambda r: (r[4] or "", r[0], r[1], r[2] or 0))
    header = "date\tvideo\tt\ttype\tcle\tstatut\trenvoi\tverif\ttexte\tcitation\n"
    projet.affirmations_tsv.write_text(header + "".join("\t".join(map(str, r)) + "\n" for r in rows))
    contested = {r[6] for r in rows if r[5] == "contredit" and r[6]} | {r[4] for r in rows if r[5] == "contredit"}
    keys = []
    for key, claims in by_key.items():
        videos = sorted({c[1] for c in claims})
        dates = sorted(c[0] for c in claims if c[0])
        confiance = "Contradictoire" if key in contested else "Répétée" if len(videos) > 1 else "Une fois"
        keys.append((key, confiance, len(videos), dates[0] if dates else "", dates[-1] if dates else "",
                     " ".join(videos), " ".join(str(claims[0][3]).split())[:200]))
    keys.sort()
    (projet.data / "cles.tsv").write_text("cle\tconfiance\tvideos\tpremiere\tderniere\tids\texemple\n" +
                                         "".join("\t".join(map(str, k)) + "\n" for k in keys))
    total = defaultdict(int)
    for k in keys:
        total[k[1]] += 1
    print(f"{len(rows)} affirmations, {len(keys)} clés : " + ", ".join(f"{n} {c}" for c, n in sorted(total.items())))
    print("dans data/affirmations.tsv et data/cles.tsv")
