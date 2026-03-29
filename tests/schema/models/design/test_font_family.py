import pathlib

import pytest
import rendercv_fonts

from rendercv.schema.models.design.font_family import available_font_families

icon_font_families = {"Font Awesome 7"}
typst_built_in_font_families = {
    "Libertinus Serif",
    "New Computer Modern",
    "DejaVu Sans Mono",
}
# Fonts that ship with macOS/Windows and are resolved by Typst via system font search.
# These are not bundled in rendercv-fonts but are available on most target platforms.
system_font_families = {"Arial", "Calibri", "Georgia", "Helvetica"}

fork_fonts_dir = (
    pathlib.Path(__file__).parents[4]
    / "src"
    / "rendercv"
    / "renderer"
    / "fonts"
)


def _fork_bundled_font_families() -> set[str]:
    """Return font family names inferred from files in renderer/fonts/."""
    names = set()
    for f in fork_fonts_dir.iterdir():
        if f.suffix.lower() in {".ttf", ".otf"}:
            names.add(f.stem)
    return names


@pytest.mark.parametrize(
    "font_family",
    [f for f in rendercv_fonts.available_font_families if f not in icon_font_families],
)
def test_bundled_fonts_are_in_available_font_families(font_family):
    assert font_family in available_font_families


@pytest.mark.parametrize(
    "font_family",
    [f for f in available_font_families if f not in typst_built_in_font_families],
)
def test_no_extra_fonts_in_available_font_families(font_family):
    allowed = (
        set(rendercv_fonts.available_font_families)
        | system_font_families
        | _fork_bundled_font_families()
    )
    assert font_family in allowed
