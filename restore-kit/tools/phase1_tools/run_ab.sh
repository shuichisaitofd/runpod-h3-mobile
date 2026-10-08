#!/bin/bash
# A then B: warmup (seed 1) + measured (seed 757358688076805); stop on first failure.
cd /workspace/runpod-slim
R=phase1_results; mkdir -p $R
for cond in ${CONDS:-A_t2va_5s B90_t2va_5s}; do
  for run in "warmup 1" "measure 757358688076805"; do
    set -- $run
    echo "=== $cond $1 $(date -Is)"
    python3 -I phase1_tools/run_bench.py phase1_$cond.json $2 "${cond}_$1" > $R/${cond}_$1.json || exit 1
    grep -E '"status"|total_s|sampling_s|peak_gpu' $R/${cond}_$1.json
    grep -q '"execution_success"' $R/${cond}_$1.json || { echo "FAILED"; exit 1; }
  done
done
echo "=== done $(date -Is)"
