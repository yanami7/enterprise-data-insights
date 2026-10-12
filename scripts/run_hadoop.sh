#!/usr/bin/env bash
# Requires an existing Linux Hadoop cluster and Python3 on every worker.
set -euo pipefail
cd "$(dirname "$0")/.."
input=${1:-data/normalized.jsonl}
test -f "$input"
run_id="data-insights-$(date +%Y%m%d-%H%M%S)-$$"
hdfs_base="/user/$(id -un)/$run_id"
hdfs dfs -mkdir -p "$hdfs_base/input"
hdfs dfs -put "$input" "$hdfs_base/input/orders.jsonl"
mapred streaming -D mapreduce.job.name="data-insights-daily-channel" \
  -files "jobs/mapper.py,jobs/reducer.py" \
  -input "$hdfs_base/input" -output "$hdfs_base/output" \
  -mapper "python3 mapper.py" -reducer "python3 reducer.py"
hdfs dfs -cat "$hdfs_base/output/part-*" > "data/hadoop-result-$run_id.tsv"
printf 'Result: data/hadoop-result-%s.tsv\nHDFS: %s\n' "$run_id" "$hdfs_base"
