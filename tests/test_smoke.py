from __future__ import annotations


def test_third_party_imports() -> None:
    import joblib  # noqa: F401
    import mne  # noqa: F401
    import numpy  # noqa: F401
    import pylsl  # noqa: F401
    import scipy  # noqa: F401
    import sklearn  # noqa: F401
    import yaml  # noqa: F401


def test_bci_imports() -> None:
    from bci import config, logging_setup  # noqa: F401
    from bci.models import base, registry  # noqa: F401
