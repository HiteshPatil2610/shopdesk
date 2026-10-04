"""Admin CLI commands:  flask --app admin_api <command>"""

from __future__ import annotations

import click
from flask import Flask

from core.actor import ActorContext
from core.clerk_gateway import get_gateway
from core.db import transaction
from core.services import auth_service


def register_cli(app: Flask) -> None:
    @app.cli.command("promote-admin")
    @click.option(
        "--clerk-user-id", required=True, help="e.g. user_2abc... (Clerk dashboard → Users)"
    )
    def promote_admin(clerk_user_id: str) -> None:
        """Give a Clerk user the ShopDesk admin role (one-time owner setup)."""
        gateway = get_gateway()
        gateway.set_role(clerk_user_id, "admin")
        info = gateway.get_user(clerk_user_id)
        with transaction():
            user = auth_service.upsert_from_clerk(info, ActorContext.system("cli"))
        name = user.display_name if user else clerk_user_id
        click.echo(f"{name} is now an admin. Sign out and back in to pick up the new role.")
