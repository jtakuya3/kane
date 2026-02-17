"""CLI entry point for kane.

Usage:
    python -m kane protocol-a     # Run Protocol A (condition comparison)
    python -m kane protocol-b     # Print Protocol B stage guide
    python -m kane analyze        # Analyze collected trial data
"""

import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m kane <command>")
        print()
        print("Commands:")
        print("  protocol-a   Run Protocol A experiments (interactive)")
        print("  protocol-b   Show Protocol B stage guide")
        print("  analyze      Analyze collected trial data")
        sys.exit(1)

    command = sys.argv[1]

    if command == "protocol-a":
        from experiments.protocol_a import run_full_protocol
        run_full_protocol()

    elif command == "protocol-b":
        from experiments.protocol_b import print_stage_guide
        print_stage_guide()

    elif command == "analyze":
        from kane.analyzer import print_comparison_table
        print_comparison_table()

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
