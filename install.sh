#!/usr/bin/env bash
# Fragile Gain — installer / установщик
#
# Поддерживаемые семейства дистрибутивов (пакеты ставятся автоматически):
#   Arch (Manjaro, EndeavourOS, CachyOS…)   — pacman
#   Debian (Ubuntu, Mint, Pop!_OS, …)       — apt
#   Fedora (RHEL-подобные, Nobara…)         — dnf
#   openSUSE (Tumbleweed, Leap, SLES)       — zypper
# На остальных дистрибутивах скрипт только проверяет зависимости и говорит, чего не хватает.
#
# Установка — в домашний каталог пользователя (root не нужен, root понадобится
# только для установки системных пакетов):
#   ~/.local/share/fragile-gain/   программа, переводы, иконки; config/ хранит настройки
#   ~/.local/bin/fragile-gain      команда запуска
#   ~/.local/share/applications/ru.fragilich.appmixer.desktop   запись в меню приложений
#
# Использование: ./install.sh [--check] [--yes] [--no-deps] [--uninstall [--purge]]
#                              [--distro ID] [--dry-run] [--help]

set -u

APP_TITLE="Fragile Gain"
APP_ID="ru.fragilich.appmixer"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
PREFIX="$DATA_HOME/fragile-gain"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"

MIN_PY="3.9"      # минимальный Python
MIN_GTK=12        # GTK 4.12+  (Gtk.CssProvider.load_from_string)
MIN_ADW=4         # libadwaita 1.4+ (Adw.ToolbarView)

MODE=install      # install | check | uninstall
ASSUME_YES=0
SKIP_DEPS=0
PURGE=0
DRY=0
FORCE_DISTRO=""

# ── сообщения: русский, если локаль русская ─────────────────────────────────
case "${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}" in ru*) UI=ru ;; *) UI=en ;; esac
t() { if [ "$UI" = ru ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }

if [ -t 1 ]; then
    B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; D=$'\033[2m'; N=$'\033[0m'
else
    B=""; G=""; Y=""; R=""; D=""; N=""
fi
info() { printf '%s\n' "${B}==>${N} $*"; }
ok()   { printf '  %s\n' "${G}✔${N} $*"; }
warn() { printf '  %s\n' "${Y}!${N} $*"; }
bad()  { printf '  %s\n' "${R}✘${N} $*"; }
die()  { printf '%s\n' "${R}$(t 'Ошибка' 'Error'):${N} $*" >&2; exit 1; }

usage() {
    cat <<EOF
$APP_TITLE — $(t 'установщик' 'installer')

$(t 'Использование' 'Usage'): ./install.sh [options]

  (no options)      $(t 'проверить зависимости, доустановить недостающее, установить программу' 'check dependencies, install missing ones, install the app')
  --check           $(t 'только проверить зависимости, ничего не менять' 'only check dependencies, change nothing')
  --yes, -y         $(t 'не задавать вопросов (согласиться на установку пакетов)' 'do not ask questions (agree to install packages)')
  --no-deps         $(t 'не ставить системные пакеты (зависимости всё равно проверяются)' 'do not install system packages (dependencies are still checked)')
  --uninstall       $(t 'удалить программу (настройки остаются)' 'remove the app (settings are kept)')
  --purge           $(t 'вместе с --uninstall: удалить и настройки' 'with --uninstall: also remove settings')
  --distro ID       $(t 'считать дистрибутив ID (arch, debian, fedora, suse) — для проверки' 'pretend the distro is ID (arch, debian, fedora, suse) — for testing')
  --dry-run         $(t 'только показать, что было бы сделано' 'only show what would be done')
  -h, --help        $(t 'эта справка' 'this help')
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --check) MODE=check ;;
        --yes|-y) ASSUME_YES=1 ;;
        --no-deps) SKIP_DEPS=1 ;;
        --uninstall) MODE=uninstall ;;
        --purge) PURGE=1 ;;
        --dry-run) DRY=1 ;;
        --distro) shift; FORCE_DISTRO="${1:-}" ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "$(t 'неизвестный параметр' 'unknown option'): $1" ;;
    esac
    shift
done

run() {   # выполнить команду (или только показать при --dry-run)
    if [ "$DRY" = 1 ]; then printf '  %s+ %s%s\n' "$D" "$*" "$N"; return 0; fi
    "$@"
}

ask() {   # ask "вопрос ru" "question en"  → 0 если да
    [ "$ASSUME_YES" = 1 ] && return 0
    [ -t 0 ] || return 1
    local reply
    read -r -p "$(t "$1" "$2") [Y/n] " reply
    case "$reply" in ""|y|Y|yes|да|Да|д|Д) return 0 ;; *) return 1 ;; esac
}

# ── дистрибутив → семейство и пакеты ────────────────────────────────────────
detect_family() {
    local id="" like="" line
    if [ -n "$FORCE_DISTRO" ]; then id="$FORCE_DISTRO"; else
        if [ -r /etc/os-release ]; then
            id="$(. /etc/os-release; printf '%s' "${ID:-}")"
            like="$(. /etc/os-release; printf '%s' "${ID_LIKE:-}")"
        fi
    fi
    for line in $id $like; do
        case "$line" in
            arch|manjaro|endeavouros|cachyos|garuda|artix|arcolinux) echo arch; return ;;
            debian|ubuntu|linuxmint|pop|elementary|zorin|raspbian|kali|neon|devuan) echo debian; return ;;
            fedora|rhel|centos|rocky|almalinux|nobara|ol) echo fedora; return ;;
            opensuse*|suse|sles|sled) echo suse; return ;;
        esac
    done
    echo unknown
}

FAMILY="$(detect_family)"

pkg_list() {   # пакеты нужного семейства
    case "$FAMILY" in
        arch)   echo "python python-gobject gtk4 libadwaita gdk-pixbuf2 librsvg libpulse pipewire pipewire-pulse wireplumber libnotify adwaita-icon-theme" ;;
        debian) echo "python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gdkpixbuf-2.0 librsvg2-common pulseaudio-utils pipewire-bin pipewire-pulse wireplumber libnotify-bin adwaita-icon-theme" ;;
        fedora) echo "python3 python3-gobject gtk4 libadwaita gdk-pixbuf2 librsvg2 pulseaudio-utils pipewire pipewire-utils pipewire-pulseaudio wireplumber libnotify adwaita-icon-theme" ;;
        suse)   echo "python3 python3-gobject typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 typelib-1_0-GdkPixbuf-2_0 gdk-pixbuf-loader-rsvg pulseaudio-utils pipewire pipewire-pulseaudio pipewire-tools wireplumber libnotify-tools adwaita-icon-theme" ;;
    esac
}

pkg_cmd() {    # команда установки (без sudo)
    case "$FAMILY" in
        arch)   echo "pacman -S --needed --noconfirm" ;;
        debian) echo "apt-get install -y" ;;
        fedora) echo "dnf install -y" ;;
        suse)   echo "zypper --non-interactive install" ;;
    esac
}

# ── проверка зависимостей ───────────────────────────────────────────────────
PROBLEMS=()       # что не так (обязательное)
WARNINGS=()       # что не критично

check_deps() {
    PROBLEMS=(); WARNINGS=()
    info "$(t 'Проверка зависимостей' 'Checking dependencies')"

    # Python
    if command -v python3 >/dev/null 2>&1; then
        if python3 -c "import sys; sys.exit(0 if sys.version_info >= tuple(map(int, '$MIN_PY'.split('.'))) else 1)"; then
            ok "Python $(python3 -c 'import platform; print(platform.python_version())')"
        else
            bad "Python $(python3 -c 'import platform; print(platform.python_version())') — $(t 'нужен' 'need') ≥ $MIN_PY"
            PROBLEMS+=("python")
        fi
    else
        bad "python3 — $(t 'не найден' 'not found')"; PROBLEMS+=("python")
    fi

    # PyGObject, GTK 4, libadwaita, GdkPixbuf (+ загрузчик SVG)
    if command -v python3 >/dev/null 2>&1; then
        local out
        out="$(python3 - "$MIN_GTK" "$MIN_ADW" <<'PY' 2>/dev/null
import sys
min_gtk, min_adw = int(sys.argv[1]), int(sys.argv[2])
try:
    import gi
except Exception:
    print("MISSING gi"); sys.exit(0)
def need(ns, ver):
    try:
        gi.require_version(ns, ver)
        return __import__("gi.repository", fromlist=[ns])
    except Exception:
        return None
ok = True
if need("Gtk", "4.0") is None:
    print("MISSING gtk"); ok = False
else:
    from gi.repository import Gtk
    v = (Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version())
    print("GTK %d.%d.%d" % v)
    if v[1] < min_gtk: print("OLD gtk %d.%d" % v[:2])
if need("Adw", "1") is None:
    print("MISSING adw"); ok = False
else:
    from gi.repository import Adw
    v = (Adw.get_major_version(), Adw.get_minor_version(), Adw.get_micro_version())
    print("ADW %d.%d.%d" % v)
    if v[1] < min_adw: print("OLD adw %d.%d" % v[:2])
if need("GdkPixbuf", "2.0") is None:
    print("MISSING pixbuf")
else:
    from gi.repository import GdkPixbuf
    names = [f.get_name() for f in GdkPixbuf.Pixbuf.get_formats()]
    print("PIXBUF ok")
    if "svg" not in names: print("MISSING svg")
try:
    from gi.repository import Gio, GLib
except Exception:
    print("MISSING gio")
PY
)"
        local line
        while IFS= read -r line; do
            case "$line" in
                "MISSING gi")     bad "PyGObject — $(t 'не установлен' 'not installed')"; PROBLEMS+=("gi") ;;
                "MISSING gtk")    bad "GTK 4 (typelib) — $(t 'не найден' 'not found')"; PROBLEMS+=("gtk") ;;
                "MISSING adw")    bad "libadwaita (typelib) — $(t 'не найден' 'not found')"; PROBLEMS+=("adw") ;;
                "MISSING pixbuf") bad "GdkPixbuf (typelib) — $(t 'не найден' 'not found')"; PROBLEMS+=("pixbuf") ;;
                "MISSING svg")    bad "$(t 'загрузчик SVG для GdkPixbuf (librsvg)' 'GdkPixbuf SVG loader (librsvg)') — $(t 'не найден' 'not found')"; PROBLEMS+=("svg") ;;
                "MISSING gio")    bad "Gio/GLib — $(t 'не найдены' 'not found')"; PROBLEMS+=("gi") ;;
                "OLD gtk"*)       bad "GTK ${line#OLD gtk } — $(t "нужен" "need") ≥ 4.$MIN_GTK"; PROBLEMS+=("oldgtk") ;;
                "OLD adw"*)       bad "libadwaita ${line#OLD adw } — $(t "нужен" "need") ≥ 1.$MIN_ADW"; PROBLEMS+=("oldadw") ;;
                "GTK "*)          ok "GTK ${line#GTK }" ;;
                "ADW "*)          ok "libadwaita ${line#ADW }" ;;
                "PIXBUF ok")      ok "GdkPixbuf" ;;
            esac
        done <<<"$out"
    fi

    # Команды звукового сервера
    local c
    for c in pactl pw-dump pw-cat; do
        if command -v "$c" >/dev/null 2>&1; then ok "$c"; else bad "$c — $(t 'не найден' 'not found')"; PROBLEMS+=("cmd:$c"); fi
    done
    if command -v notify-send >/dev/null 2>&1; then ok "notify-send $(t '(уведомления о смене выхода)' '(output-switch notifications)')"
    else warn "notify-send — $(t 'нет; уведомления о смене выхода не будут показываться' 'missing; output-switch notifications will not be shown')"; WARNINGS+=("notify-send"); fi

    # Работающий звуковой сервер (не блокирует установку)
    if command -v pactl >/dev/null 2>&1; then
        local server
        server="$(pactl info 2>/dev/null | sed -n 's/^Server Name: //p')"
        case "$server" in
            *PipeWire*) ok "$(t 'звуковой сервер' 'audio server'): $server" ;;
            "") warn "$(t 'звуковой сервер сейчас недоступен (запустите pipewire-pulse или войдите в сессию)' 'audio server is not reachable right now (start pipewire-pulse / log in to a session)')" ;;
            *) warn "$(t 'звуковой сервер' 'audio server'): $server — $(t 'программа рассчитана на PipeWire + WirePlumber, на PulseAudio часть функций может не работать' 'the app is designed for PipeWire + WirePlumber; some features may not work on plain PulseAudio')" ;;
        esac
    fi
    return 0
}

# ── установка системных пакетов ─────────────────────────────────────────────
install_packages() {
    if [ "$FAMILY" = unknown ]; then
        warn "$(t 'Дистрибутив не распознан — пакеты нужно поставить вручную.' 'Distribution not recognised — please install the packages manually.')"
        print_manual_hint
        return 1
    fi
    local pm pkgs sudo=""
    pm="$(pkg_cmd)"; pkgs="$(pkg_list)"
    if [ "$(id -u)" -ne 0 ]; then
        if command -v sudo >/dev/null 2>&1; then sudo="sudo"
        else
            warn "$(t 'sudo не найден — выполните от root:' 'sudo not found — run as root:')"
            printf '    %s %s\n' "$pm" "$pkgs"
            return 1
        fi
    fi
    info "$(t 'Нужны системные пакеты' 'System packages needed') ($FAMILY)"
    printf '    %s\n' "$pkgs"
    if ! ask "Установить недостающие пакеты (потребуется пароль sudo)?" "Install the missing packages (sudo password required)?"; then
        warn "$(t 'Пропущено по вашему выбору.' 'Skipped by your choice.')"
        printf '    %s %s %s\n' "${sudo:+sudo}" "$pm" "$pkgs"
        return 1
    fi
    [ "$FAMILY" = debian ] && run $sudo apt-get update
    # shellcheck disable=SC2086
    run $sudo $pm $pkgs || { warn "$(t 'Менеджер пакетов вернул ошибку.' 'The package manager reported an error.')"; return 1; }
    return 0
}

print_manual_hint() {
    cat <<EOF
    $(t 'Нужны (названия пакетов зависят от дистрибутива)' 'Required (package names vary by distribution)'):
      Python ≥ $MIN_PY + PyGObject, GTK ≥ 4.$MIN_GTK, libadwaita ≥ 1.$MIN_ADW, GdkPixbuf + librsvg,
      pactl (PulseAudio utils), pw-dump и pw-cat (PipeWire), $(t 'желательно' 'optional'): wireplumber, notify-send
EOF
}

# ── установка / удаление ────────────────────────────────────────────────────
do_install() {
    [ -f "$SRC_DIR/appmixer" ] || die "$(t 'не найден файл appmixer рядом с установщиком' 'file appmixer not found next to the installer')"
    local update=0
    [ -d "$PREFIX" ] && update=1
    info "$([ "$update" = 1 ] && t 'Обновление' 'Updating' || t 'Установка' 'Installing') → $PREFIX"

    run mkdir -p "$PREFIX/config" "$BIN_DIR" "$APPS_DIR" "$ICON_DIR"
    run install -m 0755 "$SRC_DIR/appmixer" "$PREFIX/appmixer"
    # переводы и данные заменяем целиком; config/ с настройками пользователя не трогаем
    run rm -rf "$PREFIX/locales" "$PREFIX/data"
    run cp -a "$SRC_DIR/locales" "$PREFIX/locales"
    run mkdir -p "$PREFIX/data"
    run cp -a "$SRC_DIR/data/silence.wav" "$PREFIX/data/silence.wav"
    run cp -a "$SRC_DIR/data/fragile-gain.svg" "$PREFIX/data/fragile-gain.svg"
    run ln -sf "$PREFIX/appmixer" "$BIN_DIR/fragile-gain"
    ok "$(t 'программа' 'application'): $PREFIX"
    ok "$(t 'команда запуска' 'launcher'): $BIN_DIR/fragile-gain"

    # иконка и запись в меню приложений
    run cp -a "$SRC_DIR/data/fragile-gain.svg" "$ICON_DIR/$APP_ID.svg"
    if [ "$DRY" = 1 ]; then
        printf '  %s+ write %s/%s.desktop%s\n' "$D" "$APPS_DIR" "$APP_ID" "$N"
    else
        cat >"$APPS_DIR/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=$APP_TITLE
GenericName=Volume mixer
GenericName[ru]=Микшер громкости
Comment=Per-application volume mixer for PipeWire
Comment[ru]=Громкость каждого приложения отдельно
Exec=$PREFIX/appmixer
Icon=$APP_ID
Terminal=false
Categories=AudioVideo;Audio;Mixer;
Keywords=volume;mixer;audio;sound;pipewire;громкость;микшер;звук;
StartupWMClass=$APP_ID
StartupNotify=false
EOF
    fi
    ok "$(t 'запись в меню приложений' 'application menu entry'): $APPS_DIR/$APP_ID.desktop"
    command -v update-desktop-database >/dev/null 2>&1 && run update-desktop-database "$APPS_DIR" >/dev/null 2>&1
    command -v gtk-update-icon-cache >/dev/null 2>&1 && run gtk-update-icon-cache -f -t "$DATA_HOME/icons/hicolor" >/dev/null 2>&1

    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *) warn "$BIN_DIR $(t 'нет в PATH — команда fragile-gain не найдётся; добавьте его в PATH или запускайте из меню приложений' 'is not in PATH — add it, or launch from the application menu')" ;;
    esac

    # быстрая проверка, что установленная копия действительно запускается
    if [ "$DRY" != 1 ] && command -v python3 >/dev/null 2>&1; then
        if python3 "$PREFIX/appmixer" --outputs >/dev/null 2>&1; then
            ok "$(t 'пробный запуск прошёл' 'smoke test passed')"
        else
            warn "$(t 'пробный запуск не удался (возможно, не запущен звуковой сервер)' 'smoke test failed (maybe the audio server is not running)')"
        fi
    fi
    echo
    info "$(t 'Готово.' 'Done.') $(t 'Запуск' 'Run'): ${B}fragile-gain${N}  $(t 'или из меню приложений' 'or from the application menu')"
    echo "    $(t 'Переключение выхода из командной строки' 'Switch output from the command line'): fragile-gain --next-output"
}

do_uninstall() {
    info "$(t 'Удаление' 'Uninstalling')"
    if [ -d "$PREFIX" ]; then
        if [ "$PURGE" = 1 ]; then
            run rm -rf "$PREFIX"
            ok "$(t 'удалено вместе с настройками' 'removed, including settings'): $PREFIX"
        else
            run rm -rf "$PREFIX/locales" "$PREFIX/data" "$PREFIX/appmixer"
            ok "$(t 'удалено (настройки сохранены в' 'removed (settings kept in') $PREFIX/config)"
        fi
    else
        warn "$(t 'программа не установлена' 'not installed'): $PREFIX"
    fi
    run rm -f "$BIN_DIR/fragile-gain" "$APPS_DIR/$APP_ID.desktop" "$ICON_DIR/$APP_ID.svg"
    command -v update-desktop-database >/dev/null 2>&1 && run update-desktop-database "$APPS_DIR" >/dev/null 2>&1
    ok "$(t 'ссылка, запись меню и иконка удалены' 'launcher, menu entry and icon removed')"
}

# ── главное ─────────────────────────────────────────────────────────────────
[ "$(id -u)" -eq 0 ] && [ "$MODE" = install ] && warn "$(t 'Запуск от root: программа установится в домашний каталог root. Лучше запускать от обычного пользователя.' 'Running as root: the app will be installed into root'"'"'s home. Prefer a regular user.')"

case "$MODE" in
    uninstall) do_uninstall; exit 0 ;;
    check)
        info "$(t 'Дистрибутив' 'Distribution'): $FAMILY"
        check_deps
        if [ ${#PROBLEMS[@]} -eq 0 ]; then echo; ok "$(t 'Всё необходимое есть.' 'Everything required is present.')"; exit 0; fi
        echo; bad "$(t 'Не хватает' 'Missing'): ${PROBLEMS[*]}"
        [ "$FAMILY" != unknown ] && printf '    %s %s %s\n' "sudo" "$(pkg_cmd)" "$(pkg_list)" || print_manual_hint
        exit 1 ;;
esac

info "$(t 'Дистрибутив' 'Distribution'): $FAMILY"
check_deps
if [ ${#PROBLEMS[@]} -gt 0 ]; then
    echo
    if [ "$SKIP_DEPS" = 1 ]; then
        warn "$(t 'Пропуск установки пакетов (--no-deps).' 'Skipping package installation (--no-deps).')"
    else
        install_packages || true
        echo
        check_deps
    fi
fi

if [ ${#PROBLEMS[@]} -gt 0 ]; then
    echo
    bad "$(t 'Установка остановлена: не хватает' 'Installation stopped: missing') ${PROBLEMS[*]}"
    for p in "${PROBLEMS[@]}"; do
        case "$p" in
            oldgtk|oldadw) printf '    %s\n' "$(t "Версии GTK/libadwaita слишком старые: нужны GTK ≥ 4.$MIN_GTK и libadwaita ≥ 1.$MIN_ADW (Ubuntu 24.04+, Debian 13+, Fedora 39+, openSUSE Tumbleweed, актуальный Arch)." "GTK/libadwaita are too old: need GTK ≥ 4.$MIN_GTK and libadwaita ≥ 1.$MIN_ADW (Ubuntu 24.04+, Debian 13+, Fedora 39+, openSUSE Tumbleweed, current Arch).")" ;;
        esac
    done
    exit 1
fi

do_install
