"""
SYNAPSE AI — Research System Evaluation CLI
============================================
Executes standardized benchmark evaluation to measure empirical system performance
instead of relying solely on subjective LLM quality scores.

Usage:
  python evaluate.py                          # Run full 50-query benchmark in offline mode
  python evaluate.py -n 10                    # Run first 10 queries
  python evaluate.py --k 5                    # Evaluate Retrieval Precision@5 and Recall@5
  python evaluate.py --mode live -n 3         # Run 3 queries against live multi-agent pipeline
  python evaluate.py --verbose                # Detailed per-query logs
"""

import argparse
import os
import sys

from evaluation.config import EvaluationConfig
from evaluation.dataset import load_benchmark_dataset
from evaluation.runner import EvaluationRunner


def parse_args():
    parser = argparse.ArgumentParser(
        description="SYNAPSE AI Empirical Research Evaluation Framework",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=os.path.join("evaluation", "datasets", "research_benchmark_50.json"),
        help="Path to the JSON benchmark dataset",
    )
    parser.add_argument(
        "-n", "--num-queries",
        type=int,
        default=None,
        help="Maximum number of queries to evaluate (default: all queries in dataset)",
    )
    parser.add_argument(
        "-k", "--top-k",
        type=int,
        default=5,
        help="Cutoff K for Retrieval Precision@K and Recall@K",
    )
    parser.add_argument(
        "--mode",
        choices=["offline", "live"],
        default="offline",
        help="Evaluation mode: 'offline' (reference corpus) or 'live' (real-time pipeline)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="eval_results",
        help="Directory to save machine-readable JSON evaluation reports",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable detailed per-query metric outputs",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Build evaluation configuration isolated from production
    config = EvaluationConfig(
        dataset_path=args.dataset,
        default_k=args.top_k,
        mode=args.mode,
        max_queries=args.num_queries,
        output_dir=args.output_dir,
        verbose=args.verbose,
    )

    # Ensure dataset exists or generate it automatically
    if not os.path.exists(config.dataset_path):
        print(f"[eval] Benchmark dataset not found at {config.dataset_path}. Generating standard 50-query dataset...")
        from evaluation.generate_dataset import generate_benchmark_file
        generate_benchmark_file(config.dataset_path)

    # Load dataset
    dataset = load_benchmark_dataset(config.dataset_path)
    total_in_ds = len(dataset)
    run_count = args.num_queries or total_in_ds

    print(f"\n====================================================================")
    print(f"             LAUNCHING SYNAPSE AI BENCHMARK EVALUATION              ")
    print(f"====================================================================")
    print(f"Dataset:         {dataset.name} ({dataset.version})")
    print(f"Dataset Path:    {config.dataset_path}")
    print(f"Queries to Run:  {run_count} of {total_in_ds}")
    print(f"Execution Mode:  {config.mode}")
    print(f"Retrieval Top-K: {config.default_k}")
    print(f"Output Directory:{config.output_dir}")
    print(f"====================================================================\n")

    # Run evaluation
    runner = EvaluationRunner(config)
    summary = runner.run_benchmark(dataset=dataset, max_queries=args.num_queries)

    # Display human-readable summary
    print("\n" + summary.format_human_readable())

    # Highlight saved machine-readable results
    latest_files = sorted(
        [os.path.join(config.output_dir, f) for f in os.listdir(config.output_dir) if f.startswith("eval_report_")],
        key=os.path.getmtime,
        reverse=True
    ) if os.path.exists(config.output_dir) else []

    if latest_files:
        print(f"\nMachine-readable JSON report: {latest_files[0]}")

    # Return exit code: 0 if no queries failed, 1 if all failed
    if summary.successful_queries == 0 and summary.total_queries > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
