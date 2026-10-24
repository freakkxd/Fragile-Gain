#!/usr/bin/env python3
"""Скриншоты для README на демо-данных.

Рисует настоящее окно Fragile Gain средствами GTK (без снимка экрана, поэтому в кадр
не попадает ничего личного) и подменяет данные: приложения, выходы, язык, тему.
Настройки пользователя и аудиосистема не затрагиваются.

Использование:
  python3 docs/make_screenshots.py                      # все сценарии в обеих темах → docs/screenshots/{light,dark}/*.png
  python3 docs/make_screenshots.py overview             # один сценарий
  python3 docs/make_screenshots.py --theme=dark         # только тёмная тема (без стилей)
  python3 docs/make_screenshots.py glass arasaka        # отдельные кадры типов/тем → docs/screenshots/styles/
Нужны PyGObject, GTK 4, libadwaita и Pillow.
"""
import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "screenshots"

# ── сценарии: язык, тема, меню, приложения (разные в каждом кадре) ───────────
# приложение: (подпись, имя в .desktop для иконки, громкость, звучит?, заглушено?,
#              название играющего, служебное?, [вложенные такого же вида])
def app(label, hint, vol=100, live=False, mute=False, title="", system=False, kids=()):
    return dict(label=label, hint=hint, vol=vol, live=live, mute=mute, title=title,
                system=system, kids=list(kids))


SCENARIOS = {
    "overview": dict(
        lang="ru", menu=None, master=("Built-in Audio Analog Stereo", 62, False),
        apps=[
            app("Anki", "anki", 90, live=False, kids=[
                app("mpv", "mpv", 100, live=True, title="привет_hello_0412.mp3")]),
            app("Brave", "brave", 100, live=True,
                title="Daft Punk — Veridis Quest"),
            app("Claude", "claude", 100),
            app("Discord", "discord", 75, live=True, title="Игровая · голосовой канал"),
            app("Telegram", "telegram", 94),
            app("noctalia-qs", "noctalia-qs", 100, system=True),
            app("pipewire", "", 100, system=True),
            app("wireplumber", "", 100, system=True),
            app("xdg-desktop-portal", "", 100, system=True),
        ]),
    "english": dict(
        lang="en", menu=None, master=("MiniFuse 2 Main Output L/R", 100, False),
        apps=[
            app("Dopamine", "dopamine", 85, live=True, title="Radiohead — Weird Fishes"),
            app("OBS Studio", "obs", 65, live=False, mute=True),
            app("qBittorrent", "qbittorrent", 100),
            app("Steam", "steam", 100, live=True, kids=[
                app("steamwebhelper", "steam", 100, live=True)]),
            app("VLC media player", "vlc", 135, live=True,
                title="Hans Zimmer — Cornfield Chase"),
            app("pactl", "", 100, system=True),
            app("pavucontrol", "pavucontrol", 100, system=True),
            app("pw-cat", "", 100, system=True),
        ]),
    "outputs": dict(
        lang="ru", menu="outputs", master=("Built-in Audio Analog Stereo", 48, False),
        apps=[
            app("Firefox", "", 100, live=True, title="Tiny Desk Concert - YouTube"),
            app("Lutris", "lutris", 100, live=False, kids=[
                app("wine64-preloader", "", 70, live=True)]),
            app("Spotify", "", 55, live=True, title="Daft Punk — Get Lucky"),
            app("Strawberry", "", 100, live=True, title="Nujabes — Feather"),
            app("Visual Studio Code", "code", 100),
            app("Vivaldi", "", 100, live=True, title="Lofi Girl — beats to study"),
            app("YouTube Music", "", 80, mute=True),
            app("WirePlumber", "", 100, system=True),
            app("xdg-desktop-portal-gtk", "", 100, system=True),
        ]),
    "language": dict(
        lang="de", menu="language", master=("MiniFuse 2 Main Output L/R", 80, False),
        apps=[
            app("Audacity", "", 100, live=True, title="Aufnahme_2025-10-21.wav"),
            app("Chromium", "", 100, live=True, title="Podcast #142: Linux-Audio"),
            app("Thunderbird", "", 100),
            app("Zoom", "", 60, mute=True),
            app("gnome-shell", "", 100, system=True),
            app("pipewire-pulse", "", 100, system=True),
        ]),
    "japanese": dict(
        lang="ja", menu=None, master=("USB Audio DAC", 70, False),
        apps=[
            app("Plex", "", 100, live=True, title="久石譲 — Summer"),
            app("Rhythmbox", "", 100, kids=[
                app("gst-play-1.0", "", 85, live=True, title="坂本龍一 — Merry Christmas")]),
            app("Signal", "", 100),
            app("Slack", "", 45, mute=True),
            app("kwin_wayland", "", 100, system=True),
            app("xdg-desktop-portal-kde", "", 100, system=True),
        ]),
    "ukrainian": dict(
        lang="uk", menu=None, master=("HDMI / DisplayPort (HP X24c)", 90, False),
        apps=[
            app("Audacious", "", 100, live=True, title="Океан Ельзи — Обійми"),
            app("Chrome", "", 100, mute=True),
            app("Viber", "", 120, live=True, title="Голосовий дзвінок"),
            app("Kodi", "", 100, kids=[
                app("ffplay", "", 100, live=True, title="intro_video.mp4")]),
            app("pipewire", "", 100, system=True),
            app("tracker-miner-fs", "", 100, system=True),
            app("xdg-desktop-portal", "", 100, system=True),
        ]),
}

# Типы интерфейса и темы Fragile: кадр снимается один раз (в docs/screenshots/styles/).
# window="appearance" — снимок окна «Оформление» поверх микшера.
STYLES = {
    "classic": dict(scenario="overview", appearance={"color_scheme": "dark", "design": "classic"}),
    "glass": dict(scenario="overview", appearance={"color_scheme": "dark", "design": "glass"}),
    "glass-light": dict(scenario="english", appearance={"color_scheme": "light", "design": "glass"}),
    "arasaka": dict(scenario="overview", appearance={"builtin_theme": "arasaka"}),
    "sorai": dict(scenario="english", appearance={"builtin_theme": "sorai", "design": "classic"}),
    "matcha-compact": dict(scenario="ukrainian", appearance={"builtin_theme": "matcha", "density": "compact"}),
    "appearance": dict(scenario="overview", appearance={"color_scheme": "dark"}, window="appearance"),
    "appearance-glass": dict(scenario="overview", appearance={"builtin_theme": "denno", "design": "glass"},
                             window="appearance"),
}

OUTPUTS = [  # (имя, подпись, «мёртвый», скрыт)
    ("builtin", "Built-in Audio Analog Stereo", False, False),
    ("minifuse", "MiniFuse 2 Main Output L/R", False, False),
    ("hdmi", "HDMI / DisplayPort (HP X24c)", True, False),
    ("loop", "MiniFuse 2 Loopback L/R", False, True),
    ("bt", "WH-1000XM5 (Bluetooth)", True, True),
]


def load_module():
    sys.argv = ["x"]
    loader = importlib.machinery.SourceFileLoader("fg", str(ROOT / "appmixer"))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("fg", loader))
    loader.exec_module(mod)
    return mod


def run_scenario(name, theme):
    """Один сценарий в одной теме (отдельный процесс): отрисовать окно, сохранить PNG."""
    style = STYLES.get(theme[len("style:"):]) if theme.startswith("style:") else None
    if style:
        sc = dict(SCENARIOS[style["scenario"]], theme=theme, appearance=style["appearance"],
                  window=style.get("window"))
        out_dir, out_name = OUT / "styles", theme[len("style:"):]
    else:
        sc = dict(SCENARIOS[name], theme=theme, appearance={"color_scheme": theme}, window=None)
        out_dir, out_name = OUT / theme, name
    m = load_module()
    from gi.repository import Adw, GLib, Gdk, Graphene, Gtk

    tmp = Path(tempfile.mkdtemp())
    m.UI_FILE = tmp / "ui.json"
    m.OUTPUTS_FILE = tmp / "outputs.json"
    ui = {"show_system": True, "lang": sc["lang"]}
    ui.update(sc["appearance"])
    m.UI_FILE.write_text(json.dumps(ui))
    m.OUTPUTS_FILE.write_text(json.dumps(
        {"hidden": [o[0] for o in OUTPUTS if o[3]], "hotkey": "<Control>XF86AudioMute"}))
    m.set_language(sc["lang"])

    def icon_for(hint):
        found = m.desktop_lookup(hint) if hint else None
        return (m.resolve_icon(found["icon"]) if found else "") or ""

    def build_rows():
        rows = []

        def make(spec, parent=None):
            r = {
                "key": ("%s/%s" % (parent["label"], spec["label"])) if parent else spec["label"],
                "label": spec["label"], "title": spec["title"], "sub": "",
                "icon": icon_for(spec["hint"]), "parent": parent["label"] if parent else "",
                "parent_key": parent["key"] if parent else None, "depth": 1 if parent else 0,
                "names": [spec["label"].lower()], "own_names": [], "ident": {}, "binaries": [],
                "streams": [], "targets": [], "clients": [], "phantoms": [], "children": [],
                "live": spec["live"], "volume": spec["vol"], "mute": spec["mute"], "pids": [],
                "system": spec["system"] or bool(parent and parent["system"]),
            }
            rows.append(r)
            for kid in spec["kids"]:
                r["children"].append(make(kid, r))
            # родитель «звучит», если звучит хотя бы один вложенный источник
            r["live"] = r["live"] or any(k["live"] for k in r["children"])
            return r

        for spec in sc["apps"]:
            make(spec)
        for r in rows:
            r["sub"] = m.state_text(r)
        rows.sort(key=lambda r: (r["system"], (r["parent"] or r["label"]).lower(),
                                 r["depth"], r["label"].lower()))
        return rows

    m.collect = build_rows
    label, vol, mute = sc["master"]
    m.master_info = lambda: {"name": "demo", "label": label, "volume": vol, "mute": mute}
    m.list_outputs = lambda: [
        {"name": n, "label": l, "dead": d, "hidden": h, "default": n == "builtin"}
        for n, l, d, h in OUTPUTS]
    m.pactl_json = lambda what: []

    # тот же app-id, что у программы (подхватываются правила окна компоновщика), но без
    # единственного экземпляра — рядом может работать настоящий микшер
    from gi.repository import Gio
    app_ = Adw.Application(application_id=m.APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
    SCALE = 2

    def render(widget, w=None, h=None):
        """Виджет → PIL-изображение (в двойном разрешении)."""
        from PIL import Image
        import io
        w = w or widget.get_width()
        h = h or widget.get_height()
        paintable = Gtk.WidgetPaintable.new(widget)
        snap = Gtk.Snapshot()
        snap.scale(SCALE, SCALE)
        paintable.snapshot(snap, w, h)
        node = snap.to_node()
        renderer = widget.get_native().get_renderer()
        texture = renderer.render_texture(node, Graphene.Rect().init(0, 0, w * SCALE, h * SCALE))
        return Image.open(io.BytesIO(texture.save_to_png_bytes().get_data())).convert("RGBA")

    tries = {"n": 0}

    def finish(win):
        """Снимок; если окно ещё не успело отрисоваться — повторяем через 0,6 с."""
        try:
            return finish_once(win)
        except TypeError:
            tries["n"] += 1
            if tries["n"] > 6:
                raise
            GLib.timeout_add(600, lambda: finish(win))
            return False

    def finish_once(win):
        from PIL import Image, ImageChops, ImageDraw, ImageFilter
        W, H = win.get_width(), win.get_height()
        shot = render(win, W, H)
        radius = m.WINDOW_RADIUS * SCALE
        mask = Image.new("L", shot.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, shot.width - 1, shot.height - 1), radius, fill=255)
        shot.putalpha(ImageChops.multiply(shot.getchannel("A"), mask))

        if sc["menu"] and not sc["window"]:
            pop = win.master.out_pop if sc["menu"] == "outputs" else win.lang_popover
            anchor = win.master.out_button if sc["menu"] == "outputs" else win.lang_button
            if pop.get_width() < 10:
                raise TypeError("popover is not laid out yet")
            pimg = render(pop, pop.get_width(), pop.get_height())
            ok, pt = anchor.compute_point(win, Graphene.Point().init(anchor.get_width() / 2, anchor.get_height()))
            px = int(pt.x * SCALE - pimg.width / 2)
            px = max(12 * SCALE, min(shot.width - pimg.width - 12 * SCALE, px))
            py = int(pt.y * SCALE) + 4 * SCALE
            sh = Image.new("RGBA", shot.size, (0, 0, 0, 0))
            ImageDraw.Draw(sh).rounded_rectangle(
                (px + 2, py + 8, px + pimg.width - 2, py + pimg.height), 14 * SCALE, fill=(0, 0, 0, 120))
            shot.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10 * SCALE)))
            shot.alpha_composite(pimg, (px, py))

        pad = 34 * SCALE
        canvas = Image.new("RGBA", (shot.width + 2 * pad, shot.height + 2 * pad), (0, 0, 0, 0))
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            (pad, pad + 10 * SCALE, pad + shot.width, pad + shot.height + 10 * SCALE), radius, fill=(0, 0, 0, 150))
        canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(16 * SCALE)))
        canvas.alpha_composite(shot, (pad, pad))
        out_dir.mkdir(parents=True, exist_ok=True)
        canvas.save(out_dir / ("%s.png" % out_name), optimize=True)
        print("saved", out_dir / ("%s.png" % out_name))
        app_.quit()
        return False

    def activate(a):
        m.install_css()
        win = m.MixerWindow(a)
        m.apply_appearance(win)
        win.set_default_size(880, 10)
        win.present()

        def step():
            win.refresh()
            win._fit_height()                          # высота окна строго по содержимому
            if sc["window"] == "appearance":
                aw = m.AppearanceWindow(win)
                aw.set_default_size(720, 1180)
                aw.present()
                GLib.timeout_add(1200, lambda: finish(aw))
                return False
            if sc["menu"] == "outputs":
                win.master.out_pop.set_autohide(False)     # окно может быть не в фокусе
                win.master.out_button.popup()
            elif sc["menu"] == "language":
                win.lang_popover.set_autohide(False)
                win.lang_button.popup()
            GLib.timeout_add(900, lambda: finish(win))
            return False
        GLib.timeout_add(1800, step)
        GLib.timeout_add(20000, lambda: (app_.quit(), False)[1])

    app_.connect("activate", activate)
    app_.run([])


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    themes = [a[len("--theme="):] for a in sys.argv[1:] if a.startswith("--theme=")] or ["light", "dark"]
    styles_only = [a for a in args if a in STYLES]
    names = [a for a in args if a not in STYLES] or ([] if styles_only else list(SCENARIOS))
    for n in names:
        if n not in SCENARIOS:
            sys.exit("неизвестный сценарий: %s (есть: %s; стили: %s)" % (n, ", ".join(SCENARIOS), ", ".join(STYLES)))
        for th in themes:
            subprocess.run([sys.executable, __file__, n, th, "--inner"], check=False)
    if "--theme=" not in " ".join(sys.argv) and (styles_only or not args):
        for key in styles_only or list(STYLES):          # типы интерфейса и встроенные темы
            subprocess.run([sys.executable, __file__, STYLES[key]["scenario"], "style:" + key, "--inner"], check=False)


if __name__ == "__main__":
    if "--inner" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--inner"]
        run_scenario(rest[0], rest[1])
    else:
        main()
