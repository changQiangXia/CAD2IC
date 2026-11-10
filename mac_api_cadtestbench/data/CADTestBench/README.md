---
license: mit
language:
  - en
task_categories:
  - other
tags:
  - cad
  - text-to-cad
  - evaluation
  - cad-model-generation
configs:
  - config_name: samples
    data_files:
      - split: abstract
        path: samples/abstract.parquet
      - split: detailed
        path: samples/detailed.parquet
  - config_name: cadtests
    data_files:
      - split: abstract
        path: cadtests/abstract.parquet
      - split: detailed
        path: cadtests/detailed.parquet
---
# Text-to-CAD Evaluation with CADTESTS

### [Dimitrios Mallis](https://dimitrismallis.github.io/), [Marco Wang](https://marcowang.tech/), [Ahmet Serdar Karadeniz](https://askaradeniz.github.io/), [Elisa Ricci](https://eliricci.eu/), [Anis Kacem](https://www.uni.lu/en/person/NTAwMzU1NDVfX0FuaXMgS0FDRU0=/), [Djamila Aouada](https://www.uni.lu/snt-en/people/djamila-aouada/)

We release CADTestBench, the first test-based benchmark for Text-to-CAD.

CADTestBench is described on the paper:

> __Text-to-CAD Evaluation with CADTests__.


CADTestBench is a benchmark of 200 CAD programs (derived from [CADPrompt](https://github.com/Kamel773/CAD_Code_Generation)), each paired with an abstract prompt providing
a high level description of the object and a detailed prompt specifying additional geometric
constraints such as exact dimensions, proportions, etc.

For each sample, CADTestBench provides a suite of executable software tests verifying whether a generated CAD Boundary Representation (B-Rep), 
meets the design specifications of the input prompt. 

## Usage

This benchmark is designed for use within the **full CADTestBench toolkit**:

[https://github.com/dimitrismallis/CADTestBench](https://github.com/dimitrismallis/CADTestBench)

That repo contains everything needed to evaluate model generations with
CADTestBench.

## Quick Start in Browser

Open **[CADTestBench Viewer](https://cadtestbench-viewer.vercel.app/)** to view four paper baselines (GPT-5.2 and Claude 4.6 Sonnet, abstract and detailed splits) with **preloaded** cadtest results. Browse directly in the browser.


## Data Description

Two tables, two splits each (`abstract`, `detailed`). The same 200 `sample_id`s appear in both splits; only the `prompt` text differs:

- **`abstract`** — short, high-level prompt.
- **`detailed`** — abstract prompt plus explicit geometric constraints (dimensions, proportions, alignment, ...).

### Tables

- **`samples`** — one row per `(sample_id, partition)`. Holds the natural-language `prompt` fed to the model.
- **`cadtests`** — one row per executable check. Holds the `cadtest_code` Python snippet that calls `check(condition, pass_msg, fail_msg)` against the model's `final_result`, its `cadtest_type` (taxonomy below), and a per-sample `requirement_id` grouping key.


### `samples` — one row per (sample, partition)

200 rows per split.

| Column        | Type     | Description                                                                                |
|---------------|----------|--------------------------------------------------------------------------------------------|
| `sample_id`   | `string` | Stable 8-digit id (e.g. `"00000007"`). Same id across both partitions.                     |
| `partition`   | `string` | `"abstract"` or `"detailed"` -- redundant with the split, included for filtered concat.    |
| `prompt`      | `string` | Natural-language description fed to the model. Differs between partitions.                 |

### `cadtests` — one row per executable check

One row per cadtest. Joinable on
(`sample_id`, `partition`).

| Column                       | Type            | Description                                                                                                         |
|------------------------------|-----------------|---------------------------------------------------------------------------------------------------------------------|
| `sample_id`                  | `string`        | Foreign key to `samples.sample_id`.                                                                                 |
| `partition`                  | `string`        | `"abstract"` or `"detailed"`.                                                                                       |
| `cadtest_id`                 | `int64`         | Cadtest id, **unique within a sample** (not globally unique).                                                       |
| `cadtest_description`        | `string`        | Human-readable description of the prompt requirement of what the test verifies.                                                                  |
| `cadtest_code`               | `string`        | Executable Python snippet usint CADQuery.  |
| `cadtest_type`               | `string`        | See category in the taxonomy below |
| `classification_reasoning`   | `string`        | Short rationale for the assigned `cadtest_type` |
| `prompt_justification`       | `string`        | A short description of why this CADTest verfies a specification of the input prompt|
| `requirement_id`             | `string` `null` | Per-sample id of the requirement this cadtest belongs to. All cadtests sharing this value form one requirement group. |
| `requirement_type`           | `string` `null` | Type of the parent requirement.     |
| `requirement_description`    | `string` `null` | Description of the parent requirement.   |

#### `cadtest_type` taxonomy

| Value                  | What it checks                                                                            |
|------------------------|-------------------------------------------------------------------------------------------|
| `topology_checks`      | Counts of faces / edges / vertices and their connectivity.                                |
| `solid_shell_validity` | Watertightness, manifoldness, no self-intersections.                                      |
| `dimensions_ratios`    | Bounding-box sizes, aspect ratios, and absolute dimensions.                               |
| `volumetric_checks`    | Volume / mass-style numeric properties.                                                   |
| `spatial_arrangement`  | Relative positioning, alignment, symmetry.                                                |
| `geometry_types`       | Presence of specific primitives (cylinder, hole, fillet, ...).                            |
| `uncategorized`        | A cadtest does not fit any of the above.                                    |


## License

MIT.
