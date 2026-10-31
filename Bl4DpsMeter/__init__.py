"""
Borderlands 4 DPS Meter: shows the damage you deal per second, in a small window on screen.

The game tells each character about every hit it deals, see native.py. Only your own character is
listened to, so it's cheap, and it's your damage only. The game only does this where the damage is
worked out, so it works solo and when hosting. A co-op guest doesn't get told anything.

The window is plain UMG built in code, like the notices in bl4-fix by flameaway.
https://github.com/flameaway/bl4-fix
"""

from __future__ import annotations

import ctypes
import re
import struct
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mods_base import (
    MODS_DIR,
    BaseOption,
    BoolOption,
    ButtonOption,
    NestedOption,
    SliderOption,
    SpinnerOption,
    build_mod,
    get_pc,
    hook,
    keybind,
)
from unrealsdk import construct_object, find_object, make_struct
from unrealsdk.hooks import Block, Type
from unrealsdk.logging import error, info
from unrealsdk.unreal import BoundFunction, UObject, WeakPointer, WrappedStruct

from . import meter, native

LOG_TAG = "[Borderlands 4 DPS Meter]"

# Everything the player reads comes in Polish and English, in that order.
Text = tuple[str, str]
POLISH = "pl"
ENGLISH = "en"
LANGUAGE_AUTO = "auto"
LANGUAGE_LABELS: dict[str, Text] = {
    LANGUAGE_AUTO: ("Automatycznie (jak w grze)", "Automatic (same as the game)"),
    POLISH: ("Polski", "Polski"),
    ENGLISH: ("English", "English"),
}
STEAM_APP_ID = 1285190
shown_language: str = ENGLISH


def say(text: Text) -> str:
    """Picks the text for the language in use."""
    return text[0] if shown_language == POLISH else text[1]


class LocalizedSpinner(SpinnerOption):
    """
    A choice whose entries read in the player's language. Its `key` stays the same whatever the
    language: that's what the code checks, and what the settings file keeps.
    """

    labels: dict[str, Text] = {}  # noqa: RUF012
    key: str = ""
    after_change: Callable[[], None] | None = None

    def key_for(self, value: str) -> str | None:
        """Finds which entry a value means, it may be in either language."""
        for key, texts in self.labels.items():
            if value == key or value in texts:
                return key
        return None

    def __setattr__(self, name: str, value: Any) -> None:
        if name != "value" or not self.labels:
            super().__setattr__(name, value)
            return
        self.key = self.key_for(value) or self.key
        super().__setattr__("value", say(self.labels[self.key]))
        if self.after_change is not None:
            self.after_change()

    def _to_json(self) -> str:
        return self.key

    def _from_json(self, value: Any) -> None:
        if self.key_for(str(value)) is None:
            super()._from_json(value)  # Which logs that it's sticking with the default
        else:
            self.value = str(value)

    def relabel(self) -> None:
        """Puts what's shown in the current language, which is no change to what's chosen."""
        self.choices = [say(text) for text in self.labels.values()]
        object.__setattr__(self, "value", say(self.labels[self.key]))


def localized_spinner(identifier: str, default: str, labels: dict[str, Text]) -> LocalizedSpinner:
    """Creates a choice from its entries' keys and what they're called."""
    option = LocalizedSpinner(identifier, default, list(labels))
    option.key = default
    option.labels = labels
    option.relabel()
    return option


RESET_AFTER_IDLE = "idle"
RESET_BY_HAND = "manual"

# Every option's texts, for when the language changes
labelled: list[tuple[Any, Text, Text]] = []


def show_label(option: Any, name: Text, description: Text) -> None:
    """Sets what an option is called, in the current language."""
    option.display_name = option.description_title = say(name)
    option.description = say(description)


def label(option: Any, name: Text, description: Text) -> Any:
    """Says what an option is called in the menus. Language changes go through what's kept here."""
    labelled.append((option, name, description))
    show_label(option, name, description)
    return option


how_to_count = label(
    localized_spinner(
        "How To Count",
        meter.MODE_FIGHT,
        {
            meter.MODE_FIGHT: ("Cała walka", "Whole fight"),
            meter.MODE_CLOCK: ("Cała walka z przerwami", "Whole fight with pauses"),
            meter.MODE_ACTIVE: ("Tylko czas trafiania", "Only time spent hitting"),
            meter.MODE_WINDOW: ("Ostatnie sekundy", "Last few seconds"),
        },
    ),
    ("Jak liczyć DPS", "How to count DPS"),
    (
        "Cała walka: obrażenia dzielone przez czas od pierwszego do ostatniego trafienia."
        " Z przerwami: czas biegnie dalej, więc DPS spada, gdy nie trafiasz."
        " Tylko czas trafiania: przerwy dłuższe niż sekunda się nie liczą."
        " Ostatnie sekundy: tylko obrażenia z wybranej liczby ostatnich sekund.",
        "Whole fight: damage over the time from the first hit to the last."
        " With pauses: the clock keeps running, so DPS falls while you're not hitting."
        " Only time spent hitting: pauses longer than a second don't count."
        " Last few seconds: only the damage from the chosen number of last seconds.",
    ),
)
window_seconds = label(
    SliderOption(identifier="Window Seconds", value=5.0, min_value=1.0, max_value=60.0, step=1.0, is_integer=False),
    ("Ile ostatnich sekund", "How many last seconds"),
    ("Działa, gdy wybrany jest sposób Ostatnie sekundy.", "Works while counting by Last few seconds."),
)
when_to_reset = label(
    localized_spinner(
        "When To Reset",
        RESET_AFTER_IDLE,
        {
            RESET_AFTER_IDLE: ("Po wyjściu z walki", "After leaving combat"),
            RESET_BY_HAND: ("Tylko ręcznie", "Only by hand"),
        },
    ),
    ("Kiedy resetować", "When to reset"),
    (
        "Poza walką oznacza, że przez ustawiony czas nie trafiłeś żadnego wroga.",
        "Out of combat means you haven't hit an enemy for the time set below.",
    ),
)
reset_seconds = label(
    SliderOption(identifier="Reset After Seconds", value=5.0, min_value=1.0, max_value=60.0, step=1.0, is_integer=False),
    ("Reset po tylu sekundach poza walką", "Reset after this many seconds out of combat"),
    ("Tyle sekund bez trafienia kończy walkę.", "This many seconds without a hit ends the fight."),
)
only_health_removed = label(
    BoolOption("Only Health Removed", False),
    ("Tylko zabrane zdrowie", "Only health removed"),
    (
        "Wyłączone: liczy pełne obrażenia, takie jak liczby na ekranie. Włączone: liczy tylko zdrowie, które"
        " wróg faktycznie stracił, więc ostatnie trafienie liczy się częściowo, a manekin treningowy prawie wcale.",
        "Off: counts the full damage, like the numbers on screen. On: counts only the health the enemy really"
        " lost, so the last hit counts in part, and a training dummy hardly at all.",
    ),
)
count_over_time = label(
    BoolOption("Count Damage Over Time", True),
    ("Licz obrażenia w czasie", "Count damage over time"),
    ("Podpalenie, korozja i podobne.", "Burning, corrosion and the like."),
)
count_companions = label(
    BoolOption("Count Companions", True),
    ("Licz towarzyszy", "Count companions"),
    (
        "Liczy trafienia przypisane przez grę Twojej postaci, ale zadane przez coś innego, na przykład przywołańca.",
        "Counts hits the game credits to your character but which something else dealt, like a summon.",
    ),
)
show_window = label(
    BoolOption("Show Window", True),
    ("Pokazuj okienko", "Show the window"),
    ("Okienko z DPS na ekranie.", "The DPS window on screen."),
)
show_details = label(
    BoolOption("Show Details", True),
    ("Pokazuj szczegóły", "Show details"),
    ("Suma obrażeń, czas, krytyki, najlepsze trafienie i zabójstwa.", "Total damage, time, crits, best hit and kills."),
)
show_last_fight = label(
    BoolOption("Show Last Fight", True),
    ("Pokazuj ostatnią walkę", "Show the last fight"),
    (
        "Po resecie zostaje wynik poprzedniej walki, żeby dało się go odczytać.",
        "After a reset, the previous fight's result stays, so it can still be read.",
    ),
)
window_x = label(
    SliderOption(identifier="Window X", value=98.5, min_value=0.0, max_value=100.0, step=0.5, is_integer=False),
    ("Pozycja w poziomie (%)", "Horizontal position (%)"),
    ("0 to lewa krawędź ekranu, 100 prawa.", "0 is the left edge of the screen, 100 the right."),
)
window_y = label(
    SliderOption(identifier="Window Y", value=26.0, min_value=0.0, max_value=100.0, step=0.5, is_integer=False),
    ("Pozycja w pionie (%)", "Vertical position (%)"),
    ("0 to góra ekranu, 100 dół.", "0 is the top of the screen, 100 the bottom."),
)
font_size = label(
    SliderOption(identifier="Font Size", value=28, min_value=10, max_value=48, step=1),
    ("Rozmiar DPS", "DPS size"),
    ("Wielkość głównej liczby. Szczegóły są mniejsze.", "The size of the main number. The details are smaller."),
)
STYLE_GAME = "game"
STYLE_COMPACT = "compact"
STYLE_MINIMAL = "minimal"
STYLE_NEON = "neon"
window_style = label(
    localized_spinner(
        "Window Style",
        STYLE_GAME,
        {
            STYLE_GAME: ("Jak w grze", "Like the game"),
            STYLE_COMPACT: ("Kompaktowy", "Compact"),
            STYLE_MINIMAL: ("Sam tekst", "Text only"),
            STYLE_NEON: ("Neon", "Neon"),
        },
    ),
    ("Styl okienka", "Window style"),
    (
        "Jak w grze: kolory i wielkie litery interfejsu gry. Kompaktowy: to samo, ale szczegóły w jednej linii."
        " Sam tekst: bez tła. Neon: mocne, jasne kolory.",
        "Like the game: the game's interface colours and capitals. Compact: the same, with the details on one line."
        " Text only: no background. Neon: strong, bright colours.",
    ),
)
RELOAD_OPTIONS = (window_x, window_y, font_size)

# --- What the game tells us -----------------------------------------------------------------------
HOSTILE = 2  # ETeamAttitude
ROLE_AUTHORITY = 3  # ENetRole
BIND_CHECK_INTERVAL = 0.5
UPDATE_INTERVAL = 0.1
MAX_ERRORS_LOGGED = 5
FLOAT_AT = struct.Struct("<f").unpack_from
POINTER_AT = struct.Struct("<Q").unpack_from

binder = native.Binder()
damage = meter.Meter()
listening: bool = False
listen_failed: bool = False
offsets: dict[str, int] = {}
flags: dict[str, tuple[int, int]] = {}
block_size: int = 0
# Damage type handle's bytes -> if it's damage over time
over_time_types: dict[bytes, bool] = {}
bound_pawn: WeakPointer = WeakPointer()
bound_address: int = 0
is_guest: bool = False
errors_logged: int = 0
fight_logged: meter.FightSummary | None = None
last_update: float = 0.0
last_bind_check: float = 0.0


def log_error_once(message: str) -> None:
    """Logs a problem, but not every frame."""
    global errors_logged  # noqa: PLW0603

    errors_logged += 1
    if errors_logged <= MAX_ERRORS_LOGGED:
        error(f"{LOG_TAG} {message}")


def set_up_listening() -> bool:
    """Reads where things are in the hit's details from the game, and checks it's all as expected."""
    global listening, listen_failed, block_size, offsets  # noqa: PLW0603

    if listening or listen_failed:
        return listening
    if not binder.ready():
        listen_failed = True
        return False
    try:
        offsets = native.struct_offsets()
        details = binder.func._find_prop("Details")
        for name in ("bWasCrit", "bIsDamageOverTime", "bCausedDeath"):
            prop = details.Struct._find_prop(name)
            flags[name] = (details.Offset_Internal + prop.Offset_Internal, int(getattr(prop, "FieldMask", 0xFF)) or 0xFF)
        sizes = {"damage": 4, "overkilldamage": 4, "damagetype": 8, "damageinstigator": 8, "attitudetowards": 1}
        end = max(offsets[name] + size for name, size in sizes.items())
        block_size = max(end, *(offset + 1 for offset, _ in flags.values()))
        if block_size > binder.func.ParamsSize:
            raise ValueError(f"fields end at {block_size}, past the {binder.func.ParamsSize} bytes of parameters")
    except Exception as ex:  # noqa: BLE001
        error(f"{LOG_TAG} The damage details changed shape: {ex!r}")
        listen_failed = True
        return False
    listening = True
    return True


def has_flag(raw: bytes, name: str) -> bool:
    """Reads one of the hit's yes or no fields."""
    offset, mask = flags[name]
    return bool(raw[offset] & mask)


def is_over_time(raw: bytes, args: WrappedStruct) -> bool:
    """Tells damage over time. The damage type's name says so too, and is only read once per type."""
    if has_flag(raw, "bIsDamageOverTime"):
        return True
    at = offsets["damagetype"]
    key = raw[at : at + 8]
    known = over_time_types.get(key)
    if known is None:
        try:
            known = str(args.Details.DamageType._name).lower().endswith("_status")
        except Exception:  # noqa: BLE001
            known = False
        over_time_types[key] = known
    return known


def record_hit(args: WrappedStruct) -> None:
    """Counts one hit. This runs for every one of them, so stays short, and mustn't break the game's damage."""
    try:
        raw = ctypes.string_at(args._get_address(), block_size)
        if raw[offsets["attitudetowards"]] != HOSTILE:
            return
        if not count_companions.value and POINTER_AT(raw, offsets["damageinstigator"])[0] != bound_address:
            return
        amount = FLOAT_AT(raw, offsets["damage"])[0]
        if only_health_removed.value:
            over = FLOAT_AT(raw, offsets["overkilldamage"])[0]
            if over > 0:
                amount -= over
        if not amount > 0:  # Also catches NaN
            return
        if not count_over_time.value and is_over_time(raw, args):
            return
        damage.add(time.monotonic(), amount, has_flag(raw, "bWasCrit"), has_flag(raw, "bCausedDeath"))
    except Exception as ex:  # noqa: BLE001
        log_error_once(repr(ex))


@hook(native.FUNC_PATH, Type.PRE)
def on_caused_damage(obj: UObject, args: WrappedStruct, _ret: Any, _func: BoundFunction) -> Any:
    # Our binding calls this on the default object, anything else is the game's own use of it
    if obj._get_address() != binder.cdo_addr:
        return None
    if listening:
        record_hit(args)
    return Block


def check_binding(pc: UObject | None) -> None:
    """Keeps listening to the character you're playing, which is a new one after a respawn or a map change."""
    global bound_pawn, bound_address, is_guest  # noqa: PLW0603

    pawn = pc.Pawn if pc else None
    if not pawn or not set_up_listening():
        return
    try:
        role = pawn.Role
        is_guest = getattr(role, "value", role) != ROLE_AUTHORITY
    except AttributeError:
        is_guest = False
    address = pawn._get_address()
    if address != bound_address and binder.bind(pawn):
        bound_pawn = WeakPointer(pawn)
        bound_address = address
        info(f"{LOG_TAG} Listening to {pawn.Class.Name}, guest: {is_guest}")


def stop_listening() -> None:
    """Takes our entry back out of the character's list."""
    global bound_pawn, bound_address  # noqa: PLW0603

    pawn = bound_pawn()
    if pawn is not None:
        binder.unbind(pawn)
    bound_pawn = WeakPointer()
    bound_address = 0


# --- The window on screen -------------------------------------------------------------------------
WINDOW_NAME = "Bl4DpsMeter_Window"
WINDOW_Z_ORDER = 18
WIDGET_CHECK_INTERVAL = 1.0
DETAILS_FONT_RATIO = 0.65
GAME_FONT = "/Game/Fonts/Industry.Industry"
GAME_TYPEFACE = "Bold"
HIT_TEST_INVISIBLE = 3
COLLAPSED = 1
SHADOW_COLOR = (0.0, 0.0, 0.0, 0.9)
SHADOW_OFFSET = 1.5
ONE_LINE_SEPARATOR = " | "


def linear(srgb: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    """Turns a colour as written on the web into the linear one UMG wants."""

    def channel(start: int) -> float:
        value = int(srgb[start : start + 2], 16) / 255.0
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    return (channel(1), channel(3), channel(5), alpha)


@dataclass(frozen=True)
class WindowStyle:
    """How the window looks."""

    background: tuple[float, float, float, float] | None
    accent: tuple[float, float, float, float] | None
    main: tuple[float, float, float, float]
    details: tuple[float, float, float, float]
    capitals: bool = False
    one_line: bool = False
    shadow: bool = False


# The game's interface colours, as the Carnage Report takes them from its stylesheets
GAME_DARK = (0.0012, 0.0052, 0.0098, 0.88)
GAME_ORANGE = linear("#ff9b2e")
GAME_LIGHT_ORANGE = linear("#ffb55c")
GAME_TEXT = linear("#e4d9ce")
GAME_CYAN = linear("#00c6ff")
WHITE = linear("#ffffff")
WINDOW_STYLES = {
    STYLE_GAME: WindowStyle(GAME_DARK, GAME_ORANGE, GAME_LIGHT_ORANGE, GAME_TEXT, capitals=True),
    STYLE_COMPACT: WindowStyle(GAME_DARK, None, GAME_LIGHT_ORANGE, GAME_TEXT, capitals=True, one_line=True),
    STYLE_MINIMAL: WindowStyle(None, None, WHITE, GAME_TEXT, shadow=True),
    STYLE_NEON: WindowStyle((0.0, 0.0, 0.0, 0.7), GAME_CYAN, GAME_CYAN, WHITE),
}

TEXT_TOTAL: Text = ("Razem", "Total")
TEXT_TIME: Text = ("Czas", "Time")
TEXT_CRITS: Text = ("Krytyki", "Crits")
TEXT_BEST: Text = ("Najlepsze", "Best")
TEXT_KILLS: Text = ("Zabójstwa", "Kills")
TEXT_LAST_FIGHT: Text = ("Ostatnia walka", "Last fight")
TEXT_GUEST: Text = ("Jako gość co-op gra nie podaje obrażeń", "As a co-op guest, the game doesn't report damage")
TEXT_NOT_LISTENING: Text = ("Patch gry: licznik czeka na aktualizację", "Game patched: the meter is waiting for an update")

window_widget: WeakPointer = WeakPointer()
window_owner: WeakPointer = WeakPointer()
window_layout: tuple[Any, ...] = ()
main_label: UObject | None = None
details_label: UObject | None = None
main_shown: str = ""
details_shown: str = ""
last_widget_check: float = 0.0


def current_style() -> WindowStyle:
    """Gets the look that's been chosen."""
    return WINDOW_STYLES[window_style.key]


def main_text(now: float) -> str:
    """Gets the big line of the window."""
    return f"DPS {meter.format_number(damage.dps(now))}"


def details_text(now: float) -> str:
    """Gets the small lines of the window."""
    lines = []
    if listen_failed:
        lines.append(say(TEXT_NOT_LISTENING))
    elif is_guest:
        lines.append(say(TEXT_GUEST))
    if show_details.value:
        crit_share = 100.0 * damage.crit / damage.total if damage.total else 0.0
        lines.append(
            f"{say(TEXT_TOTAL)} {meter.format_number(damage.total)} | {say(TEXT_TIME)} {meter.format_time(damage.duration(now))}",
        )
        lines.append(
            f"{say(TEXT_CRITS)} {crit_share:.0f}% | {say(TEXT_BEST)} {meter.format_number(damage.biggest)}"
            f" | {say(TEXT_KILLS)} {damage.kills}",
        )
    last = damage.last_fight
    if show_last_fight.value and last is not None:
        lines.append(
            f"{say(TEXT_LAST_FIGHT)}: {meter.format_number(last.dps)} DPS"
            f" | {meter.format_number(last.total)} | {meter.format_time(last.duration)}",
        )
    style = current_style()
    text = (ONE_LINE_SEPARATOR if style.one_line else "\n").join(lines)
    return text.upper() if style.capitals else text


def new_widget(path: str, outer: UObject) -> UObject:
    """Creates a new UMG object."""
    return construct_object(find_object("Class", path), outer)


def linear_color(rgba: tuple[float, float, float, float]) -> WrappedStruct:
    """Creates a linear colour struct."""
    return make_struct("LinearColor", R=rgba[0], G=rgba[1], B=rgba[2], A=rgba[3])


def set_game_font(text: UObject, size: int) -> None:
    """Uses the game's own font, if it's loaded. The default one is fine otherwise."""
    try:
        font = find_object("Font", GAME_FONT)
        text.SetFont(make_struct("SlateFontInfo", FontObject=font, TypefaceFontName=GAME_TYPEFACE, Size=size))
    except Exception:  # noqa: BLE001
        font_info = text.Font
        font_info.Size = size
        text.SetFont(font_info)


def new_text(tree: UObject, size: int, color: tuple[float, float, float, float], shadow: bool) -> UObject:
    """Creates a text block which never takes the mouse."""
    text = new_widget("/Script/UMG.TextBlock", tree)
    set_game_font(text, size)
    text.SetColorAndOpacity(make_struct("SlateColor", SpecifiedColor=linear_color(color)))
    if shadow:
        text.SetShadowColorAndOpacity(linear_color(SHADOW_COLOR))
        text.SetShadowOffset(make_struct("Vector2D", X=SHADOW_OFFSET, Y=SHADOW_OFFSET))
    text.SetVisibility(HIT_TEST_INVISIBLE)
    return text


def wanted_layout() -> tuple[Any, ...]:
    """Gets what the window gets built from, it needs building again if any of this changes."""
    return (window_style.key, *(float(option.value) for option in RELOAD_OPTIONS))


def build_window(pc: UObject) -> None:
    """Adds the window to the screen. It never takes the mouse or any input."""
    global window_widget, window_owner, window_layout  # noqa: PLW0603
    global main_label, details_label, main_shown, details_shown  # noqa: PLW0603

    # A fresh name each time, reusing one from a removed widget which hasn't been collected yet
    # would make Unreal recycle that object in place. The viewport keeps the widget alive.
    name = f"{WINDOW_NAME}_{time.monotonic_ns() % 10**12}"
    widget = construct_object(find_object("Class", "/Script/UMG.UserWidget"), pc, name)
    tree = new_widget("/Script/UMG.WidgetTree", widget)
    widget.WidgetTree = tree
    canvas = new_widget("/Script/UMG.CanvasPanel", tree)
    tree.RootWidget = canvas

    style = current_style()
    box = new_widget("/Script/UMG.Border", tree)
    box.SetBrushColor(linear_color(style.background or (0.0, 0.0, 0.0, 0.0)))
    box.SetPadding(make_struct("Margin", Left=12.0, Top=6.0, Right=12.0, Bottom=7.0))
    box.SetVisibility(HIT_TEST_INVISIBLE)
    canvas.AddChild(box)

    # Anchored by its own matching point, so it stays on screen wherever it's put
    place = make_struct("Vector2D", X=window_x.value / 100.0, Y=window_y.value / 100.0)
    slot = box.Slot
    slot.SetAnchors(make_struct("Anchors", Minimum=place, Maximum=place))
    slot.SetAlignment(place)
    slot.SetPosition(make_struct("Vector2D", X=0.0, Y=0.0))
    slot.SetAutoSize(True)

    column = new_widget("/Script/UMG.VerticalBox", tree)
    box.SetContent(column)

    # A thin line along the top, like the game's own panels
    if style.accent is not None:
        accent = new_widget("/Script/UMG.Border", tree)
        accent.SetBrushColor(linear_color(style.accent))
        column.AddChild(accent)
        accent.Slot.SetPadding(make_struct("Margin", Bottom=5.0))
        spacer = new_widget("/Script/UMG.Spacer", tree)
        spacer.SetSize(make_struct("Vector2D", X=1.0, Y=2.0))
        accent.SetContent(spacer)

    main_label = new_text(tree, int(font_size.value), style.main, style.shadow)
    column.AddChild(main_label)
    details_size = max(8, int(font_size.value * DETAILS_FONT_RATIO))
    details_label = new_text(tree, details_size, style.details, style.shadow)
    column.AddChild(details_label)
    main_shown = details_shown = ""

    widget.SetVisibility(HIT_TEST_INVISIBLE)
    widget.AddToViewport(WINDOW_Z_ORDER)
    window_widget = WeakPointer(widget)
    window_owner = WeakPointer(pc)
    window_layout = wanted_layout()


def remove_window() -> None:
    """Takes the window off the screen, if it's there."""
    global window_widget, window_owner, main_label, details_label  # noqa: PLW0603

    widget = window_widget()
    window_widget = WeakPointer()
    window_owner = WeakPointer()
    main_label = details_label = None
    if widget is not None:
        widget.RemoveFromParent()


def update_window_text(now: float) -> None:
    """Changes what the window says, only touching the game if it's different."""
    global main_shown, details_shown  # noqa: PLW0603

    if main_label is None or details_label is None:
        return
    wanted_main = main_text(now)
    if wanted_main != main_shown:
        main_shown = wanted_main
        main_label.SetText(wanted_main)
    wanted_details = details_text(now)
    if wanted_details != details_shown:
        details_shown = wanted_details
        details_label.SetText(wanted_details)
        details_label.SetVisibility(HIT_TEST_INVISIBLE if wanted_details else COLLAPSED)


def check_window(pc: UObject | None) -> None:
    """Puts the window up, as the game clears what's on screen when changing maps. Not in the main menu."""
    if not show_window.value or pc is None or not pc.Pawn:
        remove_window()
        return
    widget = window_widget()
    if (
        widget is None
        or window_owner() is not pc
        or not widget.IsInViewport()
        or window_layout != wanted_layout()
    ):
        remove_window()
        build_window(pc)


def log_finished_fight() -> None:
    """Notes how a fight went in the log, once it's over."""
    global fight_logged  # noqa: PLW0603

    fight = damage.last_fight
    if fight is not fight_logged and fight is not None:
        fight_logged = fight
        info(f"{LOG_TAG} Fight over: {fight.dps:.0f} DPS, {fight.total:.0f} damage in {fight.duration:.1f} s")


def copy_settings_to_meter() -> None:
    """Gives the counting what's been chosen in the menus."""
    damage.mode = how_to_count.key
    damage.window = window_seconds.value
    damage.reset_after = reset_seconds.value if when_to_reset.key == RESET_AFTER_IDLE else None


# This runs every frame, Loot Magnet and BLImGui use the same hook as their game thread callback
@hook("/Script/Engine.CameraModifier:BlueprintModifyCamera", Type.POST_UNCONDITIONAL)
def on_tick(_obj: UObject, _args: WrappedStruct, _ret: Any, _func: BoundFunction) -> None:
    global last_update, last_bind_check, last_widget_check  # noqa: PLW0603

    now = time.monotonic()
    if now - last_update < UPDATE_INTERVAL:
        return
    last_update = now
    try:
        copy_settings_to_meter()
        damage.tick(now)
        log_finished_fight()
        if now - last_bind_check >= BIND_CHECK_INTERVAL:
            last_bind_check = now
            check_binding(get_pc())
        if now - last_widget_check >= WIDGET_CHECK_INTERVAL:
            last_widget_check = now
            check_window(get_pc())
        update_window_text(now)
    except Exception as ex:  # noqa: BLE001
        log_error_once(repr(ex))


@keybind("Reset Meter", key="F6")
def reset_meter() -> None:
    damage.reset()
    info(f"{LOG_TAG} Reset")


@keybind("Toggle Window")
def toggle_window() -> None:
    global last_widget_check  # noqa: PLW0603

    show_window.value = not show_window.value
    mod.save_settings()
    last_widget_check = 0.0


def on_disable() -> None:
    stop_listening()
    remove_window()


# --- Language -------------------------------------------------------------------------------------
def steam_language(game_folder: Path = MODS_DIR.parent) -> str | None:
    """Reads the language Steam runs the game in."""
    try:
        manifest = game_folder.parent.parent / f"appmanifest_{STEAM_APP_ID}.acf"
        found = re.search(r'"language"\s+"(\w+)"', manifest.read_text(encoding="utf8", errors="replace"))
    except OSError:
        return None
    return found.group(1) if found else None


def game_language() -> str:
    """Gets the language the game runs in. Polish is used for Polish, English for everything else."""
    return POLISH if steam_language() == "polish" else ENGLISH


def apply_language() -> None:
    """Works out which language to use, and puts every text in the menus into it."""
    global shown_language  # noqa: PLW0603

    chosen = language_option.key
    shown_language = chosen if chosen != LANGUAGE_AUTO else game_language()
    for option, name, description in labelled:
        show_label(option, name, description)
    for option in (language_option, how_to_count, when_to_reset, window_style):
        option.relabel()
    if "mod" in globals():
        mod.description = say(MOD_DESCRIPTION)


label(
    reset_meter,
    ("Resetuj licznik", "Reset the meter"),
    ("Kończy walkę od razu. Przydatne przy liczeniu tylko ręcznie.", "Ends the fight straight away. Handy when only resetting by hand."),
)
label(
    toggle_window,
    ("Pokaż lub ukryj okienko", "Show or hide the window"),
    ("Włącza i wyłącza okienko z DPS.", "Turns the DPS window on and off."),
)
language_option = label(
    localized_spinner("Language", LANGUAGE_AUTO, LANGUAGE_LABELS),
    ("Język / Language", "Język / Language"),
    (
        "Automatycznie używa języka gry ze Steama. Twój wybór zostaje zapisany.",
        "Follows the game's language on Steam by default. What you pick here is saved.",
    ),
)
language_option.after_change = apply_language

MOD_DESCRIPTION: Text = (
    "Licznik DPS: pokazuje na ekranie, ile obrażeń na sekundę zadajesz.",
    "DPS meter: shows on screen how much damage per second you're dealing.",
)


def submenu(identifier: str, children: list[BaseOption], name: Text, description: Text) -> NestedOption:
    """Creates a menu inside the menu."""
    return label(NestedOption(identifier, children=children), name, description)


mod = build_mod(
    on_disable=on_disable,
    options=[
        language_option,
        how_to_count,
        window_seconds,
        when_to_reset,
        reset_seconds,
        submenu(
            "What Counts",
            [only_health_removed, count_over_time, count_companions],
            ("Co się liczy", "What counts"),
            ("Które obrażenia wliczać do DPS.", "Which damage goes into the DPS."),
        ),
        submenu(
            "Window",
            [show_window, window_style, show_details, show_last_fight, window_x, window_y, font_size],
            ("Okienko", "Window"),
            ("Co okienko pokazuje i gdzie.", "What the window shows, and where."),
        ),
        label(
            ButtonOption("Reset Now", on_press=lambda _: reset_meter()),
            ("Resetuj teraz", "Reset now"),
            ("Kończy walkę od razu.", "Ends the fight straight away."),
        ),
    ],
)
apply_language()
