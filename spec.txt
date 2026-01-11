# HWCI Runner

Minimal CLI runner that clones a repo at a commit SHA and runs Verilator stages from a JSON plan.

## Usage

```
python hwci.py run --repo <url> --sha <commit> --plan plan.json --out out_dir/
```

## Plan format (v0)

```
{
  "stages": [
    {
      "name": "lint",
      "type": "lint",
      "sources": ["src/rtl/top.sv"],
      "include_dirs": ["src/rtl/include"],
      "defines": ["SYNTHESIS"],
      "flags": ["-Wall"]
    },
    {
      "name": "build",
      "type": "build",
      "top": "top",
      "sources": ["src/rtl/top.sv", "src/tb/tb_top.sv"],
      "exe": ["src/tb/tb_main.cpp"],
      "flags": ["-O3"]
    },
    {
      "name": "sim",
      "type": "sim",
      "args": ["+seed=1"]
    }
  ]
}
```

Notes:
- All paths are relative to the repo root after checkout.
- `sim` uses the binary from the most recent build stage (default `obj_dir/V<top>`). You can override with `binary` (path relative to repo root).

## Output structure

```
<out_dir>/
  checkout/
  artifacts/
    lint/
      lint.log
    build/
      build.log
      obj_dir/
    sim/
      sim.log
  results.json
```
