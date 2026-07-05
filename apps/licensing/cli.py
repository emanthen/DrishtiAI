"""
Convenience entry point — delegates to the installed package CLI.
Run: python cli.py <command>
Or after `pip install drishtiai-licensing`: drishti-license <command>
"""
from drishtiai_licensing.cli import cli

if __name__ == "__main__":
    cli()
