"""CLI entry point for Kane."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kane import __version__
from kane.config.settings import Settings
from kane.gateway.server import Gateway


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="kane",
        description="Kane - Your personal AI assistant",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- start ---
    start_parser = subparsers.add_parser("start", help="Start the Kane gateway")
    start_parser.add_argument(
        "--config", type=str, default=None, help="Path to config file"
    )
    start_parser.add_argument(
        "--channel",
        type=str,
        nargs="+",
        default=None,
        help="Channels to enable (e.g. cli webhook)",
    )

    # --- onboard ---
    subparsers.add_parser("onboard", help="Run the onboarding wizard")

    # --- config ---
    config_parser = subparsers.add_parser("config", help="Show or edit configuration")
    config_parser.add_argument("--show", action="store_true", help="Print current config")
    config_parser.add_argument("--init", action="store_true", help="Create default config")

    args = parser.parse_args(argv)

    if args.command == "start":
        _cmd_start(args)
    elif args.command == "onboard":
        _cmd_onboard()
    elif args.command == "config":
        _cmd_config(args)
    else:
        parser.print_help()


def _cmd_start(args: argparse.Namespace) -> None:
    """Start the gateway."""
    config_path = Path(args.config) if args.config else None
    settings = Settings.load(config_path)

    if args.channel:
        settings.enabled_channels = args.channel

    if not settings.llm.api_key:
        print(
            "Warning: No LLM API key configured. "
            "Set it in ~/.kane/config.json or run 'kane onboard'."
        )
        print("Continuing with local-only mode (skills only, no LLM responses).\n")

    gateway = Gateway(settings)
    gateway.run()


def _cmd_onboard() -> None:
    """Interactive onboarding wizard."""
    print("=" * 50)
    print("  Welcome to Kane - Your Personal AI Assistant")
    print("=" * 50)
    print()

    settings = Settings()

    # LLM Provider
    print("Step 1: Choose your LLM provider")
    print("  1. OpenAI (GPT-4o)")
    print("  2. Anthropic (Claude)")
    print("  3. Custom (OpenAI-compatible endpoint)")
    choice = input("Select [1]: ").strip() or "1"

    if choice == "1":
        settings.llm.provider = "openai"
        settings.llm.model = "gpt-4o"
    elif choice == "2":
        settings.llm.provider = "anthropic"
        settings.llm.model = "claude-sonnet-4-20250514"
    elif choice == "3":
        settings.llm.provider = "custom"
        settings.llm.base_url = input("API base URL: ").strip()
        settings.llm.model = input("Model name: ").strip()

    # API Key
    print("\nStep 2: Enter your API key")
    api_key = input("API key: ").strip()
    settings.llm.api_key = api_key

    # Channels
    print("\nStep 3: Choose channels to enable")
    print("  1. CLI only (default)")
    print("  2. CLI + Webhook")
    ch_choice = input("Select [1]: ").strip() or "1"
    if ch_choice == "2":
        settings.enabled_channels = ["cli", "webhook"]

    # Save
    settings.save()
    print(f"\nConfiguration saved to {settings.config_dir / 'config.json'}")
    print("Run 'kane start' to launch your assistant!")


def _cmd_config(args: argparse.Namespace) -> None:
    """Show or initialize configuration."""
    if args.init:
        settings = Settings()
        settings.save()
        print(f"Default config created at {settings.config_dir / 'config.json'}")
    elif args.show:
        settings = Settings.load()
        import json
        print(json.dumps(settings._to_dict(), indent=2))
    else:
        settings = Settings.load()
        import json
        print(json.dumps(settings._to_dict(), indent=2))


if __name__ == "__main__":
    main()
