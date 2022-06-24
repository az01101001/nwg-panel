#!/usr/bin/env python3

import threading

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell

from nwg_panel.tools import check_key, get_brightness, set_brightness, get_contrast, set_contrast, get_color_preset, set_color_preset, list_color_presets, update_image


class BrightnessSlider(Gtk.EventBox):
    def __init__(self, settings, icons_path=""):
        Gtk.EventBox.__init__(self)

        defaults = {
            "show-values": True,
            "icon-size": 16,
            "interval": 10,
            "hover-opens": False,
            "leave-closes": False,
            "root-css-name": "brightness-module",
            "css-name": "brightness-popup",
            "angle": 0.0,
            "icon-placement": "start",
            "backlight-device": "",
            "backlight-controller": "light",
            "slider-inverted": False,
            "popup-icon-placement": "start",
            "popup-horizontal-alignment": "left",
            "popup-vertical-alignment": "top",
            "popup-width": 256,
            "popup-height": 64,
            "popup-horizontal-margin": 0,
            "popup-vertical-margin": 0,
            "step-size": 1,
        }
        for key in defaults:
            check_key(settings, key, defaults[key])
        self.settings = settings

        self.set_property("name", self.settings["root-css-name"])

        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)

        self.icons_path = icons_path
        self.icon_size = settings["icon-size"]
        self.bri_icon_name = "view-refresh-symbolic"
        self.bri_image = Gtk.Image.new_from_icon_name(self.bri_icon_name, Gtk.IconSize.MENU)

        self.bri_label = Gtk.Label() if settings["show-values"] else None
        self.bri_value = 0

        self.popup_window = PopupWindow(self, settings, icons_path=self.icons_path)

        if settings["angle"] != 0.0:
            self.box.set_orientation(Gtk.Orientation.VERTICAL)
            self.bri_label.set_angle(settings["angle"])

        # events
        self.connect('button-press-event', self.on_button_press)
        self.connect('enter-notify-event', self.on_enter_notify_event)
        self.connect('leave-notify-event', self.on_leave_notify_event)
        if self.settings["step-size"] > 0:
            self.add_events(Gdk.EventMask.SCROLL_MASK) 
            self.connect('scroll-event', self.on_scroll)

        self.build_box()

        self.refresh()
        Gdk.threads_add_timeout_seconds(GLib.PRIORITY_LOW, settings["interval"], self.refresh)

    def build_box(self):
        if self.settings["icon-placement"] == "start":
            self.box.pack_start(self.bri_image, False, False, 2)
            
        if self.bri_label:
            self.box.pack_start(self.bri_label, False, False, 2)

        if self.settings["icon-placement"] == "end":
            self.box.pack_start(self.bri_image, False, False, 2)

    def refresh(self):
        thread = threading.Thread(target=self.refresh_output)
        thread.daemon = True
        thread.start()

        return True

    def refresh_output(self):
        try:
            GLib.idle_add(self.update_brightness)
        except Exception as e:
            print(e)

        return False

    def update_brightness(self, get=True):
        if get:
            self.bri_value = get_brightness(device=self.settings["backlight-device"],
                                            controller=self.settings["backlight-controller"])
        
        icon_name = bri_icon_name(self.bri_value)

        if icon_name != self.bri_icon_name:
            update_image(self.bri_image, icon_name, self.icon_size, self.icons_path)
            self.bri_icon_name = icon_name

        if self.bri_label:
            self.bri_label.set_text("{}%".format(self.bri_value))
        
        if get:
            self.popup_window.refresh()
    
    def on_button_press(self, w, event):
        if not self.popup_window.get_visible():
            self.popup_window.show_all()
        else:
            self.popup_window.hide()
        
        return False
    
    def on_scroll(self, w, event):
        if event.direction == Gdk.ScrollDirection.UP:
            self.bri_value += self.settings["step-size"]
        elif event.direction == Gdk.ScrollDirection.DOWN:
            self.bri_value -= self.settings["step-size"]
        
        self.bri_value = min(self.bri_value, 100)
        self.bri_value = max(self.bri_value, 0)

        self.update_brightness(get=False)

        if self.popup_window.get_visible():
            self.popup_window.bri_scale.set_value(self.bri_value)

        set_brightness(self.bri_value, device=self.settings["backlight-device"],
                       controller=self.settings["backlight-controller"])

        return False

    def on_enter_notify_event(self, widget, event):
        if self.settings["hover-opens"]:
            if not self.popup_window.get_visible():
                self.popup_window.show_all()
        else:
            widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
            widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)

        # cancel popup window close, as it's probably unwanted ATM
        self.popup_window.on_window_enter()

        return True

    def on_leave_notify_event(self, widget, event):
        widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
        widget.unset_state_flags(Gtk.StateFlags.SELECTED)
        return True


class PopupWindow(Gtk.Window):
    def __init__(self, parent, settings, monitor=None, icons_path=""):
        Gtk.Window.__init__(self, type_hint=Gdk.WindowTypeHint.NORMAL)
        GtkLayerShell.init_for_window(self)
        if monitor:
            GtkLayerShell.set_monitor(self, monitor)

        self.parent = parent
        self.settings = settings
        self.icon_size = settings["icon-size"]
        self.icons_path = icons_path
        self.src_tag = 0
        self.value_changed = False
        self.scrolled = False

        self.set_property("name", self.settings["css-name"])
        
        self.connect("show", self.on_window_show)
        if settings["leave-closes"]:
            self.connect("leave_notify_event", self.on_window_exit)
            self.connect("enter_notify_event", self.on_window_enter)

        eb = Gtk.EventBox()
        eb.set_above_child(False)

        self.box = Gtk.Box(spacing=0)
        self.box.set_orientation(Gtk.Orientation.VERTICAL)

        eb.add(self.box)
        self.add(eb)

        # brightness
        self.bri_box = Gtk.Box(spacing=0)
        self.bri_box.set_orientation(Gtk.Orientation.HORIZONTAL)

        self.bri_scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=1)
        self.bri_scale.set_tooltip_text("brightness")
        self.bri_scale.set_has_tooltip(False)
        self.bri_scale.set_inverted(self.settings["slider-inverted"])
        if self.settings["backlight-controller"] == "ddcutil":
            self.bri_scale_handler = self.bri_scale.connect("value-changed", self.on_value_changed)
            self.bri_scale.connect("button-release-event", self.on_button_release)
            
            self.bri_scale.add_events(Gdk.EventMask.SCROLL_MASK)
            self.bri_scale.connect('scroll-event', self.on_scroll)
        else:
            self.bri_scale_handler = self.bri_scale.connect("value-changed", self.set_bri)

        self.bri_icon_name = "view-refresh-symbolic"
        self.bri_image = Gtk.Image.new_from_icon_name(self.bri_icon_name, Gtk.IconSize.MENU)

        if self.settings["backlight-controller"] == "ddcutil":
            # contrast
            self.con_box = Gtk.Box(spacing=0)
            self.con_box.set_orientation(Gtk.Orientation.HORIZONTAL)

            self.con_scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=1)
            self.con_scale.set_tooltip_text("contrast")
            self.con_scale.set_has_tooltip(False)
            self.con_scale.set_inverted(self.settings["slider-inverted"])
            
            self.con_scale_handler = self.con_scale.connect("value-changed", self.on_value_changed)
            self.con_scale.connect("button-release-event", self.on_button_release)
            
            self.con_scale.add_events(Gdk.EventMask.SCROLL_MASK)
            self.con_scale.connect('scroll-event', self.on_scroll)

            self.con_icon_name = "view-refresh-symbolic"
            self.con_image = Gtk.Image.new_from_icon_name(self.bri_icon_name, Gtk.IconSize.MENU) # TODO contrast icons
            
            # pause ddcutil and color presets
            self.pause_button = Gtk.CheckButton.new_with_label(label="Pause ddcutil") # TODO

            self.color_presets_box = Gtk.ComboBoxText.new()
            self.color_presets_box.connect("changed", self.on_changed)

            self.color_presets = list_color_presets(device=self.settings["backlight-device"])
            for code, name in self.color_presets.items():
                self.color_presets_box.append(id=code, text=name)

        if settings["popup-vertical-alignment"] == "top":
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, settings["popup-vertical-margin"])
        elif settings["popup-vertical-alignment"] == "bottom":
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, settings["popup-vertical-margin"])

        if settings["popup-horizontal-alignment"] == "left":
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, settings["popup-horizontal-margin"])
        elif settings["popup-horizontal-alignment"] == "right":
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, settings["popup-horizontal-margin"])

        Gtk.Widget.set_size_request(self.box, settings["popup-width"], settings["popup-height"])

        self.build_box()

        self.refresh()
        Gdk.threads_add_timeout(GLib.PRIORITY_LOW, 500, self.refresh)
    
    def build_box(self):
        # brightness
        if self.settings["popup-icon-placement"] == "start":
            self.bri_box.pack_start(self.bri_image, False, False, 6)
        self.bri_box.pack_start(self.bri_scale, True, True, 5)
        if self.settings["popup-icon-placement"] == "end":
            self.bri_box.pack_start(self.bri_image, False, False, 6)
        self.box.pack_start(self.bri_box, True, True, 5)

        if self.settings["backlight-controller"] == "ddcutil":
            # contrast
            if self.settings["popup-icon-placement"] == "start":
                self.con_box.pack_start(self.con_image, False, False, 6)
            self.con_box.pack_start(self.con_scale, True, True, 5)
            if self.settings["popup-icon-placement"] == "end":
                self.con_box.pack_start(self.con_image, False, False, 6)
            self.box.pack_start(self.con_box, True, True, 5)

            # pause ddcutil and color presets
            self.box.pack_start(self.pause_button, True, True, 5)
            self.box.pack_start(self.color_presets_box, True, True, 5)

    def refresh(self, *args):
        if self.get_visible():
            if not self.value_changed:
                self.bri_scale.set_value(self.parent.bri_value)
            if self.parent.bri_icon_name != self.bri_icon_name:
                update_image(self.bri_image, self.parent.bri_icon_name, self.icon_size, self.icons_path)
                self.bri_icon_name = self.parent.bri_icon_name
            
            if self.settings["backlight-controller"] == "ddcutil":
                self.update_contrast()
                self.update_color_preset()
        else:
            with self.bri_scale.handler_block(self.bri_scale_handler):
                self.bri_scale.set_value(self.parent.bri_value)

        return True

    def on_window_exit(self, w, e):
        if self.get_visible():
            self.src_tag = GLib.timeout_add_seconds(1, self.hide_and_clear_tag)
        return True

    def hide_and_clear_tag(self):
        self.hide()
        self.src_tag = 0

    def on_window_enter(self, *args):
        if self.src_tag > 0:
            GLib.Source.remove(self.src_tag)
            self.src_tag = 0
        return True

    def on_window_show(self, *args):
        self.src_tag = 0
        self.refresh()

    def set_bri(self, slider):
        self.parent.bri_value = int(slider.get_value())
        self.parent.update_brightness(get=False)
        set_brightness(self.parent.bri_value, device=self.settings["backlight-device"],
                       controller=self.settings["backlight-controller"])

    def on_button_release(self, scale, event):
        if self.value_changed:
            if scale.get_tooltip_text() == "brightness":
                self.set_bri(self.bri_scale)
            elif scale.get_tooltip_text() == "contrast":
                set_contrast(int(self.con_scale.get_value()), device=self.settings["backlight-device"])
            self.value_changed = False

    def on_value_changed(self, scale):
        if self.scrolled:
            if scale.get_tooltip_text() == "brightness":
                self.set_bri(self.bri_scale)
            elif scale.get_tooltip_text() == "contrast":
                set_contrast(int(self.con_scale.get_value()), device=self.settings["backlight-device"])
            self.scrolled = False
        else:
            self.value_changed = True

    def on_scroll(self, w, event):
        self.scrolled = True

    def on_changed(self, w):
        code = w.get_active_id()
        if self.color_presets.get(code):
            set_color_preset(code, device=self.settings["backlight-device"])

    def update_color_preset(self):
        code = get_color_preset(device=self.settings["backlight-device"])
        self.color_presets_box.set_active_id(code)

    def update_contrast(self):
        contrast = get_contrast(device=self.settings["backlight-device"])
        self.con_scale.set_value(contrast)

        # TODO contrast icons, change func
        con_icon_name = bri_icon_name(int(self.con_scale.get_value()))
        update_image(self.con_image, con_icon_name, self.icon_size, self.icons_path)

def bri_icon_name(value):
    icon_name = "display-brightness-low-symbolic"
    if value > 70:
        icon_name = "display-brightness-high-symbolic"
    elif value > 30:
        icon_name = "display-brightness-medium-symbolic"

    return icon_name
