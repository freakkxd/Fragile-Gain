"""Fragile ecosystem look for GTK4 / libadwaita apps (Python, PyGObject).

Copy this file and assets/fragile-tokens.json into the app, then:

    import gtk_fragile
    gtk_fragile.apply(window, theme="arasaka", design="sharp", density="regular")

Colours come from fragile-tokens.json (generated from Fragile Notes by
fragile-design/scripts/gen_tokens.py); the design type only changes shape.
GTK has no backdrop blur: the glass type is translucent panels with a lit rim
over the accent backdrop, and becomes opaque with reduce_transparency.
"""
import json
import re
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

TOKENS = json.loads((Path(__file__).resolve().parent / "fragile-tokens.json").read_text(encoding="utf-8"))
DESIGNS = ("sharp", "classic", "glass")
DENSITY = {"compact": (34, 22), "regular": (40, 26), "comfortable": (46, 30)}
_provider = None


def _rgb(value: str):
    value = value.strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", value)
    if m:
        n = int(m.group(1), 16)
        return (n >> 16) & 255, (n >> 8) & 255, n & 255, 1.0
    m = re.fullmatch(r"rgba?\(([^)]+)\)", value)
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]
        return int(parts[0]), int(parts[1]), int(parts[2]), float(parts[3]) if len(parts) > 3 else 1.0
    raise ValueError(value)


def _css(value: str, alpha: float = 1.0) -> str:
    r, g, b, a = _rgb(value)
    return f"rgba({r},{g},{b},{a * alpha:g})"


def tokens(theme: str = "", scheme: str = "dark", accent: str = "") -> dict:
    """Resolved colours: a built-in theme, or the base dark/light; an own accent wins."""
    t = dict(TOKENS.get(theme) or TOKENS[scheme])
    if accent:
        t["--interactive-accent"] = t["--text-accent"] = accent
    return t


def build_css(theme: str = "", scheme: str = "dark", design: str = "sharp", density: str = "regular",
              mono_labels: bool = True, reduce_transparency: bool = False, accent: str = "") -> str:
    t = tokens(theme, scheme, accent)
    dark = t["scheme"] == "dark"
    header, row = DENSITY.get(density, DENSITY["regular"])
    c = {k.lstrip("-").replace("-", "_"): v for k, v in t.items() if k.startswith("--") and "var(" not in v and "hsl" not in v}
    acc = c.get("interactive_accent", "#3db6f2")
    on_acc = c.get("text_on_accent", "#000000" if dark else "#ffffff")
    bg, side, alt = c["background_primary"], c["background_secondary"], c["background_primary_alt"]
    text, muted, faint = c["text_normal"], c["text_muted"], c["text_faint"]
    border, border_h = c["background_modifier_border"], c["background_modifier_border_hover"]
    hover, active, field = c["background_modifier_hover"], c["background_modifier_active"], c["background_modifier_form_field"]

    radius = {"sharp": (0, 0, 0), "classic": (4, 8, 12), "glass": (10, 14, 22)}[design]
    rs, rm, rl = radius
    out = [f"""
@define-color window_bg_color {bg};
@define-color view_bg_color {bg};
@define-color window_fg_color {text};
@define-color view_fg_color {text};
@define-color headerbar_bg_color {side};
@define-color headerbar_fg_color {text};
@define-color sidebar_bg_color {side};
@define-color card_bg_color {alt};
@define-color card_fg_color {text};
@define-color popover_bg_color {alt};
@define-color popover_fg_color {text};
@define-color dialog_bg_color {alt};
@define-color accent_bg_color {acc};
@define-color accent_color {c.get('text_accent', acc)};
@define-color accent_fg_color {on_acc};
@define-color borders {border};

window, .fragile-app {{ background-color: {bg}; color: {text}; }}
.fragile-header {{ min-height: {header}px; padding: 0 8px; border-bottom: 1px solid {border}; }}
.fragile-row {{ min-height: {row}px; padding: 0 8px; border-radius: {rs}px; }}
.fragile-row:hover {{ background-color: {hover}; }}
.fragile-row.active, .fragile-row:selected {{ background-color: {active}; }}
.fragile-muted {{ color: {muted}; }}
.fragile-faint {{ color: {faint}; }}
.fragile-label {{ color: {faint}; font-size: 10px; font-weight: 600; letter-spacing: 0.06em; }}
.fragile-card {{ background-color: {alt}; border: 1px solid {border}; border-radius: {rl}px; padding: 14px 16px; }}
.fragile-panel {{ background-color: {side}; border: 1px solid {border}; border-radius: {rl}px; }}
button {{ border-radius: {rs}px; }}
button.suggested-action {{ background: {acc}; color: {on_acc}; }}
entry {{ background-color: {field}; border-radius: {rs}px; border: 1px solid {border}; }}
entry:focus-within {{ border-color: {acc}; }}
popover > contents {{ background-color: {alt}; border: 1px solid {border_h}; border-radius: {rm}px; }}
scale trough highlight {{ background: {acc}; }}
"""]
    if design == "sharp":
        shadow = "rgba(0,0,0,0.32)" if dark else "rgba(0,0,0,0.1)"
        label_font = "font-family: monospace; text-transform: uppercase; letter-spacing: 0.08em; font-size: 10.5px;" if mono_labels else ""
        out.append(f"""
* {{ border-radius: 0; }}
.fragile-row.active, .fragile-row:selected {{ box-shadow: inset 2px 0 0 {acc}; }}
.fragile-card, .fragile-panel, button {{ box-shadow: none; }}
popover > contents {{ box-shadow: 6px 6px 0 0 {shadow}; }}
.fragile-label {{ {label_font} }}
switch {{ border-radius: 0; border: 1px solid {border_h}; }}
switch > slider {{ border-radius: 0; }}
""")
    elif design == "classic":
        out.append(f"""
.fragile-card, .fragile-panel {{ box-shadow: 0 1px 2px rgba(0,0,0,{0.28 if dark else 0.03}), 0 4px 10px rgba(0,0,0,{0.18 if dark else 0.05}); }}
""")
    else:
        tint = _css(bg, 1.0 if reduce_transparency else 0.58)
        tint_strong = _css(bg, 1.0 if reduce_transparency else 0.78)
        rim = "rgba(255,255,255,0.16)" if dark else "rgba(255,255,255,0.7)"
        rim_top = "rgba(255,255,255,0.34)" if dark else "rgba(255,255,255,0.95)"
        wash = _css(acc, 0.0 if reduce_transparency else 0.30)
        out.append(f"""
window, .fragile-app {{ background-image: radial-gradient(circle at 8% 0%, {wash}, transparent 60%); }}
.fragile-panel, .fragile-card {{ background-color: {tint}; border: 1px solid {rim}; box-shadow: inset 0 1px 0 {rim_top}, 0 10px 30px -8px rgba(0,0,0,{0.45 if dark else 0.22}); }}
.fragile-header {{ border-bottom-color: transparent; }}
.fragile-row {{ border-radius: 10px; }}
.fragile-row.active, .fragile-row:selected {{ background-color: {_css(acc, 0.2)}; }}
button {{ border-radius: 999px; }}
button.suggested-action {{ box-shadow: inset 0 1px 0 rgba(255,255,255,0.35), 0 4px 14px -4px {_css(acc, 0.7)}; }}
entry {{ border-radius: 12px; }}
popover > contents {{ background-color: {tint_strong}; border-color: {rim}; border-radius: 16px; }}
switch {{ border-radius: 999px; }}
switch:checked {{ background-color: {acc}; }}
switch > slider {{ border-radius: 999px; background: #ffffff; }}
""")
    return "".join(out)


def apply(window: Gtk.Widget | None = None, **kw) -> str:
    """Install (or replace) the app-wide stylesheet; tags the window with design-<type>."""
    global _provider
    css = build_css(**kw)
    display = Gdk.Display.get_default()
    if _provider is None:
        _provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(display, _provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
    _provider.load_from_string(css)
    if window is not None:
        for d in DESIGNS:
            window.remove_css_class(f"design-{d}")
        window.add_css_class(f"design-{kw.get('design', 'sharp')}")
    return css
