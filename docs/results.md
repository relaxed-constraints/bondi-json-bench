# Results

These figures show the BONDI JSON Bench reproduction of the original JSONBench
experiment. The reproduction compares MongoDB and Couchbase at scale factors
10, 100, and 200, with six client counts from 2 to 64 and three repetitions per
configuration.

Select any figure to open it at full size.

## Throughput and runtime

<figure>
  <a href="assets/figures/paper-repo/clients_by_scale.png"><img src="assets/figures/paper-repo/clients_by_scale.png" alt="Throughput and mean successful runtime by client count and scale factor" width="3023" height="1423" loading="lazy"></a>
  <figcaption>Lines show means across repetitions. Shaded bands show the range across repetitions.</figcaption>
</figure>

## Failures and outcome shares

<figure class="results-heatmap">
  <a href="assets/figures/paper-repo/failure_heatmaps.png"><img src="assets/figures/paper-repo/failure_heatmaps.png" alt="Error and timeout percentages by database, scale factor, and client count" width="971" height="1208" loading="lazy"></a>
  <figcaption>Each cell shows the mean share of attempts that ended in an error or a timeout.</figcaption>
</figure>

<figure>
  <a href="assets/figures/paper-repo/query_outcomes_normalized.png"><img src="assets/figures/paper-repo/query_outcomes_normalized.png" alt="Normalized query outcome percentages by database, scale factor, and client count" width="2711" height="1382" loading="lazy"></a>
  <figcaption>Outcome shares are averaged across runs. The plots distinguish successes, errors, timeouts, and unresolved attempts.</figcaption>
</figure>

## Results by query

### Query outcome counts

Absolute outcome counts pooled across client counts and repetitions.

<div class="results-figure-row">
<figure>
  <a href="assets/figures/paper-repo/query_outcomes_sf-10.png"><img src="assets/figures/paper-repo/query_outcomes_sf-10.png" alt="Outcome counts by query and database at scale factor 10" width="1260" height="996" loading="lazy"></a>
  <figcaption>Scale factor 10</figcaption>
</figure>
<figure>
  <a href="assets/figures/paper-repo/query_outcomes_sf-100.png"><img src="assets/figures/paper-repo/query_outcomes_sf-100.png" alt="Outcome counts by query and database at scale factor 100" width="1260" height="996" loading="lazy"></a>
  <figcaption>Scale factor 100</figcaption>
</figure>
<figure>
  <a href="assets/figures/paper-repo/query_outcomes_sf-200.png"><img src="assets/figures/paper-repo/query_outcomes_sf-200.png" alt="Outcome counts by query and database at scale factor 200" width="1260" height="996" loading="lazy"></a>
  <figcaption>Scale factor 200</figcaption>
</figure>
</div>

### Successful query runtimes

Runtime distributions for successful executions, pooled across client counts and repetitions.

<div class="results-figure-row">
<figure>
  <a href="assets/figures/paper-repo/query_runtimes_sf-10.png"><img src="assets/figures/paper-repo/query_runtimes_sf-10.png" alt="Successful runtime distributions by query and database at scale factor 10" width="1260" height="940" loading="lazy"></a>
  <figcaption>Scale factor 10</figcaption>
</figure>
<figure>
  <a href="assets/figures/paper-repo/query_runtimes_sf-100.png"><img src="assets/figures/paper-repo/query_runtimes_sf-100.png" alt="Successful runtime distributions by query and database at scale factor 100" width="1260" height="940" loading="lazy"></a>
  <figcaption>Scale factor 100</figcaption>
</figure>
<figure>
  <a href="assets/figures/paper-repo/query_runtimes_sf-200.png"><img src="assets/figures/paper-repo/query_runtimes_sf-200.png" alt="Successful runtime distributions by query and database at scale factor 200" width="1260" height="940" loading="lazy"></a>
  <figcaption>Scale factor 200</figcaption>
</figure>
</div>

## Reproducing the figures

See [Generate figures](cli.md#generate-figures) for the export command and
[Reading the figures](plotting.md) for aggregation and metric details.
