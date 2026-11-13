# Troubleshooting

## A command failed

Read the path printed in the error message. A failed CLI attempt contains
`error.txt` and any artifacts written before the failure. Do not delete that
folder to retry. Resolve the cause, then repeat the command with `--resume`.

Query errors and timeouts can be valid benchmark outcomes. A completed run with
those outcomes is not retried by resume. Inspect its outcome figures alongside
successful runtimes.

## A port is occupied

Check `bondi deployment list` and Docker's running containers. Stop the deployment
that owns the port, or select different preparation ports. Do not remove unrelated
projects. Recent BONDI fixes allow port reuse after closed TCP connections while
still rejecting active listeners.

## Preparation settings changed

Resume requires the original preparation settings. Use a new experiment name for
new data, versions, or memory limits. Benchmark resume also requires the original
timing, seed, and query settings. It can add client counts or repetitions.

## A deployment name already exists

New CLI deployments use the experiment name and scale factor. Choose a different
experiment name if another experiment already owns that name. Cleanup only when
you no longer need the original data.

## No completed runs are available to plot

Finish at least one benchmark run. `plot` excludes failed and unfinished runs,
but reports them. Missing artifacts in a completed run cause an error. Keep
`state.json`, attempt folders, and result files together.

## Memory or startup failures

Compare Docker's memory allocation with the configured database cap and caches.
Use the saved error and database logs to diagnose the failure. Increasing a timeout
alone does not fix a failed database. Keep settings fixed within a comparison;
start a new experiment if the protocol must change.
