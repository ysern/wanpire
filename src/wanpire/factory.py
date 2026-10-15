"""Back to the box's install state: the configuration the install wrote (its roles, mode,
router network and country, kept as a factory copy, ``/etc/wanpire/factory.json``) and no
account. Wi-Fi networks and passwords set since go with the configuration; sessions, leases
and any link applied go with the server's restart, which is the caller's to do (the CLI
restarts the unit, the API exits and lets the unit restart it).

The install itself (the virtual environment, the unit, the netplan drop-in, a Wi-Fi driver)
is not touched: that is ``install.sh uninstall``.
"""

from __future__ import annotations

import json

from .account import DEFAULT_PATH as ACCOUNT_PATH
from .account import Account
from .config import DEFAULT_PATH as CONFIG_PATH
from .config import Config, InvalidConfig, config_from_dict, save_config

FACTORY_PATH = "/etc/wanpire/factory.json"


class NoFactoryCopy(RuntimeError):
    """The install made no factory copy (it predates one): nothing to restore."""


def reset(config_path: str = CONFIG_PATH, account_path: str = ACCOUNT_PATH,
          factory_path: str = FACTORY_PATH) -> Config:
    """Restore the configuration from the factory copy and remove the account. Returns the
    restored configuration. Refuses, changing nothing, without a copy or with an invalid one.
    The copy is not checked against the adapters: the box may have others now, and a missing
    line adapter leaves the line waiting, not the box down."""
    try:
        with open(factory_path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError:
        raise NoFactoryCopy(f"no factory copy at {factory_path}: run the install again "
                            "(install/install.sh), which makes one from the configuration it "
                            "finds; nothing was changed") from None
    except json.JSONDecodeError as e:
        raise InvalidConfig(f"the factory copy {factory_path} is not valid JSON: {e}; nothing "
                            "was changed") from None
    cfg = config_from_dict(data)  # InvalidConfig says why, before anything is written
    save_config(cfg, config_path)
    Account(account_path).reset()
    return cfg
