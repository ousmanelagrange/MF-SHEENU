"""Nom du lien de parenté en français — docs/03-conception-detaillee.md §2.4.

Fonctions pures, sans base de données : faciles à tester.
"""


def _g(sex: str, masc: str, fem: str, neutral: str | None = None) -> str:
    if sex == "M":
        return masc
    if sex == "F":
        return fem
    return neutral or f"{masc} / {fem}"


def _ordinal(n: int) -> str:
    return "1er" if n == 1 else f"{n}e"


def blood_label(d_from: int, d_to: int, sex_to: str, half: bool = False) -> str:
    """Nom du lien vu de la personne A : « B est votre … ».

    d_from : distance de A à l'ancêtre commun ; d_to : distance de B à l'ancêtre commun.
    sex_to : sexe de B. half : frère/sœur n'ayant qu'un parent en commun.
    """
    if d_from == 0 and d_to == 0:
        return "vous-même"

    # B descend de A
    if d_from == 0:
        if d_to == 1:
            return _g(sex_to, "fils", "fille", "enfant")
        if d_to == 2:
            return _g(sex_to, "petit-fils", "petite-fille", "petit-enfant")
        if d_to == 3:
            return _g(sex_to, "arrière-petit-fils", "arrière-petite-fille", "arrière-petit-enfant")
        return (
            _g(sex_to, "descendant", "descendante", "descendant(e)") + f" à la {d_to}e génération"
        )

    # A descend de B
    if d_to == 0:
        if d_from == 1:
            return _g(sex_to, "père", "mère", "parent")
        if d_from == 2:
            return _g(sex_to, "grand-père", "grand-mère", "grand-parent")
        if d_from == 3:
            return _g(sex_to, "arrière-grand-père", "arrière-grand-mère", "arrière-grand-parent")
        return _g(sex_to, "ancêtre", "ancêtre") + f" à la {d_from}e génération"

    if d_from == 1 and d_to == 1:
        base = _g(sex_to, "frère", "sœur", "frère / sœur")
        return f"demi-{base}" if half else base
    if d_from == 1 and d_to == 2:
        return _g(sex_to, "neveu", "nièce")
    if d_from == 1 and d_to == 3:
        return _g(sex_to, "petit-neveu", "petite-nièce")
    if d_from == 1:
        return _g(sex_to, "arrière-petit-neveu", "arrière-petite-nièce") + (
            f" ({d_to - 1}e génération)" if d_to > 4 else ""
        )
    if d_from == 2 and d_to == 1:
        return _g(sex_to, "oncle", "tante")
    if d_from == 3 and d_to == 1:
        return _g(sex_to, "grand-oncle", "grand-tante")
    if d_to == 1:
        return _g(sex_to, "arrière-grand-oncle", "arrière-grand-tante") + (
            f" ({d_from - 1}e génération)" if d_from > 4 else ""
        )

    cousin = _g(sex_to, "cousin", "cousine", "cousin(e)")
    if d_from == d_to:
        if d_from == 2:
            return _g(sex_to, "cousin germain", "cousine germaine", "cousin(e) germain(e)")
        return f"{cousin} au {_ordinal(d_from - 1)} degré"
    degree = min(d_from, d_to) - 1
    shift = abs(d_from - d_to)
    shift_txt = f"{shift} génération" + ("s" if shift > 1 else "")
    base = (
        _g(sex_to, "cousin germain", "cousine germaine", "cousin(e) germain(e)")
        if degree == 1
        else f"{cousin} au {_ordinal(degree)} degré"
    )
    direction = "plus jeune" if d_to > d_from else "plus âgé" if sex_to != "F" else "plus âgée"
    return f"{base}, {shift_txt} {direction}"


def spouse_label(sex_to: str) -> str:
    return _g(sex_to, "époux", "épouse", "conjoint(e)")
