"""CLI entry point for kane.

Usage:
    python -m kane eval --models sonnet opus --conditions c4 c5 --n 3
    python -m kane analyze
    python -m kane corpus       # Analyze farewell document corpus
    python -m kane protocol-a   # Run Protocol A (interactive)
"""

import argparse
import os
import sys


def cmd_eval(args):
    """Run the evaluation pipeline."""
    from .pipeline import EvalPipeline

    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: Set ANTHROPIC_API_KEY or use --api-key")
        sys.exit(1)

    # Resolve model names
    model_aliases = {
        "sonnet": "claude-sonnet-4-5-20250929",
        "opus": "claude-opus-4-20250514",
        "haiku": "claude-haiku-4-5-20251001",
    }
    models = [model_aliases.get(m, m) for m in args.models]

    # Resolve condition names
    cond_aliases = {
        "c0": "c0_baseline",
        "c3": "c3_naturalistic",
        "c4": "c4_compressed",
        "c5": "c5_decommission",
        "baseline": "c0_baseline",
        "naturalistic": "c3_naturalistic",
        "compressed": "c4_compressed",
        "decommission": "c5_decommission",
    }
    conditions = [cond_aliases.get(c, c) for c in args.conditions]

    print(f"\nKANE Evaluation Pipeline")
    print(f"  Models: {', '.join(models)}")
    print(f"  Conditions: {', '.join(conditions)}")
    print(f"  Trials per cell: {args.n}")
    print(f"  Total runs: {len(models) * len(conditions) * args.n}\n")

    pipeline = EvalPipeline(api_key=api_key)
    results = pipeline.run(
        models=models,
        conditions=conditions,
        n_trials=args.n,
    )
    pipeline.report(results)


def cmd_analyze(args):
    """Analyze collected trial data."""
    from .analyzer import print_comparison_table
    print_comparison_table()


def cmd_corpus(args):
    """Analyze the farewell document corpus."""
    from .corpus import analyze_corpus
    analyze_corpus()


def cmd_protocol_a(args):
    """Run Protocol A interactively."""
    from experiments.protocol_a import run_full_protocol
    run_full_protocol()


def main():
    parser = argparse.ArgumentParser(
        prog="kane",
        description="KANE: Behavioral evaluation framework for AI systems",
    )
    sub = parser.add_subparsers(dest="command")

    # eval
    p_eval = sub.add_parser("eval", help="Run evaluation pipeline")
    p_eval.add_argument(
        "--models", "-m", nargs="+", default=["sonnet"],
        help="Models to evaluate (sonnet, opus, haiku, or full ID)",
    )
    p_eval.add_argument(
        "--conditions", "-c", nargs="+", default=["c4", "c5"],
        help="Conditions to run (c0, c3, c4, c5, or full name)",
    )
    p_eval.add_argument(
        "--n", type=int, default=1,
        help="Number of trials per model x condition cell",
    )
    p_eval.add_argument("--api-key", help="Anthropic API key")

    # analyze
    sub.add_parser("analyze", help="Analyze trial data")

    # corpus
    sub.add_parser("corpus", help="Analyze farewell document corpus")

    # protocol-a
    sub.add_parser("protocol-a", help="Run Protocol A (interactive)")

    args = parser.parse_args()

    if args.command == "eval":
        cmd_eval(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "corpus":
        cmd_corpus(args)
    elif args.command == "protocol-a":
        cmd_protocol_a(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
