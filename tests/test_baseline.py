"""Baseline check that the source package is importable."""


def test_virtual_ecg_package_imports():
    import virtual_ecg

    assert virtual_ecg.__doc__
