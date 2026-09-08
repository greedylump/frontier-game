# Python to portfolio

1. Open this folder in VS Code, install the editable package, and select its virtual
   environment. Run tests before changing the model. Debug one deterministic episode.
2. Explore in the notebook. Restart the kernel and run all cells before trusting it.
   Move reusable logic into src; keep notebooks focused on questions and interpretation.
3. Turn a useful question into a repeatable experiment with explicit configuration,
   seeds, and outputs. Add tests for new scientific behavior, not every plotting detail.
4. Commit source and a concise finding to Git. Large/generated results are ignored;
   deliberately curate a small results summary into docs for sharing. Record the source
   commit alongside metadata and save `python -m pip freeze` as an environment snapshot
   in the experiment output directory. Lower dependency bounds are not a lockfile.
5. Publish a repository when ready: clear README, reproducible command, labeled figure,
   assumptions, uncertainty, limitations, and your own explanation of the mechanism.
   A short portfolio case study can link to the repository and a static notebook export.
   Add a web app only after there is a finding worth communicating.

Suggested first case study: compare four policy pairs; explain the incentive to
deviate, then vary catastrophe cost. Distinguish simulated evidence from speculation.
Write down how AI helped and which calculations/tests you independently checked.
No remote repository or publication is created automatically.
