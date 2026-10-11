"""CLI for collect / normalize / report."""

from __future__ import annotations

import json
import logging
import sys

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from src.paths import ensure_data_dirs

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Debug logging")
def main(verbose: bool) -> None:
    """Bengaluru women's safety — data collection CLI."""
    _setup_logging(verbose)
    ensure_data_dirs()


@main.command("collect")
@click.option(
    "--source",
    "source_family",
    default=None,
    help="Optional family: opencity, gis_opencity, india_data_portal, data_gov_in, ncrb_pdf, ncrb_backfill, gis_github",
)
def collect_cmd(source_family: str | None) -> None:
    """Download online sources into data/raw and data/reference."""
    from src.collectors import collect, summarize

    console.print(f"[bold]Collecting[/bold] source_family={source_family or 'ALL'}")
    results = collect(source_family)
    summary = summarize(results)

    table = Table(title="Collect results")
    table.add_column("source_id")
    table.add_column("ok")
    table.add_column("files")
    table.add_column("message/error")
    for r in results:
        msg = (r.message or r.error or "")[:80]
        # Avoid Windows cp1252 crashes on Hindi labels in paths/messages
        msg = msg.encode("ascii", "replace").decode("ascii")
        table.add_row(
            r.source_id,
            "yes" if r.ok else "no",
            str(len(r.files)),
            msg,
        )
    console.print(table)
    console.print(json.dumps({k: summary[k] for k in ("total", "ok", "failed", "files")}, indent=2))
    # Soft exit: do not fail hard if some optional portals flake
    if summary["ok"] == 0 and summary["total"] > 0:
        sys.exit(2)


@main.command("normalize")
def normalize_cmd() -> None:
    """Build staged crime_aggregate_fact from latest raw downloads."""
    from src.normalize.pipeline import build_staging

    manifest = build_staging()
    console.print("[bold green]Staging built[/bold green]")
    console.print_json(data=manifest)


@main.command("clean")
def clean_cmd() -> None:
    """Build end-user canonical annual tables from staged facts."""
    from src.normalize.canonical import build_canonical

    result = build_canonical()
    console.print("[bold green]Canonical dataset built[/bold green]")
    console.print_json(
        data={
            "canonical_rows": result["canonical_rows"],
            "years": result["years"],
            "geo_names": result["geo_names"],
            "quality_tier_counts": result["quality_tier_counts"],
            "paths": result["paths"],
        }
    )


@main.command("report")
def report_cmd() -> None:
    """Run QC and write docs/coverage_report.md."""
    from src.qc.coverage import generate_coverage_report
    from src.qc.checks import run_checks

    path = generate_coverage_report()
    checks = run_checks()
    table = Table(title="QC")
    table.add_column("check")
    table.add_column("ok")
    table.add_column("detail")
    for c in checks:
        table.add_row(c.name, "PASS" if c.ok else "FAIL", c.detail)
    console.print(table)
    console.print(f"Wrote [bold]{path}[/bold]")


@main.command("run-all")
@click.option("--source", "source_family", default=None)
def run_all_cmd(source_family: str | None) -> None:
    """collect → normalize → clean → report."""
    ctx = click.get_current_context()
    ctx.invoke(collect_cmd, source_family=source_family)
    ctx.invoke(normalize_cmd)
    ctx.invoke(clean_cmd)
    ctx.invoke(report_cmd)


if __name__ == "__main__":
    main()