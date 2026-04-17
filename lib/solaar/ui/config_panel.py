## Copyright (C) 2012-2013  Daniel Pavel
## Copyright (C) 2014-2024  Solaar Contributors https://pwr-solaar.github.io/Solaar/
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License along
## with this program; if not, write to the Free Software Foundation, Inc.,
## 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import logging

from enum import Enum
from threading import Timer

import gi

from logitech_receiver import hidpp20
from logitech_receiver import settings

BUTTON_ALIAS_TO_VALUE = {
    "left": 1,
    "right": 2,
    "middle": 4,
    "back": 8,
    "forward": 16,
}

BUTTON_FUNCTION_ALIAS_TO_VALUE = {
    "tilt_left": 1,
    "tilt_right": 2,
    "dpi_next": 3,
    "dpi_previous": 4,
    "dpi": 5,
    "dpi_default": 6,
    "dpi_shift": 7,
    "profile_next": 8,
    "profile_previous": 9,
    "profile_cycle": 10,
    "g_shift": 11,
    "battery_status": 12,
    "profile_select": 13,
    "mode_switch": 14,
    "wheel_down": 16,
    "wheel_up": 17,
}

BUTTON_VALUE_TO_ALIAS = {v: k for k, v in BUTTON_ALIAS_TO_VALUE.items()}
BUTTON_FUNCTION_VALUE_TO_ALIAS = {v: k for k, v in BUTTON_FUNCTION_ALIAS_TO_VALUE.items()}

BUTTON_DROPDOWN_ITEMS = [
    ("left", "Left"),
    ("right", "Right"),
    ("middle", "Middle"),
    ("back", "Back"),
    ("forward", "Forward"),
    ("dpi", "DPI"),
    ("wheel_up", "Wheel Up"),
    ("wheel_down", "Wheel Down"),
    ("tilt_left", "Tilt Left"),
    ("tilt_right", "Tilt Right"),
    ("dpi_next", "DPI Next"),
    ("dpi_previous", "DPI Previous"),
    ("dpi_default", "DPI Default"),
    ("dpi_shift", "DPI Shift"),
    ("profile_next", "Profile Next"),
    ("profile_previous", "Profile Previous"),
    ("profile_cycle", "Profile Cycle"),
    ("g_shift", "G Shift"),
    ("battery_status", "Battery Status"),
    ("profile_select", "Profile Select"),
    ("mode_switch", "Mode Switch"),
]
BUTTON_FUNCTION_VALUE_TO_ALIAS = {v: k for k, v in BUTTON_FUNCTION_ALIAS_TO_VALUE.items()}

BUTTON_DROPDOWN_ITEMS = [
    ("left", "Left"),
    ("right", "Right"),
    ("middle", "Middle"),
    ("back", "Back"),
    ("forward", "Forward"),
    ("dpi", "DPI"),
    ("wheel_up", "Wheel Up"),
    ("wheel_down", "Wheel Down"),
    ("tilt_left", "Tilt Left"),
    ("tilt_right", "Tilt Right"),
    ("dpi_next", "DPI Next"),
    ("dpi_previous", "DPI Previous"),
    ("dpi_default", "DPI Default"),
    ("dpi_shift", "DPI Shift"),
    ("profile_next", "Profile Next"),
    ("profile_previous", "Profile Previous"),
    ("profile_cycle", "Profile Cycle"),
    ("g_shift", "G Shift"),
    ("battery_status", "Battery Status"),
    ("profile_select", "Profile Select"),
    ("mode_switch", "Mode Switch"),
]


def _pro2_get_profiles(device):
    try:
        return hidpp20.OnboardProfiles.from_device(device)
    except Exception as e:
        logger.warning("pro2 profiles read failed on %s: %r", device, e)
        return None


PRO2_HIDDEN_SETTING_KEYS = {
    "onboard_profiles",
    "report_rate",
    "sensitivity_dpi",
    "dpi",
    "led_control",
    "leds_logo",
    "led_logo",
}


def _is_pro2_device(device):
    return getattr(device, "wpid", None) == "40A8"


def _normalize_pro2_setting_key(value):
    if value is None:
        return ""
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace("(", "")
        .replace(")", "")
        .replace(":", "")
    )


def _pro2_should_hide_setting(setting):
    device = getattr(setting, "_device", None)
    if not _is_pro2_device(device):
        return False

    candidates = {
        _normalize_pro2_setting_key(getattr(setting, "name", None)),
        _normalize_pro2_setting_key(getattr(setting, "label", None)),
    }
    return any(candidate in PRO2_HIDDEN_SETTING_KEYS for candidate in candidates if candidate)


def _pro2_ensure_panel(device):
    global _box
    assert _box is not None

    panel_id = (device.receiver.path if device.receiver else device.path, device.number, "__pro2_buttons__")
    existing = _items.get(panel_id)
    if existing:
        return existing

    frame = Gtk.Frame(label="PRO 2 Onboard Editor")
    frame.set_hexpand(True)
    frame.set_label_align(0.02, 0.5)

    outer = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
    outer.set_margin_top(10)
    outer.set_margin_bottom(10)
    outer.set_margin_start(10)
    outer.set_margin_end(10)
    frame.add(outer)

    content = Gtk.Box.new(Gtk.Orientation.VERTICAL, 10)
    content.set_halign(Gtk.Align.START)
    content.set_hexpand(False)
    outer.pack_start(content, False, False, 0)

    def make_label(text, width=96):
        lbl = Gtk.Label(label=text)
        lbl.set_xalign(0.0)
        lbl.set_size_request(width, -1)
        return lbl

    def make_combo(width=138):
        combo = Gtk.ComboBoxText()
        combo.set_size_request(width, -1)
        return combo

    def make_spin(min_value, max_value, width=68):
        spin = Gtk.SpinButton.new_with_range(min_value, max_value, 1)
        spin.set_digits(0)
        spin.set_numeric(True)
        spin.set_size_request(width, -1)
        return spin

    def current_profile():
        profiles = _pro2_get_profiles(device)
        if not profiles:
            return None, None, None
        profile_no = int(profile_combo.get_active_id())
        profile = profiles.profiles.get(profile_no)
        return profiles, profile_no, profile

    def lighting_effect_label(effect_id):
        for value, label in PRO2_LIGHTING_EFFECT_ITEMS:
            if value == effect_id:
                return label
        return str(effect_id)

    def lighting_field_value(effect, name, default):
        value = getattr(effect, name, None)
        return default if value is None else int(value)

    def profile_fallback_color(profile):
        r = int(getattr(profile, "red", 255)) & 0xFF
        g = int(getattr(profile, "green", 255)) & 0xFF
        b = int(getattr(profile, "blue", 255)) & 0xFF
        return (r << 16) | (g << 8) | b

    def color_button_to_int(button):
        rgba = button.get_rgba()
        r = max(0, min(255, int(round(rgba.red * 255.0))))
        g = max(0, min(255, int(round(rgba.green * 255.0))))
        b = max(0, min(255, int(round(rgba.blue * 255.0))))
        return (r << 16) | (g << 8) | b

    def set_color_button(button, rgb):
        rgba = Gdk.RGBA()
        rgba.parse(f"#{int(rgb) & 0xFFFFFF:06X}")
        button.set_rgba(rgba)

    def build_lighting_effect():
        if not lighting_enabled.get_active():
            return _disabled_onboard_profile_lighting()

        effect_id = int(lighting_effect_combo.get_active_id() or "1")
        kwargs = {"ID": effect_id}

        if effect_id in {0x01, 0x02, 0x0A}:
            kwargs["color"] = color_button_to_int(lighting_color)

        if effect_id == 0x01:
            kwargs["ramp"] = int(lighting_ramp_combo.get_active_id() or "0")
        elif effect_id == 0x02:
            kwargs["speed"] = speed_spin.get_value_as_int()
        elif effect_id == 0x03:
            kwargs["period"] = period_spin.get_value_as_int()
            kwargs["intensity"] = intensity_spin.get_value_as_int()
        elif effect_id == 0x0A:
            kwargs["period"] = period_spin.get_value_as_int()
            kwargs["form"] = int(lighting_form_combo.get_active_id() or "0")
            kwargs["intensity"] = intensity_spin.get_value_as_int()

        return hidpp20.LEDEffectSetting(**kwargs)

    top_grid = Gtk.Grid(column_spacing=8, row_spacing=8)
    top_grid.set_halign(Gtk.Align.START)
    top_grid.set_hexpand(False)

    profile_combo = make_combo(58)
    for i in range(1, 6):
        profile_combo.append(str(i), str(i))
    profile_combo.set_active_id("1")

    dpi_combo = make_combo(78)

    report_rate_combo = make_combo(68)
    for value, label in PRO2_REPORT_RATE_ITEMS:
        report_rate_combo.append(str(value), label)

    top_grid.attach(make_label("Profile", 54), 0, 0, 1, 1)
    top_grid.attach(profile_combo, 1, 0, 1, 1)
    top_grid.attach(make_label("Rate", 42), 2, 0, 1, 1)
    top_grid.attach(report_rate_combo, 3, 0, 1, 1)
    top_grid.attach(make_label("DPI", 34), 4, 0, 1, 1)
    top_grid.attach(dpi_combo, 5, 0, 1, 1)

    content.pack_start(top_grid, False, False, 0)

    lighting_frame = Gtk.Frame(label="Lighting")
    lighting_frame.set_hexpand(False)

    lighting_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 8)
    lighting_box.set_margin_top(8)
    lighting_box.set_margin_bottom(8)
    lighting_box.set_margin_start(8)
    lighting_box.set_margin_end(8)
    lighting_frame.add(lighting_box)

    lighting_grid = Gtk.Grid(column_spacing=6, row_spacing=8)
    lighting_grid.set_halign(Gtk.Align.START)
    lighting_grid.set_hexpand(False)

    lighting_enabled = Gtk.CheckButton(label="Enable")

    lighting_effect_combo = make_combo(92)
    for value, label in PRO2_LIGHTING_EFFECT_ITEMS:
        lighting_effect_combo.append(str(value), label)

    lighting_color = Gtk.ColorButton()
    lighting_color.set_use_alpha(False)
    lighting_color.set_title("Profile Lighting Color")

    lighting_ramp_combo = make_combo(84)
    for value, label in PRO2_LIGHTING_RAMP_ITEMS:
        lighting_ramp_combo.append(str(value), label)

    lighting_form_combo = make_combo(90)
    for value, label in PRO2_LIGHTING_FORM_ITEMS:
        lighting_form_combo.append(str(value), label)

    speed_spin = make_spin(0, 255, 64)
    period_spin = make_spin(100, 5000, 76)
    intensity_spin = make_spin(0, 100, 64)

    lighting_fields = {}

    def add_lighting_field(name, row, col, label_text, widget, label_width=46):
        lbl = make_label(label_text, label_width)
        lighting_grid.attach(lbl, col, row, 1, 1)
        lighting_grid.attach(widget, col + 1, row, 1, 1)
        lighting_fields[name] = (lbl, widget)

    lighting_grid.attach(lighting_enabled, 0, 0, 1, 1)
    add_lighting_field("effect", 0, 1, "Effect", lighting_effect_combo, 44)
    add_lighting_field("color", 0, 3, "Color", lighting_color, 42)
    add_lighting_field("ramp", 0, 5, "Ramp", lighting_ramp_combo, 42)
    add_lighting_field("form", 0, 7, "Form", lighting_form_combo, 40)
    add_lighting_field("speed", 1, 1, "Speed", speed_spin, 44)
    add_lighting_field("period", 1, 3, "Period", period_spin, 44)
    add_lighting_field("intensity", 1, 5, "Intens.", intensity_spin, 48)

    lighting_box.pack_start(lighting_grid, False, False, 0)
    content.pack_start(lighting_frame, False, False, 0)

    buttons_frame = Gtk.Frame(label="Buttons")
    buttons_frame.set_hexpand(False)

    buttons_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 10)
    buttons_box.set_margin_top(10)
    buttons_box.set_margin_bottom(10)
    buttons_box.set_margin_start(10)
    buttons_box.set_margin_end(10)
    buttons_frame.add(buttons_box)

    button_grid = Gtk.Grid(column_spacing=16, row_spacing=8)
    button_grid.set_halign(Gtk.Align.START)
    button_grid.set_hexpand(False)

    button_combos = []
    for idx, label_text in enumerate(PRO2_BUTTON_LABELS):
        base_col = 0 if idx < 4 else 2
        row_idx = idx if idx < 4 else idx - 4

        lbl = make_label(label_text, 96)
        combo = make_combo(138)
        for alias, label in BUTTON_DROPDOWN_ITEMS:
            combo.append(alias, label)
        combo.set_active_id("left")

        button_grid.attach(lbl, base_col, row_idx, 1, 1)
        button_grid.attach(combo, base_col + 1, row_idx, 1, 1)
        button_combos.append(combo)

    buttons_box.pack_start(button_grid, False, False, 0)
    content.pack_start(buttons_frame, False, False, 0)

    actions = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 8)
    status_lbl = Gtk.Label(label="")
    status_lbl.set_xalign(0.0)
    status_lbl.set_hexpand(True)

    reload_btn = Gtk.Button(label="Reload")
    reload_btn.set_size_request(74, -1)
    apply_btn = Gtk.Button(label="Apply")
    apply_btn.set_size_request(74, -1)

    actions.pack_start(status_lbl, True, True, 0)
    actions.pack_start(reload_btn, False, False, 0)
    actions.pack_start(apply_btn, False, False, 0)
    buttons_box.pack_start(actions, False, False, 0)

    frame._device = device
    frame._profile_combo = profile_combo
    frame._button_combos = button_combos
    frame._dpi_combo = dpi_combo
    frame._report_rate_combo = report_rate_combo
    frame._lighting_enabled = lighting_enabled
    frame._lighting_effect_combo = lighting_effect_combo
    frame._lighting_color = lighting_color
    frame._lighting_ramp_combo = lighting_ramp_combo
    frame._lighting_form_combo = lighting_form_combo
    frame._lighting_speed_spin = speed_spin
    frame._lighting_period_spin = period_spin
    frame._lighting_intensity_spin = intensity_spin
    frame._status_lbl = status_lbl

    def sync_lighting_widgets(*_args):
        active = lighting_enabled.get_active()
        effect_id = int(lighting_effect_combo.get_active_id() or "0")
        visible_fields = PRO2_LIGHTING_VISIBLE_FIELDS.get(effect_id, {"effect"}) if active else set()

        for name, (lbl, widget) in lighting_fields.items():
            visible = active and name in visible_fields
            lbl.set_visible(visible)
            widget.set_visible(visible)
            widget.set_sensitive(visible)

        lighting_grid.show_all()
        for name, (lbl, widget) in lighting_fields.items():
            visible = active and name in visible_fields
            lbl.set_visible(visible)
            widget.set_visible(visible)

    def load_profile(*_args):
        profiles, profile_no, profile = current_profile()
        if not profiles:
            status_lbl.set_text("Read failed")
            return
        if not profile:
            status_lbl.set_text("Profile missing")
            return

        ui_to_slot = [0, 1, 2, 4, 3, 7, 6, 5]

        for idx, combo in enumerate(button_combos):
            try:
                slot_idx = ui_to_slot[idx]
                button = profile.buttons[slot_idx]
                behavior = getattr(button, "behavior", None)
                value = getattr(button, "value", None)
            except Exception:
                behavior = None
                value = None

            if behavior == 9:
                combo.set_active_id(BUTTON_FUNCTION_VALUE_TO_ALIAS.get(value, "left"))
            else:
                combo.set_active_id(BUTTON_VALUE_TO_ALIAS.get(value, "left"))

        dpi_combo.remove_all()
        try:
            resolutions = list(profile.resolutions)
        except Exception:
            resolutions = []

        for idx, dpi in enumerate(resolutions):
            dpi_combo.append(str(idx), str(dpi))

        try:
            active_idx = int(profile.resolution_default_index)
        except Exception:
            active_idx = 0

        try:
            current_rate = int(profile.report_rate)
        except Exception:
            current_rate = 1

        if report_rate_combo.get_active_id() is None:
            report_rate_combo.set_active_id("1")
        report_rate_combo.set_active_id(str(current_rate) if 1 <= current_rate <= 8 else "1")

        if resolutions:
            if active_idx < 0 or active_idx >= len(resolutions):
                active_idx = 0
            dpi_combo.set_active_id(str(active_idx))
        else:
            dpi_combo.set_active(-1)

        slot0 = _normalize_onboard_profile_lighting(getattr(profile, "lighting", None))[0]
        loaded_effect_id = int(getattr(slot0, "ID", 0) or 0)
        selected_effect_id = loaded_effect_id if loaded_effect_id in PRO2_LIGHTING_EFFECT_IDS else (1 if loaded_effect_id else 0)

        lighting_enabled.set_active(selected_effect_id != 0)
        lighting_effect_combo.set_active_id(str(selected_effect_id))

        set_color_button(
            lighting_color,
            lighting_field_value(slot0, "color", profile_fallback_color(profile)),
        )
        lighting_ramp_combo.set_active_id(str(lighting_field_value(slot0, "ramp", 0)))
        lighting_form_combo.set_active_id(str(lighting_field_value(slot0, "form", 0)))
        speed_spin.set_value(lighting_field_value(slot0, "speed", 128))
        period_spin.set_value(lighting_field_value(slot0, "period", 1000))
        intensity_spin.set_value(lighting_field_value(slot0, "intensity", 100))

        sync_lighting_widgets()
        status_lbl.set_text("Profile loaded")

    def apply_profile(*_args):
        profiles, profile_no, profile = current_profile()
        if not profiles:
            status_lbl.set_text("Read failed")
            return
        if not profile:
            status_lbl.set_text("Profile missing")
            return

        ui_to_slot = [0, 1, 2, 4, 3, 7, 6, 5]

        for idx, combo in enumerate(button_combos):
            alias = combo.get_active_id() or "left"
            slot_idx = ui_to_slot[idx]
            button = profile.buttons[slot_idx]

            if alias in BUTTON_FUNCTION_ALIAS_TO_VALUE:
                button.behavior = 9
                button.value = BUTTON_FUNCTION_ALIAS_TO_VALUE[alias]
                button.data = 0
                if hasattr(button, "type"):
                    try:
                        delattr(button, "type")
                    except Exception:
                        pass
            else:
                value = BUTTON_ALIAS_TO_VALUE[alias]
                button.behavior = 8
                button.type = 1
                button.value = value
                if hasattr(button, "data"):
                    try:
                        delattr(button, "data")
                    except Exception:
                        pass

            for attr in ["bytes", "sector", "address", "modifiers"]:
                if hasattr(button, attr):
                    try:
                        delattr(button, attr)
                    except Exception:
                        pass

        try:
            dpi_idx = dpi_combo.get_active_id()
            if dpi_idx is not None:
                dpi_idx = int(dpi_idx)
                if 0 <= dpi_idx < len(profile.resolutions):
                    profile.resolution_default_index = dpi_idx
        except Exception:
            pass

        try:
            rate_value = report_rate_combo.get_active_id()
            if rate_value is not None:
                profile.report_rate = int(rate_value)
        except Exception:
            pass

        slot0 = build_lighting_effect()
        profile.lighting = [
            slot0,
            _disabled_onboard_profile_lighting(),
            _disabled_onboard_profile_lighting(),
            _disabled_onboard_profile_lighting(),
        ]

        written = profiles.write(device)
        status_lbl.set_text(
            f"Saved profile {profile_no}: {lighting_effect_label(int(getattr(slot0, 'ID', 0) or 0))} ({written})"
        )

    profile_combo.connect(GtkSignal.CHANGED.value, load_profile)
    lighting_enabled.connect(GtkSignal.TOGGLED.value, sync_lighting_widgets)
    lighting_effect_combo.connect(GtkSignal.CHANGED.value, sync_lighting_widgets)
    reload_btn.connect(GtkSignal.CLICKED.value, load_profile)
    apply_btn.connect(GtkSignal.CLICKED.value, apply_profile)

    frame.show_all()
    _items[panel_id] = frame
    _box.pack_start(frame, False, False, 0)
    load_profile()
    return frame
from solaar.i18n import _
from solaar.i18n import ngettext

from .common import ui_async

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk  # NOQA: E402
from gi.repository import GLib  # NOQA: E402
from gi.repository import Gtk  # NOQA: E402

logger = logging.getLogger(__name__)

PRO2_BUTTON_LABELS = [
    "Left Click",
    "Right Click",
    "Middle Click",
    "Left Front",
    "Left Rear",
    "Right Front",
    "Right Rear",
    "Bottom DPI",
]

PRO2_REPORT_RATE_ITEMS = [
    (1, "1ms"),
    (2, "2ms"),
    (3, "3ms"),
    (4, "4ms"),
    (5, "5ms"),
    (6, "6ms"),
    (7, "7ms"),
    (8, "8ms"),
]

PRO2_LIGHTING_EFFECT_ITEMS = [
    (0x00, "Off"),
    (0x01, "Static"),
    (0x02, "Pulse"),
    (0x03, "Cycle"),
    (0x0A, "Breathe"),
]

PRO2_LIGHTING_EFFECT_IDS = {value for value, _label in PRO2_LIGHTING_EFFECT_ITEMS}

PRO2_LIGHTING_RAMP_ITEMS = [
    (0, "Default"),
    (1, "Yes"),
    (2, "No"),
]

PRO2_LIGHTING_FORM_ITEMS = [
    (0, "Default"),
    (1, "Sine"),
    (2, "Square"),
    (3, "Triangle"),
    (4, "Saw"),
    (5, "Shark"),
    (6, "Expo"),
]

PRO2_LIGHTING_VISIBLE_FIELDS = {
    0x00: set(),
    0x01: {"effect", "color", "ramp"},
    0x02: {"effect", "color", "speed"},
    0x03: {"effect", "period", "intensity"},
    0x0A: {"effect", "color", "period", "form", "intensity"},
}

PRO2_BINDING_ORDER = ["left", "right", "middle", "back", "forward", "dpi"]

PRO2_BINDINGS = {
    "left": {"label": "Left", "behavior": 8, "type": 1, "value": 1},
    "right": {"label": "Right", "behavior": 8, "type": 1, "value": 2},
    "middle": {"label": "Middle", "behavior": 8, "type": 1, "value": 4},
    "back": {"label": "Back", "behavior": 8, "type": 1, "value": 8},
    "forward": {"label": "Forward", "behavior": 8, "type": 1, "value": 16},
    "dpi": {"label": "DPI", "behavior": 9, "data": 0, "value": 5},
}

PRO2_SEND_VALUE_TO_ALIAS = {
    1: "left",
    2: "right",
    4: "middle",
    8: "back",
    16: "forward",
}


def _pro2_button_to_alias(button):
    behavior = getattr(button, "behavior", None)
    value = getattr(button, "value", None)
    mapping_type = getattr(button, "type", None)
    data = getattr(button, "data", None)

    if behavior == 9 and value == 5 and (data is None or data == 0):
        return "dpi"

    if behavior == 8 and mapping_type == 1:
        return PRO2_SEND_VALUE_TO_ALIAS.get(value, "left")

    return "left"


def _pro2_apply_alias(button, alias):
    spec = PRO2_BINDINGS[alias]

    button.behavior = spec["behavior"]
    button.value = spec["value"]

    if "type" in spec:
        button.type = spec["type"]
    elif hasattr(button, "type"):
        try:
            delattr(button, "type")
        except Exception:
            pass

    if "data" in spec:
        button.data = spec["data"]
    elif hasattr(button, "data"):
        try:
            delattr(button, "data")
        except Exception:
            pass

    for attr in ["bytes", "sector", "address", "modifiers"]:
        if hasattr(button, attr):
            try:
                delattr(button, attr)
            except Exception:
                pass



class GtkSignal(Enum):
    ACTIVATE = "activate"
    CHANGED = "changed"
    CLICKED = "clicked"
    MATCH_SELECTED = "match_selected"
    NOTIFY_ACTIVE = "notify::active"
    TOGGLED = "toggled"
    VALUE_CHANGED = "value-changed"
    COLOR_SET = "color-set"


def _read_async(setting, force_read, sbox, device_is_online, sensitive):
    def _do_read(s, force, sb, online, sensitive):
        try:
            v = s.read(not force)
        except Exception as e:
            v = None
            logger.warning("%s: error reading so use None (%s): %s", s.name, s._device, repr(e))
        GLib.idle_add(_update_setting_item, sb, v, online, sensitive, True, priority=99)

    ui_async(_do_read, setting, force_read, sbox, device_is_online, sensitive)


def _write_async(setting, value, sbox, sensitive=True, key=None):
    def _do_write(_s, v, sb, key):
        try:
            if key is None:
                v = setting.write(v)
            else:
                v = setting.write_key_value(key, v)
                v = {key: v}
        except Exception:
            v = None
        if sb:
            GLib.idle_add(_update_setting_item, sb, v, True, sensitive, priority=99)

    if sbox:
        sbox._control.set_sensitive(False)
        sbox._failed.set_visible(False)
        sbox._spinner.set_visible(True)
        sbox._spinner.start()
    ui_async(_do_write, setting, value, sbox, key)


class ComboBoxText(Gtk.ComboBoxText):
    def get_value(self):
        return int(self.get_active_id())

    def set_value(self, value):
        return self.set_active_id(str(int(value)))


class Scale(Gtk.Scale):
    def get_value(self):
        return int(super().get_value())


class Control:
    def __init__(self, **kwargs):
        self.sbox = None
        self.delegate = None

    def init(self, sbox, delegate):
        self.sbox = sbox
        self.delegate = delegate if delegate else self

    def changed(self, *args):
        if self.get_sensitive():
            self.delegate.update()

    def update(self):
        _write_async(self.sbox.setting, self.get_value(), self.sbox)

    def layout(self, sbox, label, change, spinner, failed):
        sbox.pack_start(label, False, False, 0)
        sbox.pack_end(change, False, False, 0)
        fill = sbox.setting.kind == settings.Kind.RANGE or sbox.setting.kind == settings.Kind.HETERO
        sbox.pack_end(self, fill, fill, 0)
        sbox.pack_end(spinner, False, False, 0)
        sbox.pack_end(failed, False, False, 0)
        return self


class ToggleControl(Gtk.Switch, Control):
    def __init__(self, sbox, delegate=None):
        super().__init__(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.init(sbox, delegate)
        self.connect(GtkSignal.NOTIFY_ACTIVE.value, self.changed)

    def set_value(self, value):
        if value is not None:
            self.set_state(value)

    def get_value(self):
        return self.get_state()


class SliderControl(Gtk.Scale, Control):
    def __init__(self, sbox, delegate=None):
        super().__init__(halign=Gtk.Align.FILL)
        self.init(sbox, delegate)
        self.timer = None
        self.set_range(*self.sbox.setting.range)
        self.set_round_digits(0)
        self.set_digits(0)
        self.set_increments(1, 5)
        self.connect(GtkSignal.VALUE_CHANGED.value, self.changed)

    def set_value(self, value):
        if isinstance(value, dict):
            value = next(iter(value.values()))
        return super().set_value(value)

    def get_value(self):
        return int(super().get_value())

    def changed(self, *args):
        if self.get_sensitive():
            if self.timer:
                self.timer.cancel()
            self.timer = Timer(0.5, lambda: GLib.idle_add(self.do_change))
            self.timer.start()

    def do_change(self):
        self.timer.cancel()
        self.update()


def _create_choice_control(sbox, delegate=None, choices=None):
    if 50 > len(choices if choices else sbox.setting.choices):
        return ChoiceControlLittle(sbox, choices=choices, delegate=delegate)
    else:
        return ChoiceControlBig(sbox, choices=choices, delegate=delegate)

class ChoiceControlLittle(Gtk.ComboBoxText, Control):
    def __init__(self, sbox, delegate=None, choices=None):
        super().__init__(halign=Gtk.Align.FILL)
        self.init(sbox, delegate)
        self.choices = choices if choices is not None else sbox.setting.choices
        for entry in self.choices:
            self.append(str(int(entry)), str(entry))
        self.connect(GtkSignal.CHANGED.value, self.changed)

    def get_value(self):
        return int(self.get_active_id()) if self.get_active_id() is not None else None

    def set_value(self, value):
        if value is not None:
            self.set_active_id(str(int(value)))

    def get_choice(self):
        id = self.get_value()
        return next((x for x in self.choices if x == id), None)

    def set_choices(self, choices):
        self.remove_all()
        for choice in choices:
            self.append(str(int(choice)), _(str(choice)))


class ChoiceControlBig(Gtk.Entry, Control):
    def __init__(self, sbox, delegate=None, choices=None):
        super().__init__(halign=Gtk.Align.FILL)
        self.init(sbox, delegate)
        self.choices = choices if choices is not None else sbox.setting.choices
        self.value = None
        self.set_width_chars(max([len(str(x)) for x in self.choices]) + 5)
        liststore = Gtk.ListStore(int, str)
        for v in self.choices:
            liststore.append((int(v), str(v)))
        completion = Gtk.EntryCompletion()
        completion.set_model(liststore)

        def norm(s):
            return s.replace("_", "").replace(" ", "").lower()

        completion.set_match_func(lambda completion, key, it: norm(key) in norm(completion.get_model()[it][1]))
        completion.set_text_column(1)
        self.set_completion(completion)
        self.connect(GtkSignal.CHANGED.value, self.changed)
        self.connect(GtkSignal.ACTIVATE.value, self.activate)
        completion.connect(GtkSignal.MATCH_SELECTED.value, self.select)

    def get_value(self):
        choice = self.get_choice()
        return int(choice) if choice is not None else None

    def set_value(self, value):
        if value is not None:
            self.set_text(str(next((x for x in self.choices if x == value), None)))

    def get_choice(self):
        key = self.get_text()
        return next((x for x in self.choices if x == key), None)

    def set_choices(self, choices):
        self.choices = choices

    def changed(self, *args):
        self.value = self.get_choice()
        icon = "dialog-warning" if self.value is None else "dialog-question" if self.get_sensitive() else ""
        self.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, icon)
        tooltip = _("Incomplete") if self.value is None else _("Complete - ENTER to change")
        self.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, tooltip)

    def activate(self, *_args):
        if self.value is not None and self.get_sensitive():
            self.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "")
            self.delegate.update()

    def select(self, _completion, model, iter):
        self.set_value(model.get(iter, 0)[0])
        if self.value and self.get_sensitive():
            self.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "")
            self.delegate.update()


class MapChoiceControl(Gtk.HBox, Control):
    def __init__(self, sbox, delegate=None):
        super().__init__(homogeneous=False, spacing=6)
        self.init(sbox, delegate)
        self.keyBox = Gtk.ComboBoxText()
        for entry in sbox.setting.choices:
            self.keyBox.append(str(int(entry)), _(str(entry)))
        self.keyBox.set_active(0)
        key_choice = int(self.keyBox.get_active_id())
        self.value_choices = self.sbox.setting.choices[key_choice]
        self.valueBox = _create_choice_control(sbox.setting, choices=self.value_choices, delegate=self)
        self.pack_start(self.keyBox, False, False, 0)
        self.pack_end(self.valueBox, False, False, 0)
        self.keyBox.connect(GtkSignal.CHANGED.value, self.map_value_notify_key)

    def get_value(self):
        key_choice = int(self.keyBox.get_active_id())
        if key_choice is not None and self.valueBox.get_value() is not None:
            return self.valueBox.get_value()

    def set_value(self, value):
        if value is None:
            return
        self.valueBox.set_sensitive(self.get_sensitive())
        key = int(self.keyBox.get_active_id())
        if value.get(key) is not None:
            self.valueBox.set_value(value.get(key))
        self.valueBox.set_sensitive(True)

    def map_populate_value_box(self, key_choice):
        choices = self.sbox.setting.choices[key_choice]
        if choices != self.value_choices:
            self.value_choices = choices
            self.valueBox.set_choices(choices)
        current = self.sbox.setting._value.get(key_choice) if self.sbox.setting._value else None
        if current is not None:
            self.valueBox.set_value(current)

    def map_value_notify_key(self, *_args):
        key_choice = int(self.keyBox.get_active_id())
        if self.keyBox.get_sensitive():
            self.map_populate_value_box(key_choice)

    def update(self):
        key_choice = int(self.keyBox.get_active_id())
        value = self.get_value()
        if value is not None and self.valueBox.get_sensitive() and self.sbox.setting._value.get(key_choice) != value:
            self.sbox.setting._value[int(key_choice)] = value
            _write_async(self.sbox.setting, value, self.sbox, key=int(key_choice))


class MultipleControl(Gtk.ListBox, Control):
    def __init__(self, sbox, change, button_label="...", delegate=None):
        super().__init__()
        self.init(sbox, delegate)
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_no_show_all(True)
        self._showing = True
        self.setup(sbox.setting)  # set up the data and boxes for the sub-controls
        btn = Gtk.Button(label=button_label)
        btn.connect(GtkSignal.CLICKED.value, self.toggle_display)
        self._button = btn
        hbox = Gtk.HBox(homogeneous=False, spacing=6)
        hbox.pack_end(change, False, False, 0)
        hbox.pack_end(btn, False, False, 0)
        self._header = hbox
        vbox = Gtk.VBox(homogeneous=False, spacing=6)
        vbox.pack_start(hbox, True, True, 0)
        vbox.pack_end(self, True, True, 0)
        self.vbox = vbox
        self.toggle_display()
        _disable_listbox_highlight_bg(self)

    def layout(self, sbox, label, change, spinner, failed):
        self._header.pack_start(label, False, False, 0)
        self._header.pack_end(spinner, False, False, 0)
        self._header.pack_end(failed, False, False, 0)
        sbox.pack_start(self.vbox, True, True, 0)
        sbox._button = self._button
        return True

    def toggle_display(self, *_args):
        self._showing = not self._showing
        if not self._showing:
            for c in self.get_children():
                c.hide()
            self.hide()
        else:
            self.show()
            for c in self.get_children():
                c.show_all()


class MultipleToggleControl(MultipleControl):
    def setup(self, setting):
        self._label_control_pairs = []
        for k in setting._validator.get_options():
            h = Gtk.HBox(homogeneous=False, spacing=0)
            lbl_text = str(k)
            lbl_tooltip = None
            if hasattr(setting, "_labels"):
                l1, l2 = setting._labels.get(k, (None, None))
                lbl_text = l1 if l1 else lbl_text
                lbl_tooltip = l2 if l2 else lbl_tooltip
            lbl = Gtk.Label(label=lbl_text)
            h.set_tooltip_text(lbl_tooltip or " ")
            control = Gtk.Switch()
            control._setting_key = int(k)
            control.connect(GtkSignal.NOTIFY_ACTIVE.value, self.toggle_notify)
            h.pack_start(lbl, False, False, 0)
            h.pack_end(control, False, False, 0)
            lbl.set_margin_start(30)
            self.add(h)
            self._label_control_pairs.append((lbl, control))

    def toggle_notify(self, switch, _active):
        if switch.get_sensitive():
            key = switch._setting_key
            new_state = switch.get_state()
            if self.sbox.setting._value[key] != new_state:
                self.sbox.setting._value[key] = new_state
                _write_async(self.sbox.setting, new_state, self.sbox, key=int(key))

    def set_value(self, value):
        if value is None:
            return
        active = 0
        total = len(self._label_control_pairs)
        to_join = []
        for lbl, elem in self._label_control_pairs:
            v = value.get(elem._setting_key, None)
            if v is not None:
                elem.set_state(v)
            if elem.get_state():
                active += 1
            to_join.append(f"{lbl.get_text()}: {str(elem.get_state())}")
        b = ", ".join(to_join)
        self._button.set_label(f"{active} / {total}")
        self._button.set_tooltip_text(b)


class MultipleRangeControl(MultipleControl):
    def setup(self, setting):
        self._items = []
        for item in setting._validator.items:
            lbl_text = str(item)
            lbl_tooltip = None
            if hasattr(setting, "_labels"):
                l1, l2 = setting._labels.get(int(item), (None, None))
                lbl_text = l1 if l1 else lbl_text
                lbl_tooltip = l2 if l2 else lbl_tooltip
            item_lbl = Gtk.Label(label=lbl_text)
            self.add(item_lbl)
            self.set_tooltip_text(lbl_tooltip or " ")
            item_lb = Gtk.ListBox()
            item_lb.set_selection_mode(Gtk.SelectionMode.NONE)
            item_lb._sub_items = []
            for sub_item in setting._validator.sub_items[item]:
                h = Gtk.HBox(homogeneous=False, spacing=20)
                lbl_text = str(sub_item)
                lbl_tooltip = None
                if hasattr(setting, "_labels_sub"):
                    l1, l2 = setting._labels_sub.get(str(sub_item), (None, None))
                    lbl_text = l1 if l1 else lbl_text
                    lbl_tooltip = l2 if l2 else lbl_tooltip
                sub_item_lbl = Gtk.Label(label=lbl_text)
                h.set_tooltip_text(lbl_tooltip or " ")
                h.pack_start(sub_item_lbl, False, False, 0)
                sub_item_lbl.set_margin_start(30)
                if sub_item.widget == "Scale":
                    control = Gtk.Scale.new_with_range(
                        Gtk.Orientation.HORIZONTAL,
                        sub_item.minimum,
                        sub_item.maximum,
                        1,
                    )
                    control.set_round_digits(0)
                    control.set_digits(0)
                    h.pack_end(control, True, True, 0)
                elif sub_item.widget == "SpinButton":
                    control = Gtk.SpinButton.new_with_range(sub_item.minimum, sub_item.maximum, 1)
                    control.set_digits(0)
                    h.pack_end(control, False, False, 0)
                else:
                    raise NotImplementedError
                control.connect(GtkSignal.VALUE_CHANGED.value, self.changed, item, sub_item)
                item_lb.add(h)
                h._setting_sub_item = sub_item
                h._label, h._control = sub_item_lbl, control
                item_lb._sub_items.append(h)
            item_lb._setting_item = item
            _disable_listbox_highlight_bg(item_lb)
            self.add(item_lb)
            self._items.append(item_lb)

    def changed(self, control, item, sub_item):
        if control.get_sensitive():
            if hasattr(control, "_timer"):
                control._timer.cancel()
            control._timer = Timer(0.5, lambda: GLib.idle_add(self._write, control, item, sub_item))
            control._timer.start()

    def _write(self, control, item, sub_item):
        control._timer.cancel()
        delattr(control, "_timer")
        new_state = int(control.get_value())
        if self.sbox.setting._value[int(item)][str(sub_item)] != new_state:
            self.sbox.setting._value[int(item)][str(sub_item)] = new_state
            _write_async(self.sbox.setting, self.sbox.setting._value[int(item)], self.sbox, key=int(item))

    def set_value(self, value):
        if value is None:
            return
        b = ""
        n = 0
        for ch in self._items:
            item = ch._setting_item
            v = value.get(int(item), None)
            if v is not None:
                b += f"{str(item)}: ("
                to_join = []
                for c in ch._sub_items:
                    sub_item = c._setting_sub_item
                    try:
                        sub_item_value = v[str(sub_item)]
                    except KeyError:
                        sub_item_value = c._control.get_value()
                    c._control.set_value(sub_item_value)
                    n += 1
                    to_join.append(f"{str(sub_item)}={sub_item_value}")
                b += ", ".join(to_join) + ") "
        lbl_text = ngettext("%d value", "%d values", n) % n
        self._button.set_label(lbl_text)
        self._button.set_tooltip_text(b)


class PackedRangeControl(MultipleRangeControl):
    def setup(self, setting):
        self._items = []
        validator = setting._validator
        for item in range(validator.count):
            h = Gtk.HBox(homogeneous=False, spacing=0)
            lbl = Gtk.Label(label=str(validator.keys[item]))
            control = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, validator.min_value, validator.max_value, 1)
            control.set_round_digits(0)
            control.set_digits(0)
            control.connect(GtkSignal.VALUE_CHANGED.value, self.changed, validator.keys[item])
            h.pack_start(lbl, False, False, 0)
            h.pack_end(control, True, True, 0)
            h._setting_item = validator.keys[item]
            h.control = control
            lbl.set_margin_start(30)
            self.add(h)
            self._items.append(h)

    def changed(self, control, item):
        if control.get_sensitive():
            if hasattr(control, "_timer"):
                control._timer.cancel()
            control._timer = Timer(0.5, lambda: GLib.idle_add(self._write, control, item))
            control._timer.start()

    def _write(self, control, item):
        control._timer.cancel()
        delattr(control, "_timer")
        new_state = int(control.get_value())
        if self.sbox.setting._value[int(item)] != new_state:
            self.sbox.setting._value[int(item)] = new_state
            _write_async(self.sbox.setting, self.sbox.setting._value[int(item)], self.sbox, key=int(item))

    def set_value(self, value):
        if value is None:
            return
        b = ""
        n = len(self._items)
        for h in self._items:
            item = h._setting_item
            v = value.get(int(item), None)
            if v is not None:
                h.control.set_value(v)
            else:
                v = self.sbox.setting._value[int(item)]
            b += f"{str(item)}: ({str(v)}) "
        lbl_text = ngettext("%d value", "%d values", n) % n
        self._button.set_label(lbl_text)
        self._button.set_tooltip_text(b)


class GraphicEQControl(MultipleControl):
    def setup(self, setting):
        self._items = []
        validator = setting._validator
        row = Gtk.ListBoxRow()
        hbox = Gtk.HBox(homogeneous=True, spacing=8)
        for item in range(validator.count):
            vbox = Gtk.VBox(homogeneous=False, spacing=2)
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.VERTICAL, validator.min_value, validator.max_value, 1)
            scale.set_inverted(True)
            scale.set_round_digits(0)
            scale.set_digits(0)
            scale.set_draw_value(True)
            scale.connect("format-value", lambda s, v: f"{int(v)} dB")
            scale.set_has_origin(True)
            scale.set_size_request(-1, 150)
            scale.add_mark(0, Gtk.PositionType.LEFT, "0")
            scale.connect(GtkSignal.VALUE_CHANGED.value, self._changed, validator.keys[item])
            lbl = Gtk.Label(label=str(validator.keys[item]))
            lbl.set_line_wrap(True)
            lbl.set_justify(Gtk.Justification.CENTER)
            vbox.pack_start(scale, True, True, 0)
            vbox.pack_end(lbl, False, False, 0)
            vbox._setting_item = validator.keys[item]
            vbox.control = scale
            hbox.pack_start(vbox, True, True, 0)
            self._items.append(vbox)
        row.add(hbox)
        self.add(row)

    def _changed(self, control, item):
        if control.get_sensitive():
            if hasattr(control, "_timer"):
                control._timer.cancel()
            control._timer = Timer(0.5, lambda: GLib.idle_add(self._write, control, item))
            control._timer.start()

    def _write(self, control, item):
        control._timer.cancel()
        delattr(control, "_timer")
        new_state = int(control.get_value())
        if self.sbox.setting._value[int(item)] != new_state:
            self.sbox.setting._value[int(item)] = new_state
            _write_async(self.sbox.setting, self.sbox.setting._value[int(item)], self.sbox, key=int(item))

    def set_value(self, value):
        if value is None:
            return
        b = ""
        n = len(self._items)
        for vbox in self._items:
            item = vbox._setting_item
            v = value.get(int(item), None)
            if v is not None:
                vbox.control.set_value(v)
            else:
                v = self.sbox.setting._value[int(item)]
            b += f"{str(item)}: ({str(v)}) "
        lbl_text = ngettext("%d value", "%d values", n) % n
        self._button.set_label(lbl_text)
        self._button.set_tooltip_text(b)


# control with an ID key that determines what else to show
class HeteroKeyControl(Gtk.HBox, Control):
    def __init__(self, sbox, delegate=None):
        super().__init__(homogeneous=False, spacing=6)
        self.init(sbox, delegate)
        self._items = {}
        for item in sbox.setting.possible_fields:
            if item["label"]:
                item_lblbox = Gtk.Label(label=item["label"])
                self.pack_start(item_lblbox, False, False, 0)
                item_lblbox.set_visible(False)
            else:
                item_lblbox = None

            item_box = ComboBoxText()
            if item["kind"] == settings.Kind.CHOICE:
                for entry in item["choices"]:
                    item_box.append(str(int(entry)), str(entry))
                item_box.set_active(0)
                item_box.connect(GtkSignal.CHANGED.value, self.changed)
                self.pack_start(item_box, False, False, 0)
            elif item["kind"] == settings.Kind.COLOR:
                item_box = Gtk.ColorButton()
                item_box.connect(GtkSignal.COLOR_SET.value, self.changed)
                self.pack_start(item_box, False, False, 0)
            elif item["kind"] == settings.Kind.RANGE:
                item_box = Scale()
                item_box.set_range(item["min"], item["max"])
                item_box.set_round_digits(0)
                item_box.set_digits(0)
                item_box.set_increments(1, 5)
                item_box.connect(GtkSignal.VALUE_CHANGED.value, self.changed)
                self.pack_start(item_box, True, True, 0)
            item_box.set_visible(False)
            self._items[str(item["name"])] = (item_lblbox, item_box)

    def get_value(self):
        result = {}
        for k, (_lblbox, box) in self._items.items():
            if isinstance(box, Gtk.ColorButton):
                rgba = box.get_rgba()
                r = int(rgba.red * 255)
                g = int(rgba.green * 255)
                b = int(rgba.blue * 255)
                result[str(k)] = (r << 16) | (g << 8) | b
            else:
                result[str(k)] = box.get_value()
        result = hidpp20.LEDEffectSetting(**result)
        return result

    def set_value(self, value):
        self.set_sensitive(False)
        if value is not None:
            for k, v in value.__dict__.items():
                if k in self._items:
                    (lblbox, box) = self._items[k]
                    if isinstance(box, Gtk.ColorButton):
                        rgba = Gdk.RGBA()
                        color_string = f"#{v:06X}"  # e.g. "#FF0000"
                        rgba.parse(color_string)
                        box.set_rgba(rgba)
                    else:
                        box.set_value(v)
        else:
            self.sbox._failed.set_visible(True)
        self.setup_visibles(value.ID if value is not None else 0)

    def setup_visibles(self, id_):
        fields = self.sbox.setting.fields_map[id_][1] if id_ in self.sbox.setting.fields_map else {}
        for name, (lblbox, box) in self._items.items():
            visible = name in fields or name == "ID"
            if lblbox:
                lblbox.set_visible(visible)
            box.set_visible(visible)

    def changed(self, control):
        if self.get_sensitive() and control.get_sensitive():
            if "ID" in self._items and control == self._items["ID"][1]:
                self.setup_visibles(int(self._items["ID"][1].get_value()))
            if hasattr(control, "_timer"):
                control._timer.cancel()
            control._timer = Timer(0.3, lambda: GLib.idle_add(self._write, control))
            control._timer.start()

    def _write(self, control):
        control._timer.cancel()
        delattr(control, "_timer")
        new_state = self.get_value()
        if self.sbox.setting._value != new_state:
            _write_async(self.sbox.setting, new_state, self.sbox)


def _disabled_onboard_profile_lighting():
    return hidpp20.LEDEffectSetting(ID=0, color=0, ramp=0)


def _clone_onboard_profile_led_effect(effect):
    if effect is None:
        return _disabled_onboard_profile_lighting()
    try:
        return hidpp20.LEDEffectSetting.from_bytes(effect.to_bytes())
    except Exception:
        return _disabled_onboard_profile_lighting()


def _normalize_onboard_profile_lighting(lighting):
    result = [_clone_onboard_profile_led_effect(effect) for effect in (lighting or [])]
    while len(result) < 4:
        result.append(_disabled_onboard_profile_lighting())
    return result[:4]


def onboard_profile_lighting_load(profile):
    lighting = _normalize_onboard_profile_lighting(getattr(profile, "lighting", None))
    slot0 = lighting[0]
    effect_id = getattr(slot0, "ID", None)
    enabled = effect_id is not None and int(effect_id) != 0
    color = getattr(slot0, "color", None)
    if color is None:
        r = int(getattr(profile, "red", 255)) & 0xFF
        g = int(getattr(profile, "green", 255)) & 0xFF
        b = int(getattr(profile, "blue", 255)) & 0xFF
        color = (r << 16) | (g << 8) | b
    return enabled, int(color) & 0xFFFFFF


def onboard_profile_lighting_apply(device, profiles, profile_index, enabled, color, done_cb=None):
    profile = profiles.profiles[profile_index]
    previous_lighting = _normalize_onboard_profile_lighting(getattr(profile, "lighting", None))
    color = int(color) & 0xFFFFFF

    if enabled:
        profile.lighting = [
            hidpp20.LEDEffectSetting(ID=0x01, color=color, ramp=0),
            _disabled_onboard_profile_lighting(),
            _disabled_onboard_profile_lighting(),
            _disabled_onboard_profile_lighting(),
        ]
    else:
        profile.lighting = [
            _disabled_onboard_profile_lighting(),
            _disabled_onboard_profile_lighting(),
            _disabled_onboard_profile_lighting(),
            _disabled_onboard_profile_lighting(),
        ]

    def _done(ok):
        if done_cb:
            done_cb(ok)
        return False

    def _worker():
        ok = True
        try:
            profiles.write(device)
        except Exception:
            ok = False
            logger.exception(
                "failed to write onboard profile lighting for profile %s on %s",
                profile_index,
                device,
            )
            profile.lighting = previous_lighting
        GLib.idle_add(_done, ok, priority=99)

    ui_async(_worker)


class OnboardProfileLightingControl(Gtk.HBox):
    def __init__(self, device, profiles, profile_index):
        super().__init__(homogeneous=False, spacing=6)
        self._device = device
        self._profiles = profiles
        self._profile_index = profile_index
        self._loading = False

        self._label = Gtk.Label(label=_("Lighting"))
        self._label.set_xalign(0.0)

        self._enabled = Gtk.CheckButton(label=_("Enable Lighting"))
        self._color = Gtk.ColorButton()
        self._color.set_use_alpha(False)
        self._color.set_title(_("Profile Lighting Color"))

        self.pack_start(self._label, True, True, 0)
        self.pack_start(self._enabled, False, False, 0)
        self.pack_start(self._color, False, False, 0)

        self._enabled.connect(GtkSignal.TOGGLED.value, self._changed)
        self._color.connect(GtkSignal.COLOR_SET.value, self._changed)

        self.load()

    def _set_color(self, rgb):
        rgba = Gdk.RGBA()
        rgba.parse(f"#{int(rgb) & 0xFFFFFF:06X}")
        self._color.set_rgba(rgba)

    def _get_color(self):
        rgba = self._color.get_rgba()
        r = max(0, min(255, int(round(rgba.red * 255.0))))
        g = max(0, min(255, int(round(rgba.green * 255.0))))
        b = max(0, min(255, int(round(rgba.blue * 255.0))))
        return (r << 16) | (g << 8) | b

    def load(self):
        enabled, color = onboard_profile_lighting_load(self._profiles.profiles[self._profile_index])
        self._loading = True
        self._enabled.set_active(enabled)
        self._set_color(color)
        self._color.set_sensitive(enabled)
        self._color.set_visible(enabled)
        self._loading = False

    def _changed(self, *_args):
        if self._loading:
            return
        enabled = self._enabled.get_active()
        self._color.set_sensitive(enabled)
        self._color.set_visible(enabled)
        self.set_sensitive(False)

        def _done(ok):
            self.set_sensitive(True)
            if not ok:
                self.load()

        onboard_profile_lighting_apply(
            self._device,
            self._profiles,
            self._profile_index,
            enabled,
            self._get_color(),
            done_cb=_done,
        )


def create_onboard_profile_lighting_row(device, profiles, profile_index):
    return OnboardProfileLightingControl(device, profiles, profile_index)


_allowables_icons = {True: "changes-allow", False: "changes-prevent", settings.SENSITIVITY_IGNORE: "dialog-error"}
_allowables_tooltips = {
    True: _("Changes allowed"),
    False: _("No changes allowed"),
    settings.SENSITIVITY_IGNORE: _("Ignore this setting"),
}
_next_allowable = {True: False, False: settings.SENSITIVITY_IGNORE, settings.SENSITIVITY_IGNORE: True}
_icons_allowables = {v: k for k, v in _allowables_icons.items()}


# clicking on the lock icon changes from changeable to unchangeable to ignore
def _change_click(button, sbox):
    icon = button.get_children()[0]
    icon_name, _ = icon.get_icon_name()
    allowed = _icons_allowables.get(icon_name, True)
    new_allowed = _next_allowable[allowed]
    sbox._control.set_sensitive(new_allowed is True)
    _change_icon(new_allowed, icon)
    if sbox.setting._device.persister:  # remember the new setting sensitivity
        sbox.setting._device.persister.set_sensitivity(sbox.setting.name, new_allowed)
    if allowed == settings.SENSITIVITY_IGNORE:  # update setting if it was being ignored
        setting = next((s for s in sbox.setting._device.settings if s.name == sbox.setting.name), None)
        if setting:
            persisted = sbox.setting._device.persister.get(setting.name) if sbox.setting._device.persister else None
            if setting.persist and persisted is not None:
                _write_async(setting, persisted, sbox)
            else:
                _read_async(setting, True, sbox, bool(sbox.setting._device.online), sbox._control.get_sensitive())
    return True


def _change_icon(allowed, icon):
    if allowed in _allowables_icons:
        icon._allowed = allowed
        icon.set_from_icon_name(_allowables_icons[allowed], Gtk.IconSize.LARGE_TOOLBAR)
        icon.set_tooltip_text(_allowables_tooltips[allowed])


def _create_sbox(s, _device):
    if not s.display:
        return
    if _pro2_should_hide_setting(s):
        return
    sbox = Gtk.HBox(homogeneous=False, spacing=6)
    sbox.setting = s
    sbox.kind = s.kind
    if s.description:
        sbox.set_tooltip_text(s.description)
    lbl = Gtk.Label(label=s.label)
    label = Gtk.EventBox()
    label.add(lbl)
    spinner = Gtk.Spinner()
    spinner.set_tooltip_text(_("Working") + "...")
    sbox._spinner = spinner
    failed = Gtk.Image.new_from_icon_name("dialog-warning", Gtk.IconSize.SMALL_TOOLBAR)
    failed.set_tooltip_text(_("Read/write operation failed."))
    sbox._failed = failed
    change_icon = Gtk.Image.new_from_icon_name("changes-prevent", Gtk.IconSize.LARGE_TOOLBAR)
    sbox._change_icon = change_icon
    _change_icon(False, change_icon)
    change = Gtk.Button()
    change.set_relief(Gtk.ReliefStyle.NONE)
    change.add(change_icon)
    change.set_sensitive(True)
    change.connect(GtkSignal.CLICKED.value, _change_click, sbox)

    if s.kind == settings.Kind.TOGGLE:
        control = ToggleControl(sbox)
    elif s.kind == settings.Kind.RANGE:
        control = SliderControl(sbox)
    elif s.kind == settings.Kind.CHOICE:
        control = _create_choice_control(sbox)
    elif s.kind == settings.Kind.MAP_CHOICE:
        control = MapChoiceControl(sbox)
    elif s.kind == settings.Kind.MULTIPLE_TOGGLE:
        control = MultipleToggleControl(sbox, change)
    elif s.kind == settings.Kind.MULTIPLE_RANGE:
        control = MultipleRangeControl(sbox, change)
    elif s.kind == settings.Kind.PACKED_RANGE:
        control = PackedRangeControl(sbox, change)
    elif s.kind == settings.Kind.GRAPHIC_EQ:
        control = GraphicEQControl(sbox, change)
    elif s.kind == settings.Kind.HETERO:
        control = HeteroKeyControl(sbox, change)
    else:
        logger.warning("setting %s display not implemented", s.label)
        return None

    control.set_sensitive(False)  # the first read will enable it
    control.layout(sbox, label, change, spinner, failed)
    sbox._control = control
    sbox.show_all()
    spinner.start()  # the first read will stop it
    failed.set_visible(False)
    return sbox


def _update_setting_item(sbox, value, is_online=True, sensitive=True, null_okay=False):
    sbox._spinner.stop()
    sensitive = sbox._change_icon._allowed if sensitive is None else sensitive
    if value is None and not null_okay:
        sbox._control.set_sensitive(sensitive is True)
        _change_icon(sensitive, sbox._change_icon)
        sbox._failed.set_visible(is_online)
        return
    sbox._failed.set_visible(False)
    sbox._control.set_sensitive(False)
    try:  # a call was producing a TypeError so guard against that
        sbox._control.set_value(value)
    except TypeError as e:
        logger.warning("%s: error setting control value (%s): %s", sbox.setting.name, sbox.setting._device, repr(e))
    sbox._control.set_sensitive(sensitive is True)
    _change_icon(sensitive, sbox._change_icon)


def _disable_listbox_highlight_bg(lb):
    colour = Gdk.RGBA()
    colour.parse("rgba(0,0,0,0)")
    for child in lb.get_children():
        child.override_background_color(Gtk.StateFlags.PRELIGHT, colour)


# config panel
_box = None
_items = {}


def create():
    global _box
    assert _box is None
    _box = Gtk.VBox(homogeneous=False, spacing=4)
    _box._last_device = None

    config_scroll = Gtk.ScrolledWindow()
    config_scroll.add(_box)
    config_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    config_scroll.set_shadow_type(Gtk.ShadowType.NONE)  # was IN
    config_scroll.set_size_request(0, 350)  # ask for enough vertical space for about eight settings

    return config_scroll


def update(device, is_online=None):
    assert _box is not None
    assert device
    device_id = (device.receiver.path if device.receiver else device.path, device.number)
    if is_online is None:
        is_online = bool(device.online)

    # if the device changed since last update, clear the box first
    if device_id != _box._last_device:
        _box.set_visible(False)
        _box._last_device = device_id

    # hide controls belonging to other devices
    for k, sbox in _items.items():
        sbox = _items[k]
        sbox.set_visible(k[0:2] == device_id)

    for s in device.settings:
        k = (device_id[0], device_id[1], s.name)
        if k in _items:
            sbox = _items[k]
        else:
            sbox = _create_sbox(s, device)
            if sbox is None:
                continue
            _items[k] = sbox
            _box.pack_start(sbox, False, False, 0)
        sensitive = device.persister.get_sensitivity(s.name) if device.persister else True
        _read_async(s, False, sbox, is_online, sensitive)

    if getattr(device, "wpid", None) == "40A8":
        panel = _pro2_ensure_panel(device)
        panel.set_visible(True)

    _box.set_visible(True)


def clean(device):
    """Remove the controls for a given device serial.
    Needed after the device has been unpaired.
    """
    assert _box is not None
    device_id = (device.receiver.path if device.receiver else device.path, device.number)
    for k in list(_items.keys()):
        if k[0:2] == device_id:
            _box.remove(_items[k])
            del _items[k]


def destroy():
    global _box
    _box = None
    _items.clear()


def change_setting(device, setting, values):
    """External interface to change a setting and have the GUI show the change"""
    assert device == setting._device
    GLib.idle_add(_change_setting, device, setting, values, priority=99)


def _change_setting(device, setting, values):
    device_path = device.receiver.path if device.receiver else device.path
    if (device_path, device.number, setting.name) in _items:
        sbox = _items[(device_path, device.number, setting.name)]
    else:
        sbox = None
    _write_async(setting, values[-1], sbox, None, key=values[0] if len(values) > 1 else None)


def record_setting(device, setting, values):
    """External interface to have the GUI show a change to a setting. Doesn't write to the device"""
    GLib.idle_add(_record_setting, device, setting, values, priority=99)


def _record_setting(device, setting_class, values):
    logger.debug("on %s changing setting %s to %s", device, setting_class.name, values)
    setting = next((s for s in device.settings if s.name == setting_class.name), None)
    if setting is None:
        logger.debug(
            "No setting for %s found on %s when trying to record a change made elsewhere",
            setting_class.name,
            device,
        )
    if setting:
        assert device == setting._device
        if len(values) > 1:
            setting.update_key_value(values[0], values[-1])
            value = {values[0]: values[-1]}
        else:
            setting.update(values[-1])
            value = values[-1]
        device_path = device.receiver.path if device.receiver else device.path
        if (device_path, device.number, setting.name) in _items:
            sbox = _items[(device_path, device.number, setting.name)]
            if sbox:
                _update_setting_item(sbox, value, sensitive=None)
