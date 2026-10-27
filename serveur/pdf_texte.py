# -*- coding: utf-8 -*-
"""Texte d'un fichier PDF, pour que l'IA prépare une séance à partir d'un document de l'enseignant.

Utilise pypdf s'il est installé (paquet python3-pypdf sous Ubuntu, ou pip install pypdf) ; sinon, un lecteur
minimal, sans dépendance : objets et flux compressés (FlateDecode), flux d'objets, polices avec table ToUnicode
ou encodage simple, opérateurs de texte (Tj, TJ, ', "). Il ne lit pas les PDF chiffrés ni les images scannées :
le texte rendu est alors vide ou très court, et l'appelant le signale à l'enseignant.
"""
import io
import re
import zlib

TAILLE_TEXTE = 200_000          # caractères gardés au plus


def extraire(donnees, max_car=TAILLE_TEXTE):
    """Texte du PDF (pages séparées par une ligne vide), ou "" si rien n'est lisible."""
    try:
        import logging
        import pypdf
        logging.getLogger("pypdf").setLevel(logging.ERROR)     # avertissements sur les PDF mal formés
        lecteur = pypdf.PdfReader(io.BytesIO(donnees))
        texte = "\n\n".join((p.extract_text() or "").strip() for p in lecteur.pages).strip()
        if len(texte) >= 40:
            return _nettoyer(texte)[:max_car]
    except Exception:            # pypdf absent, ou fichier qu'il ne lit pas : lecteur intégré
        pass
    try:
        return _nettoyer(_Lecteur(donnees).texte())[:max_car]
    except Exception:
        return ""


def _nettoyer(t):
    t = t.replace("\r", "\n").replace("\x00", "")
    t = re.sub(r"[ \t\f\v]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


# ---------------------------------------------------------------- lecteur intégré
_DELIM = b"()<>[]{}/%"
_BLANCS = b" \t\r\n\f\x00"
# noms de glyphes courants (encodage /Differences sans table ToUnicode)
_GLYPHES = {
    "space": " ", "exclam": "!", "quotedbl": '"', "numbersign": "#", "dollar": "$", "percent": "%", "ampersand": "&",
    "quoteright": "’", "quotesingle": "'", "parenleft": "(", "parenright": ")", "asterisk": "*", "plus": "+", "comma": ",",
    "hyphen": "-", "period": ".", "slash": "/", "colon": ":", "semicolon": ";", "less": "<", "equal": "=", "greater": ">",
    "question": "?", "at": "@", "bracketleft": "[", "backslash": "\\", "bracketright": "]", "underscore": "_",
    "quoteleft": "‘", "braceleft": "{", "bar": "|", "braceright": "}", "asciitilde": "~", "endash": "–", "emdash": "—",
    "quotedblleft": "“", "quotedblright": "”", "guillemotleft": "«", "guillemotright": "»", "bullet": "•", "ellipsis": "…",
    "fi": "fi", "fl": "fl", "ff": "ff", "ffi": "ffi", "ffl": "ffl", "oe": "œ", "OE": "Œ", "ae": "æ", "AE": "Æ", "germandbls": "ß",
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "degree": "°", "multiply": "×", "minus": "−", "euro": "€", "Euro": "€", "dotlessi": "ı",
}
_ACCENTS = {"acute": "́", "grave": "̀", "circumflex": "̂", "dieresis": "̈", "cedilla": "̧", "tilde": "̃", "ring": "̊"}


def _glyphe(nom):
    import unicodedata
    if nom in _GLYPHES:
        return _GLYPHES[nom]
    if len(nom) == 1:
        return nom
    m = re.fullmatch(r"uni([0-9A-Fa-f]{4})+", nom) or re.fullmatch(r"u([0-9A-Fa-f]{4,6})", nom)
    if m:
        h = nom[3:] if nom.startswith("uni") else nom[1:]
        return "".join(chr(int(h[i:i + 4], 16)) for i in range(0, len(h), 4)) if nom.startswith("uni") else chr(int(h, 16))
    for acc, comb in _ACCENTS.items():           # eacute → é, Ccedilla → Ç
        if nom.endswith(acc) and len(nom) == len(acc) + 1:
            return unicodedata.normalize("NFC", nom[0] + comb)
    return ""


class _Ref:
    __slots__ = ("n",)

    def __init__(self, n):
        self.n = n


class _Analyseur:
    """Analyse les objets PDF (dictionnaires, tableaux, noms, nombres, chaînes, références)."""

    def __init__(self, b, i=0):
        self.b, self.i = b, i

    def blancs(self):
        b, n = self.b, len(self.b)
        while self.i < n:
            c = b[self.i]
            if c in _BLANCS:
                self.i += 1
            elif c == 0x25:                           # commentaire
                while self.i < n and b[self.i] not in b"\r\n":
                    self.i += 1
            else:
                break

    def jeton(self):
        """Prochain jeton brut : (genre, valeur). Genres : num, nom, chaine, op, debut_dict, fin_dict, debut_tab, fin_tab."""
        self.blancs()
        b, n, i = self.b, len(self.b), self.i
        if i >= n:
            return None, None
        c = b[i:i + 1]
        if b[i:i + 2] == b"<<":
            self.i += 2
            return "debut_dict", None
        if b[i:i + 2] == b">>":
            self.i += 2
            return "fin_dict", None
        if c == b"[":
            self.i += 1
            return "debut_tab", None
        if c == b"]":
            self.i += 1
            return "fin_tab", None
        if c == b"/":
            j = i + 1
            while j < n and b[j] not in _BLANCS and b[j] not in _DELIM:
                j += 1
            self.i = j
            nom = re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), b[i + 1:j])
            return "nom", nom.decode("latin-1")
        if c == b"(":
            return "chaine", self.chaine_litterale()
        if c == b"<":
            j = b.find(b">", i)
            j = n if j < 0 else j
            h = re.sub(rb"[^0-9A-Fa-f]", b"", b[i + 1:j])
            self.i = j + 1
            if len(h) % 2:
                h += b"0"
            return "chaine", bytes.fromhex(h.decode())
        j = i
        while j < n and b[j] not in _BLANCS and b[j] not in _DELIM:
            j += 1
        if j == i:                                    # délimiteur isolé ({, }, ) …) : ignoré
            self.i = i + 1
            return "op", c.decode("latin-1")
        mot = b[i:j]
        self.i = j
        if re.fullmatch(rb"[+-]?(\d+\.?\d*|\.\d+)", mot):
            return "num", float(mot)
        return "op", mot.decode("latin-1")

    def chaine_litterale(self):
        b, n = self.b, len(self.b)
        i, prof, out = self.i + 1, 1, bytearray()
        echap = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12, ord("("): 40, ord(")"): 41, ord("\\"): 92}
        while i < n:
            c = b[i]
            if c == 0x5C and i + 1 < n:              # \
                d = b[i + 1]
                if d in echap:
                    out.append(echap[d]); i += 2
                elif 0x30 <= d <= 0x37:
                    m = re.match(rb"[0-7]{1,3}", b[i + 1:i + 4])
                    out.append(int(m.group(), 8) & 0xFF); i += 1 + len(m.group())
                elif d in b"\r\n":
                    i += 2 + (d == 13 and i + 2 < n and b[i + 2] == 10)
                else:
                    out.append(d); i += 2
                continue
            if c == 0x28:
                prof += 1
            elif c == 0x29:
                prof -= 1
                if prof == 0:
                    i += 1
                    break
            out.append(c)
            i += 1
        self.i = i
        return bytes(out)

    def objet(self):
        """Objet PDF complet à la position courante."""
        genre, v = self.jeton()
        if genre == "debut_dict":
            d = {}
            while True:
                g, k = self.jeton()
                if g in ("fin_dict", None):
                    return d
                if g == "nom":
                    d[k] = self.objet()
        if genre == "debut_tab":
            t = []
            while True:
                sauv = self.i
                g, _ = self.jeton()
                if g in ("fin_tab", None):
                    return t
                self.i = sauv
                t.append(self.objet())
        if genre == "num":                            # « 12 0 R » : référence
            sauv = self.i
            g2, v2 = self.jeton()
            if g2 == "num":
                g3, v3 = self.jeton()
                if g3 == "op" and v3 == "R":
                    return _Ref(int(v))
            self.i = sauv
            return v
        return v


class _Lecteur:
    def __init__(self, b):
        self.b = b
        self.objets = {}                              # numéro → (dictionnaire ou valeur, flux décodé ou None)
        for m in re.finditer(rb"(?<![0-9])(\d+)\s+\d+\s+obj\b", b):
            num, a = int(m.group(1)), _Analyseur(b, m.end())
            try:
                val = a.objet()
            except Exception:
                continue
            flux = None
            a.blancs()
            if isinstance(val, dict) and b.startswith(b"stream", a.i):
                debut = a.i + 6
                debut += 2 if b[debut:debut + 2] == b"\r\n" else 1
                lg = val.get("Length")
                fin = debut + int(lg) if isinstance(lg, float) and b[debut + int(lg):debut + int(lg) + 20].lstrip().startswith(b"endstream") else b.find(b"endstream", debut)
                flux = self.decoder(val, b[debut:fin if fin > 0 else len(b)])
            self.objets[num] = (val, flux)
        for num, (val, flux) in list(self.objets.items()):      # flux d'objets (PDF 1.5 et plus)
            if isinstance(val, dict) and val.get("Type") == "ObjStm" and flux:
                try:
                    n, premier = int(val.get("N", 0)), int(val.get("First", 0))
                    tete = _Analyseur(flux)
                    paires = [(int(tete.jeton()[1]), int(tete.jeton()[1])) for _ in range(n)]
                    for k, dec in paires:
                        if k not in self.objets:
                            self.objets[k] = (_Analyseur(flux, premier + dec).objet(), None)
                except Exception:
                    continue

    @staticmethod
    def decoder(d, brut):
        filtres = d.get("Filter")
        filtres = filtres if isinstance(filtres, list) else [filtres] if filtres else []
        for f in filtres:
            if f == "FlateDecode":
                try:
                    brut = zlib.decompress(brut)
                except zlib.error:
                    brut = zlib.decompressobj().decompress(brut)
            elif f == "ASCIIHexDecode":
                brut = bytes.fromhex(re.sub(rb"[^0-9A-Fa-f]", b"", brut.split(b">")[0]).decode())
            else:                                     # filtres d'image (DCT, JBIG2…) : pas de texte
                return None
        return brut

    def val(self, x):
        while isinstance(x, _Ref):
            x = self.objets.get(x.n, (None, None))[0]
        return x

    def flux(self, x):
        return self.objets.get(x.n, (None, None))[1] if isinstance(x, _Ref) else None

    def pages(self):
        cat = next((v for v, _ in self.objets.values() if isinstance(v, dict) and v.get("Type") == "Catalog"), None)
        vues = set()

        def parcourir(noeud, ressources):
            noeud = self.val(noeud)
            if not isinstance(noeud, dict) or id(noeud) in vues:
                return
            vues.add(id(noeud))
            ressources = self.val(noeud.get("Resources")) or ressources
            if noeud.get("Type") == "Page" or "Contents" in noeud:
                yield noeud, ressources
            for k in self.val(noeud.get("Kids")) or []:
                yield from parcourir(k, ressources)

        if cat:
            yield from parcourir(cat.get("Pages"), {})
        else:                                         # sans catalogue lisible : les pages dans l'ordre du fichier
            for v, _ in self.objets.values():
                if isinstance(v, dict) and v.get("Type") == "Page":
                    yield v, self.val(v.get("Resources")) or {}

    def police(self, ref, cache):
        if id(ref) in cache:
            return cache[id(ref)]
        f = self.val(ref) or {}
        table, octets = {}, 1
        tu = f.get("ToUnicode")
        cmap = self.flux(tu) if isinstance(tu, _Ref) else None
        if cmap:
            octets, table = self.lire_cmap(cmap)
        elif f.get("Subtype") == "Type0":
            octets = 2
        else:
            enc = self.val(f.get("Encoding"))
            if isinstance(enc, dict):
                code = 0
                for x in self.val(enc.get("Differences")) or []:
                    if isinstance(x, float):
                        code = int(x)
                    elif isinstance(x, str):
                        table[code] = _glyphe(x)
                        code += 1
        cache[id(ref)] = (octets, table)
        return cache[id(ref)]

    @staticmethod
    def lire_cmap(b):
        t = b.decode("latin-1")
        octets = 2 if re.search(r"begincodespacerange\s*<[0-9A-Fa-f]{4}>", t) else 1
        table = {}
        u16 = lambda h: bytes.fromhex(h if len(h) % 4 == 0 else h.zfill(len(h) + (4 - len(h) % 4))).decode("utf-16-be", "replace")
        for bloc in re.findall(r"beginbfchar(.*?)endbfchar", t, re.S):
            for src, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", bloc):
                table[int(src, 16)] = u16(dst) if dst else ""
        for bloc in re.findall(r"beginbfrange(.*?)endbfrange", t, re.S):
            for a, z, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]+>|\[[^\]]*\])", bloc):
                a, z = int(a, 16), int(z, 16)
                if dst.startswith("["):
                    for k, h in enumerate(re.findall(r"<([0-9A-Fa-f]+)>", dst)):
                        table[a + k] = u16(h)
                else:
                    base = int(dst[1:-1], 16)
                    for k in range(min(z - a + 1, 65536)):
                        table[a + k] = chr(base + k) if base + k < 0x110000 else ""
        return octets, table

    @staticmethod
    def decoder_chaine(s, police):
        octets, table = police
        if octets == 2:
            codes = [int.from_bytes(s[i:i + 2], "big") for i in range(0, len(s) - 1, 2)]
        else:
            codes = list(s)
        out = []
        for c in codes:
            if c in table:
                out.append(table[c])
            elif octets == 1:
                out.append(bytes([c]).decode("cp1252", "replace") if c >= 32 else "")
        return "".join(out)

    def texte_page(self, contenu, ressources, cache):
        polices = self.val((ressources or {}).get("Font")) or {}
        a, pile, out = _Analyseur(contenu), [], []
        police, y = (1, {}), None
        while True:
            genre, v = a.jeton()
            if genre is None:
                break
            if genre in ("num", "chaine", "nom"):
                pile.append(v)
                continue
            if genre == "debut_tab":
                tab = []
                while True:
                    g2, v2 = a.jeton()
                    if g2 in ("fin_tab", None):
                        break
                    tab.append(v2)
                pile.append(tab)
                continue
            if genre in ("debut_dict", "fin_dict"):
                continue
            op = v
            if op == "Tf" and len(pile) >= 2 and isinstance(pile[-2], str):
                ref = polices.get(pile[-2]) if isinstance(polices, dict) else None
                police = self.police(ref, cache) if ref is not None else (1, {})
            elif op in ("Td", "TD") and len(pile) >= 2 and isinstance(pile[-1], float):
                out.append("\n" if abs(pile[-1]) > 0.5 else " ")
            elif op == "Tm" and len(pile) >= 6 and isinstance(pile[-1], float):
                if y is not None and abs(pile[-1] - y) > 0.5:
                    out.append("\n")
                y = pile[-1]
            elif op == "T*":
                out.append("\n")
            elif op == "Tj" and pile and isinstance(pile[-1], bytes):
                out.append(self.decoder_chaine(pile[-1], police))
            elif op in ("'", '"') and pile and isinstance(pile[-1], bytes):
                out.append("\n" + self.decoder_chaine(pile[-1], police))
            elif op == "TJ" and pile and isinstance(pile[-1], list):
                for x in pile[-1]:
                    if isinstance(x, bytes):
                        out.append(self.decoder_chaine(x, police))
                    elif isinstance(x, float) and x < -250:
                        out.append(" ")
            elif op == "ET":
                out.append(" ")
            pile = []
        return "".join(out)

    def texte(self):
        cache, pages = {}, []
        for page, ressources in self.pages():
            contenus = self.val(page.get("Contents"))
            refs = page.get("Contents") if not isinstance(contenus, list) else contenus
            refs = refs if isinstance(refs, list) else [refs]
            flux = b"\n".join(f for f in (self.flux(r) for r in refs) if f)
            if flux:
                pages.append(self.texte_page(flux, ressources, cache))
        return "\n\n".join(p.strip() for p in pages)
