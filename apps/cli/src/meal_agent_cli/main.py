"""Interactive CLI for the Woolworths meal planning agent."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project folder (where .env lives), not just current directory
_project_root = Path(__file__).resolve().parents[4]
load_dotenv(_project_root / ".env")
load_dotenv(Path.cwd() / ".env")  # fallback if run from project root

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from agent.conversation import ConversationManager
from agent.orchestrator import MealAgentOrchestrator
from agent.review import ReviewGate

console = Console()


def _prompt_discovery() -> dict:
    """Run interactive discovery questionnaire."""
    answers: dict = {}
    console.print(
        Panel(
            "[bold]Welcome, Chef's Assistant[/bold]\n\n"
            "I'll help you plan simple, great meals and build your Woolworths shop. "
            "Let's start with a few questions.",
            title="Woolworths Meal Agent",
        )
    )

    for key, question, typ, opts in ConversationManager.QUESTIONS:
        default = opts.get("default")
        if typ is int:
            raw = Prompt.ask(question, default=str(default))
            answers[key] = int(raw)
        elif typ is float:
            raw = Prompt.ask(question, default=str(default))
            answers[key] = float(raw)
        else:
            answers[key] = Prompt.ask(question, default=str(default))

    return answers


def _display_meal_plan(orchestrator: MealAgentOrchestrator) -> None:
    plan = orchestrator.state.meal_plan
    if not plan:
        return
    console.print(Panel(orchestrator.review.format_meal_plan_summary(plan), title="Meal Plan"))


def _display_products(orchestrator: MealAgentOrchestrator) -> None:
    resolved = orchestrator.state.resolved_list
    if not resolved:
        return
    console.print(Panel(orchestrator.review.format_product_list(resolved), title="Products"))


def _display_dinner_recipes(orchestrator: MealAgentOrchestrator) -> None:
    plan = orchestrator.state.meal_plan
    if not plan:
        return
    dinners = [m for m in plan.meals if m.slot.value == "dinner"]
    if not dinners:
        return
    console.print(
        Panel(
            orchestrator.review.format_dinner_recipes(plan),
            title="Chef's Dinner Recipes",
        )
    )


def _display_recipes(orchestrator: MealAgentOrchestrator) -> None:
    plan = orchestrator.state.meal_plan
    if not plan:
        return
    console.print(Panel(orchestrator.review.format_recipes(plan), title="Recipes"))


def _print_cart_summary(
    *,
    success_count: int,
    added_total: float,
    failure_count: int,
    skipped_offline: int,
    cart_subtotal: float | None,
    errors: list[str],
) -> None:
    console.print(
        f"Cart: {success_count} added (${added_total:.2f}), "
        f"{failure_count} failed, {skipped_offline} need manual search"
    )
    if cart_subtotal is not None:
        console.print(f"Woolworths trolley subtotal: ${cart_subtotal:.2f}")
        if added_total > 0 and cart_subtotal + 5 < added_total:
            console.print(
                Panel(
                    f"[bold yellow]Trolley (${cart_subtotal:.2f}) is lower than items "
                    f"we added (${added_total:.2f}).[/bold yellow]\n\n"
                    "Your session may have expired partway through. Run:\n"
                    "  meal-agent login\n"
                    "  meal-agent cart-retry --csv output/shopping_list_....csv",
                    title="Incomplete cart",
                )
            )
    for err in errors:
        console.print(f"  [yellow]{err}[/yellow]")


async def run_interactive(export_only: bool = False) -> int:
    orchestrator = MealAgentOrchestrator()
    review = ReviewGate()

    answers = _prompt_discovery()
    profile = await orchestrator.run_discovery(answers)

    allergy_msg = orchestrator.conversation.confirm_allergies(profile)
    if profile.allergies:
        console.print(Panel(allergy_msg, style="bold yellow"))
        if not Confirm.ask("Confirm allergies are correct?"):
            console.print("Please restart and re-enter allergies.")
            return 1

    console.print("\n[bold]Planning your meals...[/bold]")
    await orchestrator.generate_plan(profile)
    if orchestrator.planner._last_llm_error:
        console.print(
            Panel(
                orchestrator.planner._last_llm_error,
                title="OpenAI — using template meals",
                style="yellow",
            )
        )
    _display_meal_plan(orchestrator)

    if not Confirm.ask("Approve this meal plan?"):
        if Confirm.ask("Swap a meal?"):
            idx = int(Prompt.ask("Meal index to swap (0-based)", default="0"))
            orchestrator.state.meal_plan = orchestrator.planner.swap_meal(
                orchestrator.state.meal_plan,
                idx,
                profile,
            )
            _display_meal_plan(orchestrator)
        if not Confirm.ask("Approve updated plan?"):
            console.print("Plan not approved. Exiting.")
            return 0

    orchestrator.approve_plan(True)
    _display_dinner_recipes(orchestrator)

    console.print("\n[bold]Searching Woolworths for products...[/bold]")
    session_ok = await orchestrator.adapter.is_session_available()
    if not session_ok:
        console.print(
            "[yellow]Woolworths session not responding — run: meal-agent login[/yellow]\n"
            "[yellow]Will still attempt live search; unmatched items use estimates.[/yellow]"
        )
    else:
        orchestrator.resolver.offline_mode = False

    resolved = await orchestrator.resolve_products(profile, orchestrator.state.meal_plan)
    resolved, suggestions = await orchestrator.reconcile_budget(resolved, profile)

    if suggestions:
        table = Table(title="Budget Swap Suggestions")
        table.add_column("Ingredient")
        table.add_column("Savings")
        table.add_column("Suggestion")
        for s in suggestions[:5]:
            table.add_row(s.ingredient, f"${s.savings:.2f}", s.message)
        console.print(table)

    console.print(Panel(orchestrator.budget_engine.summarize(resolved), title="Budget"))
    if not resolved.within_budget:
        over = resolved.total - resolved.budget_nzd
        console.print(
            Panel(
                f"[bold red]Over budget by ${over:.2f}[/bold red]\n"
                "Some items were trimmed or swapped. Review the list carefully before approving.",
                title="Budget warning",
            )
        )
    _display_products(orchestrator)

    if profile.allergies:
        console.print(review.format_allergy_confirmation(profile))

    if not Confirm.ask("Approve this product list?"):
        console.print("Products not approved. Exporting list for manual shopping.")
        paths = await orchestrator.export_only(resolved)
        console.print(f"Exported: {', '.join(paths)}")
        _display_recipes(orchestrator)
        return 0

    orchestrator.approve_products(True)

    console.print(Panel(review.cart_disclaimer(), title="Cart Notice"))

    if export_only:
        paths = await orchestrator.export_only(resolved)
        console.print(f"[green]Exported shopping list:[/green] {', '.join(paths)}")
    elif Confirm.ask("Add approved items to your Woolworths cart?"):
        try:
            result = await orchestrator.add_to_cart(
                resolved,
                plan_approved=True,
                products_approved=True,
                allow_over_budget=Confirm.ask(
                    "Total is over budget. Add anyway?",
                    default=False,
                )
                if not resolved.within_budget
                else False,
            )
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            paths = await orchestrator.export_only(resolved)
            console.print(f"Exported list instead: {', '.join(paths)}")
            _display_recipes(orchestrator)
            return 0
        _print_cart_summary(
            success_count=result.success_count,
            added_total=result.added_total,
            failure_count=result.failure_count,
            skipped_offline=result.skipped_offline,
            cart_subtotal=result.cart_subtotal,
            errors=result.errors,
        )
        if result.success_count > 0:
            from woolworths_adapter.browser_open import open_cart_in_browser

            console.print("\n[bold]Opening Woolworths cart in your browser...[/bold]")
            open_cart_in_browser()
            console.print(
                "If the cart looks empty, make sure you are logged in to the same "
                "Woolworths account in your browser."
            )
        if orchestrator.state.export_paths:
            console.print(
                f"Fallback list exported: {', '.join(orchestrator.state.export_paths)}"
            )
    else:
        paths = await orchestrator.export_only(resolved)
        console.print(f"Exported: {', '.join(paths)}")

    _display_recipes(orchestrator)
    console.print("\n[bold green]Done![/bold green]")
    return 0


async def run_from_profile(
    profile_path: Path | str,
    *,
    auto_approve: bool = False,
    export_only: bool = False,
) -> int:
    """Run using a saved JSON profile (for repeat test runs)."""
    orchestrator = MealAgentOrchestrator()
    conv = ConversationManager()
    profile = conv.profile_from_file(profile_path)

    console.print(
        Panel(
            f"Loaded profile: [bold]{Path(profile_path).name}[/bold]\n"
            f"{profile.household_size} people · ${profile.budget_nzd} budget · "
            f"{profile.store_name or 'any store'}\n"
            f"Allergies: {', '.join(profile.allergies) or 'none'}",
            title="Saved profile",
        )
    )

    await orchestrator.run_discovery(conv.load_answers(profile_path))

    console.print("\n[bold]Planning your meals...[/bold]")
    await orchestrator.generate_plan(profile)
    if orchestrator.planner._last_llm_error:
        console.print(
            Panel(orchestrator.planner._last_llm_error, title="OpenAI", style="yellow")
        )
    _display_meal_plan(orchestrator)

    if not auto_approve and not Confirm.ask("Approve this meal plan?"):
        return 0
    orchestrator.approve_plan(True)
    _display_dinner_recipes(orchestrator)

    console.print("\n[bold]Searching Woolworths for products...[/bold]")
    if not await orchestrator.adapter.is_session_available():
        console.print(
            "[yellow]Woolworths session not responding — run: meal-agent login[/yellow]\n"
            "[yellow]Will still attempt live search; unmatched items use estimates.[/yellow]"
        )
    else:
        orchestrator.resolver.offline_mode = False

    resolved = await orchestrator.resolve_products(profile, orchestrator.state.meal_plan)
    resolved, suggestions = await orchestrator.reconcile_budget(resolved, profile)

    console.print(Panel(orchestrator.budget_engine.summarize(resolved), title="Budget"))
    console.print(
        f"Addable to cart: ${resolved.addable_total:.2f} ({len(resolved.addable_items())} items) · "
        f"Manual: ${resolved.offline_total:.2f} ({len(resolved.offline_items())} items)"
    )
    _display_products(orchestrator)

    if not auto_approve and not Confirm.ask("Approve this product list?"):
        await orchestrator.export_only(resolved)
        return 0
    orchestrator.approve_products(True)

    if export_only:
        paths = await orchestrator.export_only(resolved)
        console.print(f"Exported: {', '.join(paths)}")
    else:
        try:
            result = await orchestrator.add_to_cart(
                resolved,
                plan_approved=True,
                products_approved=True,
                allow_over_budget=auto_approve and not resolved.within_budget,
            )
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            await orchestrator.export_only(resolved)
            return 1

        _print_cart_summary(
            success_count=result.success_count,
            added_total=result.added_total,
            failure_count=result.failure_count,
            skipped_offline=result.skipped_offline,
            cart_subtotal=result.cart_subtotal,
            errors=result.errors,
        )
        if result.success_count > 0:
            from woolworths_adapter.browser_open import open_cart_in_browser

            console.print("\n[bold]Opening Woolworths cart in your browser...[/bold]")
            open_cart_in_browser()

    _display_recipes(orchestrator)
    console.print("\n[bold green]Done![/bold green]")
    return 0


async def run_cart_retry(csv_path: str, *, missing_only: bool = True) -> int:
    """Add missing items from an exported shopping list CSV."""
    from woolworths_adapter.browser_open import open_cart_in_browser
    from woolworths_adapter.cart_retry import retry_cart_from_csv

    path = Path(csv_path)
    console.print(Panel(f"Retrying cart from:\n[bold]{path}[/bold]", title="Cart retry"))

    result = await retry_cart_from_csv(path, missing_only=missing_only)
    _print_cart_summary(
        success_count=result.success_count,
        added_total=result.added_total,
        failure_count=result.failure_count,
        skipped_offline=result.skipped_offline,
        cart_subtotal=result.cart_subtotal,
        errors=result.errors,
    )
    if result.skipped_in_cart:
        console.print(
            f"[dim]{result.skipped_in_cart} items already in trolley — skipped[/dim]"
        )
    if result.success_count > 0:
        console.print("\n[bold]Opening Woolworths cart in your browser...[/bold]")
        open_cart_in_browser()
    return 0 if result.failure_count == 0 else 1


async def run_demo(export_only: bool = True) -> int:
    """Non-interactive demo with sample profile."""
    orchestrator = MealAgentOrchestrator()
    profile = ConversationManager.sample_profile()

    console.print(Panel("Running demo with sample profile", title="Demo"))
    console.print(f"Profile: {profile.household_size} people, ${profile.budget_nzd} budget")

    state = await orchestrator.run_full_pipeline(
        profile,
        auto_approve=True,
        export_only=export_only,
        auto_swap=True,
    )

    if state.meal_plan:
        _display_meal_plan(orchestrator)

    if state.resolved_list:
        console.print(Panel(orchestrator.budget_engine.summarize(state.resolved_list)))
        _display_products(orchestrator)

    if state.export_paths:
        console.print(f"Exported: {', '.join(state.export_paths)}")

    if state.cart_errors:
        for err in state.cart_errors:
            console.print(f"[yellow]{err}[/yellow]")

    return 0


async def run_login() -> int:
    """Log in to Woolworths NZ and cache session for live pricing/cart."""
    from woolies_cli.browser import AuthError
    from woolworths_adapter.login import run_login_interactive_cli, session_exists

    console.print(
        Panel(
            "This opens woolworths.co.nz in your default browser.\n\n"
            "• Sign in on woolworths.co.nz — your password is never stored here\n"
            "• Use Chrome, Edge, or Firefox (cookies are copied from your browser)\n"
            "• Only session cookies are saved locally on your machine",
            title="Woolworths Login",
        )
    )

    if session_exists():
        console.print("[green]Existing session found.[/green] Re-login will refresh it.")

    try:
        await run_login_interactive_cli()
    except AuthError as exc:
        console.print(f"[red]Login failed:[/red] {exc}")
        return 1
    except Exception as exc:
        console.print(f"[red]Login error:[/red] {exc}")
        return 1

    console.print("[bold green]Logged in successfully.[/bold green]")
    console.print("Try: meal-agent demo  (or meal-agent for the full flow)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Woolworths NZ Meal Planning Agent")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "demo", "login", "cart-retry"],
        help="run (interactive), demo, login, or cart-retry (from exported CSV)",
    )
    parser.add_argument(
        "--csv",
        type=str,
        help="Shopping list CSV for cart-retry",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="cart-retry: add every CSV row, even if SKU is already in trolley",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Skip cart, export shopping list only",
    )
    parser.add_argument(
        "--profile",
        type=str,
        help="Run from saved JSON profile (e.g. profiles/ferrymead_gluten_free.json)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Auto-approve plan and products (for test runs with --profile)",
    )
    args = parser.parse_args()

    try:
        if args.command == "demo":
            code = asyncio.run(run_demo(export_only=True))
        elif args.command == "login":
            code = asyncio.run(run_login())
        elif args.command == "cart-retry":
            if not args.csv:
                console.print("[red]cart-retry requires --csv path/to/shopping_list.csv[/red]")
                code = 1
            else:
                code = asyncio.run(run_cart_retry(args.csv, missing_only=not args.all))
        elif args.profile:
            code = asyncio.run(
                run_from_profile(
                    args.profile,
                    auto_approve=args.yes,
                    export_only=args.export_only,
                )
            )
        else:
            code = asyncio.run(run_interactive(export_only=args.export_only))
        sys.exit(code)
    except KeyboardInterrupt:
        console.print("\nCancelled.")
        sys.exit(130)


if __name__ == "__main__":
    main()
