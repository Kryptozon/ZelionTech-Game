from . import core, missions, proof, admin, group


def get_routers():
    # Order matters: command/feature routers before the catch-all group router.
    return [core.router, missions.router, proof.router, admin.router, group.router]
