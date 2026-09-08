import json
import subprocess
import sys


def test_cli_outputs_and_refuses_overwrite(tmp_path):
    output = tmp_path / "baseline"
    command = [sys.executable, "-m", "frontier_game", "--trials", "10",
               "--horizon", "3", "--output", str(output)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    assert {p.name for p in output.iterdir()} == {
        "episodes.csv", "summary.csv", "metadata.json", "payoffs.png"}
    metadata = json.loads((output / "metadata.json").read_text())
    assert metadata["seed"] == 42
    assert metadata["trials"] == 10
    assert metadata["config"]["horizon"] == 3
    assert subprocess.run(command, capture_output=True).returncode != 0
