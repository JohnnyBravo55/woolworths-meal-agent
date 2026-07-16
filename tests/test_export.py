"""Tests for export functionality."""

from pathlib import Path

from shared.models import GroceryLineItem, ResolvedGroceryList
from woolworths_adapter.export import export_csv, export_markdown


def test_export_markdown_and_csv(tmp_path: Path):
    resolved = ResolvedGroceryList(
        items=[
            GroceryLineItem(
                ingredient="milk",
                sku="12345",
                product_name="Anchor Milk 2L",
                quantity=1,
                unit_price=4.50,
                line_total=4.50,
                product_url="https://www.woolworths.co.nz/shop/productdetails?stockcode=12345",
            )
        ],
        total=4.50,
        budget_nzd=100,
        within_budget=True,
    )

    md = export_markdown(resolved, output_dir=tmp_path)
    csv = export_csv(resolved, output_dir=tmp_path)

    assert md.exists()
    assert csv.exists()
    assert "Anchor Milk" in md.read_text(encoding="utf-8")
    assert "12345" in csv.read_text(encoding="utf-8")
