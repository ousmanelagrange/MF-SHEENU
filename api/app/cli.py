"""Commandes d'administration de la plateforme, à lancer sur le serveur :

    python -m app.cli operator add moi@exemple.com     # donner l'accès à la supervision
    python -m app.cli operator remove moi@exemple.com
    python -m app.cli operator list

Il n'existe volontairement aucune route d'API pour se nommer opérateur : il faut un accès
au serveur. Chaque changement est inscrit au journal de la plateforme.
"""

import sys
import uuid

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import PlatformAudit, User

CLI_OPERATOR = uuid.UUID(int=0)  # auteur des actions faites en ligne de commande


def operator(action: str, email: str | None = None) -> int:
    with SessionLocal() as db:
        if action == "list":
            for u in db.scalars(select(User).where(User.is_platform_admin.is_(True))):
                print(f"{u.email or u.phone}\t{u.full_name}")
            return 0
        user = db.scalar(select(User).where(User.email == (email or "").lower()))
        if user is None:
            print(f"Aucun compte pour {email}. La personne doit d'abord s'inscrire.")
            return 1
        user.is_platform_admin = action == "add"
        db.add(
            PlatformAudit(
                operator_id=CLI_OPERATOR,
                action=f"operator_{action}",
                target=str(user.id),
                detail={"email": user.email},
            )
        )
        db.commit()
        print(f"{user.full_name} : opérateur = {user.is_platform_admin}")
        return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "operator" and args[1] in ("add", "remove", "list"):
        sys.exit(operator(args[1], args[2] if len(args) > 2 else None))
    print(__doc__)
    sys.exit(2)
