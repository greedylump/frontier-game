# Initial validation

Verified on Windows with Python 3.12.14 in a temporary virtual environment using
the bundled NumPy/pandas packages and installed project dependencies. The editable
installation with the `dev` extra succeeded. This was not a separate clean-machine
test of every supported Python version.

- All 14 pytest cases passed, including the CLI output and overwrite check.
- The notebook passed schema validation and all cells executed in a fresh Jupyter kernel.
- The seed-42 baseline ran 1,000 episodes and produced CSV, metadata, and a chart.
- The generated chart was visually inspected for labels and layout.

The sample baseline is included under `results/baseline`. Its observed catastrophe
frequency is 0.768, with a Wilson 95% interval of approximately [0.741, 0.793].
This is an output of the arbitrary teaching parameters, not an estimate of real-world
AI risk. Consult its metadata for exact scientific-package versions and settings.

The distributed notebook has cleared outputs so it opens as a fresh exercise.
The project folder has an initialized local Git repository; the ZIP omits Git
internals, caches, and the temporary validation environment.
