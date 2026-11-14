"""Step 0 check: the package imports and the CLI parses."""

import pytest

from inspect_vo import cli


def test_help_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "calibrate" in capsys.readouterr().out


def test_no_command_prints_help(capsys):
    assert cli.main([]) == 0
    assert "inspect-vo" in capsys.readouterr().out


def test_unbuilt_step_reports_itself(capsys):
    rc = cli.main(["flatten", "outputs/x"])
    assert rc == 2
    assert "step 6" in capsys.readouterr().err
