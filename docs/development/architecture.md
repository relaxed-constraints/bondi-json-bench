# Architecture

## Overview

The _BONDI JSON Bench_ architecture has three layers. This repository contains the **consumers**
(the CLI, Yanex scripts, notebooks and tests) and the **JSON Bench core API**. The
consumers use the core API to prepare data, run experiments, and analyse results.

**BONDI** is a separate package dependency, installed with the project. It provides
database deployments, data loading, native queries, workloads, and query execution.
The core API builds on these features and adds the benchmark-specific logic.

```mermaid
---
config:
  block:
    padding: 6
---
block
  columns 1
  block:consumers
    columns 1
    block:consumerComponents
      CLI["Command-line<br/>interface"]
      Yanex["Yanex scripts"]
      Notebooks["Notebooks"]
      Tests["Unit & integration tests"]
    end
    consumersLabel["Consumers"]
  end
  block:JSONBench
    columns 1
    block:jsonBenchComponents
      columns auto
      JD["Data generation"]
      JT["Template loading<br/>& translation"]
      JP["Database setup<br/>& indexes"]
      JE["Benchmark<br/>execution"]
      JA["Analysis & plotting"]
    end
    jsonBenchLabel["JSON Bench core API"]
  end
  block:BONDI
    columns 1
    block:bondiComponents
      BDp["Database<br/>Deployments"]
      BDa["Data loading"]
      BQ["Native queries"]
      BW["Workloads"]
      BL["Executors &<br/>load generation"]
    end
    bondiLabel["BONDI"]
  end
  classDef component fill:var(--jb-node-bg),stroke:var(--jb-node-border),color:var(--jb-diagram-text)
  class CLI,Yanex,Notebooks,Tests,JD,JT,JP,JE,JA,BDp,BDa,BQ,BW,BL component
  style consumers fill:var(--jb-frame-bg),stroke:var(--jb-frame-border),stroke-width:1px,stroke-dasharray:2 3
  style consumerComponents fill:transparent,stroke:none
  style consumersLabel fill:transparent,stroke:none,color:var(--jb-diagram-text),font-weight:bold
  style JSONBench fill:var(--jb-frame-bg),stroke:var(--jb-frame-border),stroke-width:1px,stroke-dasharray:2 3
  style BONDI fill:var(--jb-frame-bg),stroke:var(--jb-frame-border),stroke-width:1px,stroke-dasharray:2 3
  style jsonBenchComponents fill:transparent,stroke:none
  style bondiComponents fill:transparent,stroke:none
  style jsonBenchLabel fill:transparent,stroke:none,color:var(--jb-diagram-text),font-weight:bold
  style bondiLabel fill:transparent,stroke:none,color:var(--jb-diagram-text),font-weight:bold
```

## Core Components

The core API is implemented as a Python package under `src/json_bench`.
Its functionality is grouped into separate modules, as shown below.

| Component | Responsibility |
| --- | --- |
| `data.py` | Generate travel documents without database or file access |
| `queries.py` | Validate templates and translate them into native BONDI queries |
| `validate.py` | Compare collected grouped query results |
| `indexes.py` | Apply benchmark-specific indexes |
| `experiment.py` | Prepare databases and execute one benchmark run |
| `analysis.py` | Calculate measurement summaries and prepare result cohorts |
| `plotting.py` | Return Matplotlib figures from prepared analysis data |
| `cli.py` | Expand matrices, save state, resume, clean up, and export figures |
| `experiments/` | Yanex adapters, configuration, templates, and index definitions |

BONDI supplies deployments, document loading, query objects, executors, workloads,
and sustained-load generation. JSONBench owns the travel model, template language,
benchmark protocol, and analysis choices.

Both CLI and Yanex call `prepare_databases()` and `run_benchmark()`. Changes to
execution belong there, not in two separate interface implementations. Plotting
functions do not access databases or write files; callers choose how to save them.
