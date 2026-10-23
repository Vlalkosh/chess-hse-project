"""Check console startup and readable errors for missing graphics dependencies."""

import builtins
import sys

import pytest

import main


def test_console_mode_does_not_import_graphics(monkeypatch, capsys):
    """Check console output works without importing Tkinter or the GUI module."""
    original_import = builtins.__import__

    def without_graphics(name, *args, **kwargs):
        """Fail if console mode attempts to import the graphical interface."""
        if name in ("tkinter", "chess_engine.gui"):
            raise AssertionError("Console mode must not import the graphical interface.")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_graphics)
    monkeypatch.setattr(sys, "argv", ["main.py", "--console"])
    main.main()
    assert "8 r n b q k b n r" in capsys.readouterr().out


@pytest.mark.parametrize("missing", ["PIL", "tkinter"])
def test_missing_graphics_dependency_has_readable_error(monkeypatch, capsys, missing):
    """Check missing Pillow or Tkinter produces a useful message and exit code 1."""
    original_import = builtins.__import__

    def missing_dependency(name, *args, **kwargs):
        """Simulate the selected missing graphics dependency during import."""
        if name == "chess_engine.gui" and missing == "PIL":
            raise ModuleNotFoundError("Pillow is missing", name="PIL")
        if name == "tkinter" and missing == "tkinter":
            raise ModuleNotFoundError("Tk is missing", name="tkinter")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_dependency)
    monkeypatch.setattr(sys, "argv", ["main.py"])
    with pytest.raises(SystemExit) as error:
        main.main()
    assert error.value.code == 1
    stderr = capsys.readouterr().err
    assert "requirements.txt" in stderr if missing == "PIL" else "Tcl/Tk" in stderr
