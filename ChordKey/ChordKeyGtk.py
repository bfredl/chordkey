# -*- coding: UTF-8 -*-

from __future__ import division, print_function, unicode_literals

### Logging ###
import logging
_logger = logging.getLogger("OnboardGtk")
###############

import sys
import time
import signal
import os.path

import dbus
import dbus.service
import dbus.mainloop.glib

from gi.repository import GLib, Gdk, Gtk

import virtkey

from ChordKey.KbdWindow       import KbdWindow, KbdPlugWindow
from ChordKey.Keyboard        import ChordKeyboard
from ChordKey.ChordKeyboardWidget  import ChordKeyboardWidget
from ChordKey.Indicator       import Indicator
#from ChordKey.LayoutLoaderSVG import LayoutLoaderSVG
from ChordKey.Appearance      import ColorScheme
from ChordKey.IconPalette     import IconPalette
from ChordKey.utils           import show_confirmation_dialog, CallOnce, Process, \
                                    unicode_str
import ChordKey.osk as osk

### Config Singleton ###
from ChordKey.Config import get_config
config = get_config()
########################

import ChordKey.KeyCommon

app = "chordkey"
app_upper = "ChordKey"
DEFAULT_FONTSIZE = 10


class ChordKeyGtk(object):
    """
    Main controller class for ChordKey
    """

    DBUS_NAME = "org.chordkey.ChordKey"

    keyboard = None

    def __init__(self):

        # Make sure windows get "chordkey", "ChordKey" as name and class
        GLib.set_prgname(str(app))
        Gdk.set_program_class(app_upper)

        # Use D-bus main loop by default
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

        # Check if there is already a Onboard instance running
        bus = dbus.SessionBus()
        has_remote_instance = bus.name_has_owner(self.DBUS_NAME)

        # Embedded instances can't become primary instances
        if has_remote_instance and \
           not config.options.allow_multiple_instances:
            # Present remote instance
            remote = bus.get_object(self.DBUS_NAME, ServiceOnboardKeyboard.PATH)
            remote.Show(dbus_interface=ServiceOnboardKeyboard.IFACE)
            _logger.info("Exiting: Not the primary instance.")
            sys.exit(0)

            # Register our dbus name
            self._bus_name = dbus.service.BusName(self.DBUS_NAME, bus)

        self.init()

        _logger.info("Entering mainloop of onboard")
        Gtk.main()


    def init(self):
        self.keyboard_state = None
        self.vk_timer = None
        self.reset_vk()
        self._connections = []
        self._window = None
        self.status_icon = None
        self.service_keyboard = None

        # finish config initialization
        config.init()

        # Release pressed keys when onboard is killed.
        # Don't keep enter key stuck when being killed from lightdm.
        self._osk_util = osk.Util()
        self._osk_util.set_unix_signal_handler(signal.SIGTERM, self.on_sigterm)
        self._osk_util.set_unix_signal_handler(signal.SIGINT, self.on_sigint)

        # Create the central keyboard model
        self.keyboard = ChordKeyboard()
        
        # Create the initial keyboard widget
        # Care for toolkit independence only once there is another
        # supported one besides GTK.
        self.keyboard_widget = ChordKeyboardWidget(self.keyboard)

        icp = IconPalette()
        icp.set_layout_view(self.keyboard_widget)
        icp.connect("activated", self._on_icon_palette_acticated)

        self._window = KbdWindow(self.keyboard_widget, icp)
        self.do_connect(self._window, "quit-onboard",
                        lambda x: self.do_quit_onboard())

        self._window.application = self
        config.main_window = self._window # need this to access screen properties

        self.load_vk()

        # Handle command line options x, y, size after window creation
        # because the rotation code needs the window's screen.
        if not config.xid_mode:
            rect = self._window.get_rect().copy()
            options = config.options
            if options.size:
                size = options.size.split("x")
                rect.w = int(size[0])
                rect.h = int(size[1])
            if not options.x is None:
                rect.x = options.x
            if not options.y is None:
                rect.y = options.y

            # Make sure the keyboard fits on screen
            rect = self._window.limit_size(rect)

            if rect != self._window.get_rect():
                orientation = self._window.get_screen_orientation()
                self._window.write_window_rect(orientation, rect)
                self._window.restore_window_rect() # move/resize early

        # export dbus service
        if not config.xid_mode:
            self.service_keyboard = ServiceOnboardKeyboard(self.keyboard_widget)

        # show/hide the window
        self.keyboard_widget.set_startup_visibility()

        # keep keyboard window and icon palette on top of dash
        if not config.xid_mode: # be defensive, not necessary when embedding
            self._osk_util.keep_windows_on_top([self._window,
                                                self._window.icp])

        # connect notifications for keyboard map and group changes
        self.keymap = Gdk.Keymap.get_default()
        self.do_connect(self.keymap, "keys-changed", self.cb_keys_changed) # map changes
        self.do_connect(self.keymap, "state-changed", self.cb_state_changed)
        Gdk.event_handler_set(cb_any_event, self)          # group changes

        # connect config notifications here to keep config from holding
        # references to keyboard objects.
        once = CallOnce(50).enqueue  # delay callbacks by 50ms
        reload_layout       = lambda x: once(self.reload_layout_and_present)
        update_ui           = lambda x: once(self._update_ui)
        update_transparency = lambda x: once(self.keyboard_widget.update_transparency)
        update_inactive_transparency = \
                              lambda x: once(self.keyboard_widget.update_inactive_transparency)

        if 0:
            # general
            config.auto_show.enabled_notify_add(lambda x: \
                                        self.keyboard_widget.update_auto_show())

            # window
            config.window.window_state_sticky_notify_add(lambda x: \
                                       self._window.update_sticky_state())
            config.window.window_decoration_notify_add(self._update_window_options)
            config.window.force_to_top_notify_add(self._update_window_options)
            config.window.keep_aspect_ratio_notify_add(update_ui)

            config.window.transparency_notify_add(update_transparency)
            config.window.background_transparency_notify_add(update_transparency)
            config.window.transparent_background_notify_add(update_ui)
            config.window.enable_inactive_transparency_notify_add(update_transparency)
            config.window.inactive_transparency_notify_add(update_inactive_transparency)
            config.window.docking_notify_add(self._update_docking)

            # layout
            config.layout_filename_notify_add(reload_layout)

            # theme
            #config.gdi.gtk_theme_notify_add(self.on_gtk_theme_changed)
            config.theme_notify_add(self.on_theme_changed)
            config.key_label_font_notify_add(reload_layout)
            config.key_label_overrides_notify_add(reload_layout)
            config.theme_settings.color_scheme_filename_notify_add(reload_layout)
            config.theme_settings.key_label_font_notify_add(reload_layout)
            config.theme_settings.key_label_overrides_notify_add(reload_layout)
            config.theme_settings.theme_attributes_notify_add(update_ui)

            # snippets
            config.snippets_notify_add(reload_layout)

            # universal access
            config.scanner.enabled_notify_add(self.keyboard._on_scanner_enabled)
            GLib.idle_add(self.keyboard.enable_scanner, config.scanner.enabled)

            config.window.resize_handles_notify_add(lambda x: \
                                        self.keyboard_widget.update_resize_handles())

            # advanced
            config.keyboard.key_synth_notify_add(reload_layout)


            # misc
            config.keyboard.show_click_buttons_notify_add(update_ui)
            config.lockdown.lockdown_notify_add(update_ui)
            config.clickmapper.state_notify_add(update_ui)
            if config.mousetweaks:
                config.mousetweaks.state_notify_add(update_ui)

        # create status icon
        self.status_icon = Indicator()
        self.status_icon.set_keyboard_window(self._window)
        self.do_connect(self.status_icon, "quit-onboard",
                        lambda x: self.do_quit_onboard())

        # Callbacks to use when icp or status icon is toggled
        if 0: #FIXME
            config.show_status_icon_notify_add(self.show_hide_status_icon)
            config.icp.in_use_notify_add(self.cb_icp_in_use_toggled)

        self.show_hide_status_icon(config.show_status_icon)


        # Minimize to IconPalette if running under GDM
        if 'RUNNING_UNDER_GDM' in os.environ:
            config.icp.in_use = True
            config.show_status_icon = False

        # unity-2d needs the skip-task-bar hint set before the first mapping.
        self.show_hide_taskbar()



    def on_sigterm(self):
        """
        Exit onboard on kill.
        """
        _logger.debug("SIGTERM received")
        self.do_quit_onboard()

    def on_sigint(self):
        """
        Exit onboard on Ctrl+C press.
        """
        _logger.debug("SIGINT received")
        self.do_quit_onboard()

    def do_connect(self, instance, signal, handler):
        handler_id = instance.connect(signal, handler)
        self._connections.append((instance, handler_id))

    # Method concerning the taskbar
    def show_hide_taskbar(self):
        """
        This method shows or hides the taskbard depending on whether there
        is an alternative way to unminimize the Onboard window.
        This method should be called every time such an alternative way
        is activated or deactivated.
        """
        if self._window:
            self._window.update_taskbar_hint()

    # Method concerning the icon palette
    def _on_icon_palette_acticated(self, widget):
        self.keyboard_widget.toggle_visible()

    def cb_icp_in_use_toggled(self, icp_in_use):
        """
        This is the callback that gets executed when the user toggles
        the gsettings key named in_use of the icon_palette. It also
        handles the showing/hiding of the taskar.
        """
        _logger.debug("Entered in on_icp_in_use_toggled")
        self.show_hide_icp()
        _logger.debug("Leaving on_icp_in_use_toggled")

    def show_hide_icp(self):
        if self._window.icp:
            show = config.is_icon_palette_in_use()
            if show:
                # Show icon palette if appropriate and handle visibility of taskbar.
                if not self._window.is_visible():
                    self._window.icp.show()
                self.show_hide_taskbar()
            else:
                # Show icon palette if appropriate and handle visibility of taskbar.
                if not self._window.is_visible():
                    self._window.icp.hide()
                self.show_hide_taskbar()

    # Methods concerning the status icon
    def show_hide_status_icon(self, show_status_icon):
        """
        Callback called when gsettings detects that the gsettings key specifying
        whether the status icon should be shown or not is changed. It also
        handles the showing/hiding of the taskar.
        """
        if show_status_icon:
            self.status_icon.set_visible(True)
        else:
            self.status_icon.set_visible(False)
        self.show_hide_icp()
        self.show_hide_taskbar()

    def cb_status_icon_clicked(self,widget):
        """
        Callback called when status icon clicked.
        Toggles whether Onboard window visibile or not.

        TODO would be nice if appeared to iconify to taskbar
        """
        self.keyboard_widget.toggle_visible()


    # keyboard layout changes
    def cb_keys_changed(self, keymap):
        self.load_vk()

    # modifier changes
    def cb_state_changed(self, keymap):
        _logger.debug("keyboard state changed to 0x{:x}" \
                      .format(keymap.get_modifier_state()))
        mod_mask = keymap.get_modifier_state()
        self.keyboard.set_modifiers(mod_mask)

    def cb_vk_timer(self):
        """
        Timer callback for polling until virtkey becomes valid.
        """
        if self.load_vk():
            GLib.source_remove(self.vk_timer)
            self.vk_timer = None
            return False
        return True

    def _update_ui(self):
        self.keyboard.update_ui()
        self.keyboard.redraw()

    def _update_window_options(self, value = None):
        window = self._window
        if window:
            window.update_window_options()
            if window.icp:
                window.icp.update_window_options()
            self._update_ui()

    def _update_docking(self, value = None):
        self._update_window_options()
        # give WM time to settle or move might fail
        GLib.idle_add(self._update_docking_delayed)

    def _update_docking_delayed(self):
        self._window.update_docking()
        self.keyboard_widget.update_resize_handles()
        self.keyboard.update_ui() # for the move button
        self.keyboard.redraw()

    def on_gtk_theme_changed(self, gtk_theme = None):
        """
        Switch onboard themes in sync with gtk-theme changes.
        """
        config.update_theme_from_system_theme()

    def on_gtk_font_dpi_changed(self):
        """
        Refresh the key's pango layout objects so that they can adapt
        to the new system dpi setting.
        """
        self.keyboard_widget.refresh_pango_layouts()
        self._update_ui()

        return False

    def on_theme_changed(self, theme):
        config.apply_theme()
        self.reload_layout()

    def reload_layout_and_present(self):
        """
        Reload the layout and briefly show the window
        with active transparency
        """
        self.reload_layout(force_update = True)
        self.keyboard_widget.update_transparency()

    def reload_layout(self, force_update=False):
        """
        Checks if the X keyboard layout has changed and
        (re)loads Onboards layout accordingly.
        """
        keyboard_state = (None, None)

        vk = self.get_vk()
        if vk:
            try:
                vk.reload() # reload keyboard names
                keyboard_state = (vk.get_layout_symbols(),
                                  vk.get_current_group_name())
            except virtkey.error:
                self.reset_vk()
                force_update = True
                _logger.warning("Keyboard layout changed, but retrieving "
                                "keyboard information failed")

        if self.keyboard_state != keyboard_state or force_update:
            self.keyboard_state = keyboard_state
            self.load_layout(config.layout_filename,
                             config.theme_settings.color_scheme_filename)

        # if there is no X keyboard, poll until it appears (if ever)

    def load_layout(self, layout_filename, color_scheme_filename):
        _logger.info("Loading keyboard layout from " + layout_filename)
        if (color_scheme_filename):
            _logger.info("Loading color scheme from " + color_scheme_filename)


        color_scheme = ColorScheme.load(color_scheme_filename) \
                       if color_scheme_filename else None
        #layout = LayoutLoaderSVG().load(vk, layout_filename, color_scheme)


        #self.keyboard.layout = layout
        self.keyboard.color_scheme = color_scheme
        self.keyboard.on_layout_loaded()

        if self._window and self._window.icp:
            self._window.icp.queue_draw()

    def load_vk(self):
        vk = self.get_vk()
        if vk:
            self.keyboard.cleanup()
            self.keyboard.init_key_synth(vk)
        else:
            if not self.vk_timer:
                self.vk_timer = GLib.timeout_add_seconds(1, self.cb_vk_timer)


    def get_vk(self):
        if not self._vk:
            try:
                # may fail if there is no X keyboard (LP: 526791)
                self._vk = virtkey.virtkey()

            except virtkey.error as e:
                t = time.time()
                if t > self._vk_error_time + .2: # rate limit to once per 200ms
                    _logger.warning("vk: " + unicode_str(e))
                    self._vk_error_time = t

        return self._vk

    def reset_vk(self):
        self._vk = None
        self._vk_error_time = 0


    # Methods concerning the application
    def do_quit_onboard(self):
        _logger.debug("Entered do_quit_onboard")
        self.final_cleanup()
        self.cleanup()

    def cleanup(self):
        config.cleanup()

        # Make an effort to disconnect all handlers.
        # Used to be used for safe restarting.
        for instance, handler_id in self._connections:
            instance.disconnect(handler_id)

        if self.keyboard:
            self.keyboard.cleanup()

        self.status_icon.set_keyboard_window(None)
        self._window.cleanup()
        self._window.destroy()
        self._window = None
        Gtk.main_quit()

    def final_cleanup(self):
        config.final_cleanup()

    @staticmethod
    def _can_show_in_current_desktop():
        """
        When GNOME's "Typing Assistent" is enabled in GNOME Shell, Onboard 
        starts simultaneously with the Shell's built-in screen keyboard. 
        With GNOME Shell 3.5.4-0ubuntu2 there is no known way to choose
        one over the other (LP: 879942). 

        Adding NotShowIn=GNOME; to onboard-autostart.desktop prevents it 
        from running not only in GNOME Shell, but also in the GMOME Fallback 
        session, which is undesirable. Both share the same xdg-desktop name.

        -> Do it ourselves: optionally check for GNOME Shell and yield to the
        built-in keyboard.
        """
        result = True

        if config.options.not_show_in:
            bus = dbus.SessionBus()
            current = os.environ.get("XDG_CURRENT_DESKTOP", "")
            names = config.options.not_show_in.split(",")
            for name in names:                
                if name == "GNOME":
                    if bus.name_has_owner("org.gnome.Shell"):
                        result = False
                elif name == current:
                    result = False

            if not result:
                _logger.info("Command line option not-show-in={} forbids running in "
                             "current desktop environment '{}'; exiting." \
                             .format(names, current))
        return result


class ServiceOnboardKeyboard(dbus.service.Object):
    """
    Onboard's D-Bus service.
    """

    PATH = "/org/onboard/Onboard/Keyboard"
    IFACE = "org.onboard.Onboard.Keyboard"

    class ServiceOnboardException(dbus.DBusException):
        _dbus_error_name = 'org.onboard.Exception'


    def __init__(self, keyboard):
        super(ServiceOnboardKeyboard, self).__init__(dbus.SessionBus(), self.PATH)
        self._keyboard = keyboard

    @dbus.service.method(dbus_interface=IFACE)
    def Show(self):
        self._keyboard.set_visible(True)

    @dbus.service.method(dbus_interface=IFACE)
    def Hide(self):
        self._keyboard.set_visible(False)

    @dbus.service.method(dbus_interface=dbus.PROPERTIES_IFACE,
                         in_signature='ss', out_signature='v')
    def Get(self, iface, prop):
        if iface == self.IFACE:
            if prop == 'Visible':
                return self._keyboard.is_visible()
            else:
                raise self.ServiceOnboardException(\
                    ('Unknown property \'{0}\'').format(prop))
        else:
            raise self.ServiceOnboardException(\
                ('Unknown interface \'{0}\'').format(iface))

    @dbus.service.method(dbus_interface=dbus.PROPERTIES_IFACE, in_signature='ssv')
    def Set(self, iface, prop, value):
        if iface == self.IFACE:
            if prop == 'Visible':
                raise self.ServiceOnboardException(\
                    ('Property \'{0}\' is read-only').format(prop))
            else:
                raise self.ServiceOnboardException(\
                    ('Unknown property \'{0}\'').format(prop))
        else:
            raise self.ServiceOnboardException(\
                ('Unknown interface \'{0}\'').format(iface))

    @dbus.service.method(dbus_interface=dbus.PROPERTIES_IFACE,
                         in_signature='s', out_signature='a{sv}')
    def GetAll(self, iface):
        if iface == self.IFACE:
            return { 'Visible': self._keyboard.is_visible() }
        else:
            raise self.ServiceOnboardException(\
                ('Unknown interface \'{0}\'').format(iface))

    @dbus.service.method(dbus_interface=dbus.INTROSPECTABLE_IFACE, out_signature='s')
    def Introspect(self):
        ref = dbus.service.Object.Introspect(self, self._object_path, self.connection)

        iface = '  <interface name="{}">\n' \
                '      <property name="Visible" type="b" access="read"/>\n' \
                '  </interface>\n' \
                .format(self.IFACE)

        return ref[:-8] + iface + '</node>\n'

    @dbus.service.signal(dbus_interface=dbus.PROPERTIES_IFACE, signature='sa{sv}as')
    def PropertiesChanged(self, iface, changed, invalidated):
        return iface, changed, invalidated


def cb_any_event(event, onboard):
    # Update layout on keyboard group changes
    # XkbStateNotify maps to Gdk.EventType.NOTHING
    # https://bugzilla.gnome.org/show_bug.cgi?id=156948

    # Hide bug in Oneiric's GTK3
    # Suppress ValueError: invalid enum value: 4294967295
    try:
        type = event.type
    except ValueError:
        type = None

    if 0: # debug
        a = [event, event.type]
        if type == Gdk.EventType.VISIBILITY_NOTIFY:
            a += [event.state]
        if type == Gdk.EventType.CONFIGURE:
            a += [event.x, event.y, event.width, event.height]
        if type == Gdk.EventType.WINDOW_STATE:
            a += [event.window_state]
        if type == Gdk.EventType.UNMAP:
            a += [event.window, "0x{:x}".format(event.window.get_xid())]
        print(*a)

    #if type == Gdk.EventType.NOTHING:
    #    onboard.reload_layout()

    if type == Gdk.EventType.SETTING:
        if event.setting.name == "gtk-theme-name":
            onboard.on_gtk_theme_changed()
        elif event.setting.name in ["gtk-xft-dpi",
                                    "gtk-xft-antialias"
                                    "gtk-xft-hinting",
                                    "gtk-xft-hintstyle"]:
            # Update the cached pango layout object here or Onboard
            # doesn't get those settings, in particular the font dpi.
            # For some reason the font sizes are still off when running
            # this immediately. Delay it a little.
            GLib.idle_add(onboard.on_gtk_font_dpi_changed)

    Gtk.main_do_event(event)

