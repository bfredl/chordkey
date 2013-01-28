# -*- coding: utf-8 -*-
"""
File containing Config singleton.
"""

from __future__ import division, print_function, unicode_literals

import os
import sys
from shutil import copytree
from optparse import OptionParser

from gi.repository import GLib, Gtk

from ChordKey.utils        import show_confirmation_dialog, Version, unicode_str
from ChordKey.WindowUtils  import Handle, DockingEdge
from ChordKey.ConfigUtils  import ConfigObject
from ChordKey.MouseControl import Mousetweaks, ClickMapper
from ChordKey.Exceptions   import SchemaError

### Logging ###
import logging
_logger = logging.getLogger("Config")
###############

# gsettings schemas
SCHEMA_ONBOARD          = "org.onboard"
SCHEMA_KEYBOARD         = "org.onboard.keyboard"
SCHEMA_WINDOW           = "org.onboard.window"
SCHEMA_WINDOW_LANDSCAPE = "org.onboard.window.landscape"
SCHEMA_WINDOW_PORTRAIT  = "org.onboard.window.portrait"
SCHEMA_ICP              = "org.onboard.icon-palette"
SCHEMA_ICP_LANDSCAPE    = "org.onboard.icon-palette.landscape"
SCHEMA_ICP_PORTRAIT     = "org.onboard.icon-palette.portrait"
SCHEMA_AUTO_SHOW        = "org.onboard.auto-show"
SCHEMA_UNIVERSAL_ACCESS = "org.onboard.universal-access"
SCHEMA_THEME            = "org.onboard.theme-settings"
SCHEMA_LOCKDOWN         = "org.onboard.lockdown"
SCHEMA_SCANNER          = "org.onboard.scanner"

SCHEMA_GSS              = "org.gnome.desktop.screensaver"
SCHEMA_GDI              = "org.gnome.desktop.interface"
SCHEMA_GDA              = "org.gnome.desktop.a11y.applications"

MODELESS_GKSU_KEY = "/apps/gksu/disable-grab"  # old gconf key, unused

# hard coded defaults
DEFAULT_X                  = 100   # Make sure these match the schema defaults,
DEFAULT_Y                  = 50    # else dconf data migration won't happen.
DEFAULT_WIDTH              = 700
DEFAULT_HEIGHT             = 205

# Default rect on Nexus 7
# landscape x=65, y=500, w=1215 h=300
# portrait  x=55, y=343, w=736 h=295

DEFAULT_ICP_X              = 100   # Make sure these match the schema defaults,
DEFAULT_ICP_Y              = 50    # else dconf data migration won't happen.
DEFAULT_ICP_HEIGHT         = 64
DEFAULT_ICP_WIDTH          = 64

DEFAULT_LAYOUT             = "Compact"
DEFAULT_THEME              = "Classic Onboard"
DEFAULT_COLOR_SCHEME       = "Classic Onboard"

START_ONBOARD_XEMBED_COMMAND = "onboard --xid"

GTK_KBD_MIXIN_MOD          = "Onboard.KeyboardGTK"
GTK_KBD_MIXIN_CLS          = "KeyboardGTK"

INSTALL_DIR                = "/usr/share/onboard"
LOCAL_INSTALL_DIR          = "/usr/local/share/onboard"
USER_DIR                   = ".onboard"

SYSTEM_DEFAULTS_FILENAME   = "onboard-defaults.conf"

DEFAULT_RESIZE_HANDLES     = list(Handle.RESIZERS)

SCHEMA_VERSION_0_97         = Version(1, 0)   # Onboard 0.97
SCHEMA_VERSION_0_98         = Version(2, 0)   # Onboard 0.97.1
SCHEMA_VERSION_0_99         = Version(2, 1)   # Onboard 0.99.0
SCHEMA_VERSION              = SCHEMA_VERSION_0_99


# enum for simplified number of resize_handles
class NumResizeHandles:
    NONE = 0
    SOME = 1
    ALL  = 2

class Config(ConfigObject):
    """
    Singleton Class to encapsulate the gsettings stuff and check values.
    """

    # String representation of the module containing the Keyboard mixin
    # used to draw keyboard
    _kbd_render_mixin_mod = GTK_KBD_MIXIN_MOD

    # String representation of the keyboard mixin used to draw keyboard.
    _kbd_render_mixin_cls = GTK_KBD_MIXIN_CLS

    # extension of layout files
    LAYOUT_FILE_EXTENSION = ".onboard"

    # A copy of snippets so that when the list changes in gsettings we can
    # tell which items have changed.
    _last_snippets = None

    # Margin to leave around labels
    LABEL_MARGIN = (1, 1)

    # Horizontal label alignment
    DEFAULT_LABEL_X_ALIGN = 0.5

    # Vertical label alignment
    DEFAULT_LABEL_Y_ALIGN = 0.5

    # layout group for independently sized superkey labels
    SUPERKEY_SIZE_GROUP = "super"

    # width of frame around onboard when window decoration is disabled
    UNDECORATED_FRAME_WIDTH = 5.0

    # radius of the rounded window corners
    CORNER_RADIUS = 10

    # y displacement of the key face of dish keys
    DISH_KEY_Y_OFFSET = 1.0

    # raised border size of dish keys
    DISH_KEY_BORDER = (2.5, 2.5)

    # minimum time keys are drawn in pressed state
    UNPRESS_DELAY = 0.15

    # index of currently active pane, not stored in gsettings
    active_layer_index = 0

    # threshold protect window move/resize
    drag_protection = True

    # Allow to iconify onboard when neither icon-palette nor
    # status-icon are enabled, else hide and show the window.
    # Iconifying is shaky in unity and gnome-shell. After unhiding
    # from launcher once, the WM won't allow to unminimize onboard
    # itself anymore for auto-show. (Precise)
    allow_iconifying = False

    def __new__(cls, *args, **kwargs):
        """
        Singleton magic.
        """
        if not hasattr(cls, "self"):
            cls.self = object.__new__(cls, *args, **kwargs)
            cls.self.construct()
        return cls.self

    def __init__(self):
        """
        This constructor is still called multiple times.
        Do nothing here and use the singleton constructor construct() instead.
        Don't call base class constructors.
        """
        pass

    def construct(self):
        """
        Singleton constructor, runs only once.
        First intialization stage to runs before the
        single instance check. Only do the bare minimum here.
        """
        # parse command line
        parser = OptionParser()
        parser.add_option("-l", "--layout", dest="layout",
                help=_format("Layout file ({}) or name",
                             self.LAYOUT_FILE_EXTENSION))
        parser.add_option("-t", "--theme", dest="theme",
                help=_("Theme file (.theme) or name"))
        parser.add_option("-x", type="int", dest="x", help=_("Window x position"))
        parser.add_option("-y", type="int", dest="y", help=_("Window y position"))
        parser.add_option("-s", "--size", dest="size",
                help=_("Window size, widthxheight"))
        parser.add_option("-e", "--xid", action="store_true", dest="xid_mode",
                help=_("Start in XEmbed mode, e.g. for gnome-screensaver"))
        parser.add_option("-a", "--keep-aspect", action="store_true",
                dest="keep_aspect_ratio",
                help=_("Keep aspect ratio when resizing the window"))
        parser.add_option("-d", "--debug", type="str", dest="debug",
            help="DEBUG={notset|debug|info|warning|error|critical}")
        parser.add_option("-m", "--allow-multiple-instances",
                action="store_true", dest="allow_multiple_instances",
                help=_("Allow multiple Onboard instances"))
        parser.add_option("-q", "--quirks", dest="quirks",
                help=_("Override auto-detection and manually select quirks\n"
                       "QUIRKS={metacity|compiz|mutter}"))
        parser.add_option("--not-show-in", dest="not_show_in",
                metavar="DESKTOPS",
                help=_("Silently fail to start in the given desktop "
                       "environments. DESKTOPS is a comma-separated list of "
                       "XDG desktop names, e.g. GNOME for GNOME Shell."
                       ))

        options = parser.parse_args()[0]
        self.options = options

        self.xid_mode = options.xid_mode
        self.quirks = options.quirks

        # setup logging
        log_params = {
            "format" : '%(asctime)s:%(levelname)s:%(name)s: %(message)s'
        }
        if options.debug:
             log_params["level"] = getattr(logging, options.debug.upper())
        if False: # log to file
            log_params["level"] = "DEBUG"
            logfile = open("/tmp/onboard.log", "w")
            sys.stdout = logfile
            sys.stderr = logfile

        logging.basicConfig(**log_params)

        # Add basic config children for usage before the single instance check.
        # All the others are added in self._init_keys().
        self.children = []
        self.gnome_a11y = self.add_optional_child(ConfigGDA)
        self.gnome_a11y.init_from_gsettings()


    def init(self):
        """
        Second initialization stage.
        Call this after single instance checking on application start.
        """

        # call base class constructor once logging is available
        try:
            ConfigObject.__init__(self)
        except SchemaError as e:
            _logger.error(unicode_str(e))
            sys.exit()

        # init paths
        self.install_dir = self._get_install_dir()
        self.user_dir = self._get_user_dir()

        # migrate old user dir ".sok" to ".onboard"
        old_user_dir = os.path.join(os.path.expanduser("~"), ".sok")
        user_dir = self.user_dir
        if not os.path.exists(user_dir) and os.path.exists(old_user_dir):
            _logger.info(_format("Migrating user directory '{}' to '{}'.", \
                                 old_user_dir, user_dir))
            try:
                copytree(old_user_dir, user_dir)
            except OSError as ex: # python >2.5
                _logger.error(_format("Failed to migrate user directory. ") + \
                              unicode_str(ex))

        # Load system defaults (if there are any, not required).
        # Used for distribution specific settings, aka branding.
        paths = [os.path.join(self.install_dir, SYSTEM_DEFAULTS_FILENAME),
                 os.path.join("/etc/onboard", SYSTEM_DEFAULTS_FILENAME)]
        self.load_system_defaults(paths)

        # initialize all property values
        self.init_properties(self.options)

        # Make sure there is a 'Default' entry when tracking the system theme.
        # 'Default' is the theme used when encountering an so far unknown
        # gtk-theme. 'Default' is added on first start and therefore a
        # corresponding system default is respected.
        theme_assocs = self.system_theme_associations.copy()
        if not "Default" in theme_assocs:
            theme_assocs["Default"] = self.theme
            self.system_theme_associations = theme_assocs

        # remember command line theme for system theme tracking
        if self.options.theme:
            self.remember_theme(self.theme)

        # load theme
        global Theme
        from ChordKey.Appearance import Theme
        self.apply_theme()

        # give gtk theme a chance to take over
        self.update_theme_from_system_theme()

        # misc initializations
        self._last_snippets = dict(self.snippets)  # store a copy

        # remember state of mousetweaks click-type window
        if self.mousetweaks:
            self.mousetweaks.old_click_type_window_visible = \
                          self.mousetweaks.click_type_window_visible

            if self.mousetweaks.is_active() and \
                self.universal_access.hide_click_type_window:
                self.mousetweaks.click_type_window_visible = False

        # remember if we are running under GDM
        self.running_under_gdm = 'RUNNING_UNDER_GDM' in os.environ

        # tell config objects that their properties are valid now
        self.on_properties_initialized()

        _logger.debug("Leaving init")

    def cleanup(self):
        # This used to stop dangling main windows from responding
        # when restarting. Restarts don't happen anymore, keep
        # this for now anyway.
        self.disconnect_notifications()
        self.clickmapper.cleanup()
        if self.mousetweaks:
            self.mousetweaks.cleanup()

    def final_cleanup(self):
        if self.mousetweaks:
            if self.xid_mode:
                self.mousetweaks.click_type_window_visible = \
                        self.mousetweaks.old_click_type_window_visible
            else:
                if self.universal_access.enable_click_type_window_on_exit:
                    self.mousetweaks.click_type_window_visible = True
                else:
                    self.mousetweaks.click_type_window_visible = \
                        self.mousetweaks.old_click_type_window_visible

    def _init_keys(self):
        """ Create key descriptions """

        self.schema = SCHEMA_ONBOARD
        self.sysdef_section = "main"

        self.add_key("schema-version", "") # is assigned SCHEMA_VERSION on first start
        self.add_key("use-system-defaults", False)
        self.layout_key = \
        self.add_key("layout", DEFAULT_LAYOUT)
        self.theme_key  = \
        self.add_key("theme",  DEFAULT_THEME)
        self.add_key("system-theme-tracking-enabled", True)
        self.add_key("system-theme-associations", {}, 'a{ss}')
        self.add_key("snippets", {}, "as")
        self.add_key("show-status-icon", True)
        self.add_key("start-minimized", False)
        self.add_key("xembed-onboard", False, prop="onboard_xembed_enabled")
        self.add_key("show-tooltips", True)
        self.add_key("key-label-font", "")      # default font for all themes
        self.add_key("key-label-overrides", {}, "as") # default labels for all themes
        self.add_key("current-settings-page", 0)

        self.keyboard         = ConfigKeyboard()
        self.window           = ConfigWindow()
        self.icp              = ConfigICP(self)
        self.auto_show        = ConfigAutoShow()
        self.universal_access = ConfigUniversalAccess(self)
        self.theme_settings   = ConfigTheme(self)
        self.lockdown         = ConfigLockdown(self)
        self.scanner          = ConfigScanner(self)
        self.gss              = ConfigGSS(self)
        self.gdi              = ConfigGDI(self)

        self.children += [self.keyboard,
                          self.window,
                          self.icp,
                          self.auto_show,
                          self.universal_access,
                          self.theme_settings,
                          self.lockdown,
                          self.gss,
                          self.gdi,
                          self.scanner]

        try:
            self.mousetweaks = Mousetweaks()
            self.children.append(self.mousetweaks)
        except (SchemaError, ImportError) as e:
            _logger.warning(unicode_str(e))
            self.mousetweaks = None

        self.clickmapper = ClickMapper()

    def init_from_gsettings(self):
        """
        Overloaded to migrate old dconf data to new gsettings schemas
        """
        ConfigObject.init_from_gsettings(self)

        # --- onboard 0.97 -> 0.98 ---------------------------------------------
        format = Version.from_string(self.schema_version)
        if format < SCHEMA_VERSION_0_98:
            _logger.info("Migrating dconf values from before v0.98: "
                         "/apps/onboard -> /org/onboard")
            self.migrate_dconf_tree("apps.", "org.")

            # --- onboard 0.96 -> 0.97 ---------------------------------------------
            format = Version.from_string(self.schema_version)
            if format < SCHEMA_VERSION_0_97:
                _logger.info("Migrating dconfs values from before v0.97")
                self._migrate_to_0_97()

            self.schema_version = SCHEMA_VERSION.to_string()

    def _migrate_to_0_97(self):
        # window rect moves from org.onboard to
        # org.onboard.window.landscape/portrait
        co = self.window.landscape
        if co.gskeys["x"].is_default() and \
           co.gskeys["y"].is_default() and \
           co.gskeys["width"].is_default() and \
           co.gskeys["height"].is_default():

            co.delay()
            co.migrate_dconf_value("/apps/onboard/x", co.gskeys["x"])
            co.migrate_dconf_value("/apps/onboard/y", co.gskeys["y"])
            co.migrate_dconf_value("/apps/onboard/width", co.gskeys["width"])
            co.migrate_dconf_value("/apps/onboard/height", co.gskeys["height"])
            co.apply()

        # icon-palette rect moves from org.onboard.icon-palette to
        # org.onboard.icon-palette.landscape/portrait
        co = self.icp.landscape
        if co.gskeys["x"].is_default() and \
           co.gskeys["y"].is_default() and \
           co.gskeys["width"].is_default() and \
           co.gskeys["height"].is_default():

            co.delay()
            co.migrate_dconf_value("/apps/onboard/icon-palette/x", co.gskeys["x"])
            co.migrate_dconf_value("/apps/onboard/icon-palette/y", co.gskeys["y"])
            co.migrate_dconf_value("/apps/onboard/icon-palette/width", co.gskeys["width"])
            co.migrate_dconf_value("/apps/onboard/icon-palette/height", co.gskeys["height"])
            co.apply()

        # move keys from root to window
        co = self.window
        co.migrate_dconf_key("/apps/onboard/window-decoration", "window-decoration")
        co.migrate_dconf_key("/apps/onboard/force-to-top", "force-to-top")
        co.migrate_dconf_key("/apps/onboard/transparent-background", "transparent-background")
        co.migrate_dconf_key("/apps/onboard/transparency", "transparency")
        co.migrate_dconf_key("/apps/onboard/background-transparency", "background-transparency")
        co.migrate_dconf_key("/apps/onboard/enable-inactive-transparency", "enable-inactive-transparency")
        co.migrate_dconf_key("/apps/onboard/inactive-transparency", "inactive-transparency")
        co.migrate_dconf_key("/apps/onboard/inactive-transparency-delay", "inactive-transparency-delay")

        # accessibility keys move from root to universal-access
        co = self.universal_access
        co.migrate_dconf_key("/apps/onboard/hide-click-type-window", "hide-click-type-window")
        co.migrate_dconf_key("/apps/onboard/enable-click-type-window-on-exit", "enable-click-type-window-on-exit")

        # move keys from root to keyboard
        co = self.keyboard
        co.migrate_dconf_key("/apps/onboard/show-click-buttons", "show-click-buttons")

    ##### handle special keys only valid in system defaults #####
    def _read_sysdef_section(self, parser):
        super(self.__class__, self)._read_sysdef_section(parser)

        # Convert the simplified superkey_label setting into
        # the more general key_label_overrides setting.
        sds = self.system_defaults
        if "superkey_label" in sds:
            overrides = sds.get( "key_label_overrides", {})
            group = self.SUPERKEY_SIZE_GROUP \
                if sds.get("superkey_label_independent_size") else ""
            for key_id in ["LWIN", "RWIN"]:
                overrides[key_id] = (sds["superkey_label"], group)
            sds["key_label_overrides"] = overrides

    def _convert_sysdef_key(self, gskey, sysdef, value):
        # key exclusive to system defaults?
        if sysdef in ["superkey-label", \
                      "superkey-label-independent-size"]:
            return value
        else:
            return super(self.__class__, self). \
                         _convert_sysdef_key(gskey, sysdef, value)


    ##### property helpers #####
    def _unpack_key_label_overrides(self, value):
        return self.unpack_string_list(value, "a{s[ss]}")

    def _pack_key_label_overrides(self, value):
        return self.pack_string_list(value)

    def _unpack_snippets(self, value):
        return self.unpack_string_list(value, "a{i[ss]}")

    def _pack_snippets(self, value):
        return self.pack_string_list(value)

    # Property layout_filename, linked to gsettings key "layout".
    # layout_filename may only get/set a valid filename,
    # whereas layout also allows to get/set only the basename of a layout.
    def layout_filename_notify_add(self, callback):
        self.layout_notify_add(callback)

    def get_layout_filename(self):
        gskey = self.layout_key
        return self.find_layout_filename(gskey.value, gskey.key,
                                     self.LAYOUT_FILE_EXTENSION,
                                     os.path.join(self.install_dir,
                                                  "layouts", DEFAULT_LAYOUT +
                                                  self.LAYOUT_FILE_EXTENSION))
    
    def set_layout_filename(self, filename):
        if filename and os.path.exists(filename):
            self.layout = filename
        else:
            _logger.warning(_format("layout '{filename}' does not exist", \
                                    filename=filename))

    layout_filename = property(get_layout_filename, set_layout_filename)


    def find_layout_filename(self, filename, description,
                                    extension = "", final_fallback = ""):
        """ Find layout file, either the final layout or an import file. """
        return self._get_user_sys_filename(
             filename    = filename,
             description = description,
             user_filename_func   = lambda x: \
                 os.path.join(self.user_dir,    "layouts", x) + extension,
             system_filename_func = lambda x: \
                 os.path.join(self.install_dir, "layouts", x) + extension,
             final_fallback       = final_fallback)

    # Property theme_filename, linked to gsettings key "theme".
    # theme_filename may only get/set a valid filename,
    # whereas theme also allows to get/set only the basename of a theme.
    def theme_filename_notify_add(self, callback):
        self.theme_notify_add(callback)

    def get_theme_filename(self):
        return self._get_user_sys_filename_gs(
             gskey                = self.theme_key,
             user_filename_func   = Theme.build_user_filename,
             system_filename_func = Theme.build_system_filename,
             final_fallback       = os.path.join(self.install_dir,
                                                "themes", DEFAULT_THEME +
                                                "." + Theme.extension()))
    def set_theme_filename(self, filename, save = True):
        if filename and os.path.exists(filename):
            self.set_theme(filename, save)

            # remember currently active gtk theme
            if self.system_theme_tracking_enabled:
                self.remember_theme(filename)
        else:
            _logger.warning(_format("theme '{filename}' does not exist", \
                                    filename=filename))

    theme_filename = property(get_theme_filename, set_theme_filename)

    def remember_theme(self, theme_filename):
        if self.gdi:   # be defensive
            gtk_theme = self.get_gtk_theme()
            theme_assocs = self.system_theme_associations.copy()
            theme_assocs[gtk_theme] = theme_filename
            self.system_theme_associations = theme_assocs

    def apply_theme(self):
        theme_filename = self.theme_filename
        _logger.info(_format("Loading theme from '{}'", theme_filename))

        theme = Theme.load(theme_filename)
        if not theme:
            _logger.error(_format("Unable to read theme '{}'", theme_filename))
        else:
            # Save to gsettings
            # Make sure gsettings is in sync with onboard (LP: 877601)
            self.theme = theme_filename
            theme.apply()

            # Fix theme not saved to gesettings when switching
            # system contrast themes.
            # Possible gsettings bug in Precise (wasn't in Oneiric).
            self.apply()

    def update_theme_from_system_theme(self):
        """ Switches themes for system theme tracking """
        if self.system_theme_tracking_enabled:
            gtk_theme = self.get_gtk_theme()
            theme_assocs = self.system_theme_associations

            new_theme = theme_assocs.get(gtk_theme, None)
            if not new_theme:
                new_theme = theme_assocs.get("Default", None)
                if not new_theme:
                    new_theme = DEFAULT_THEME

            self.theme = new_theme
            self.apply_theme()

    def get_gtk_theme(self):
        gtk_settings = Gtk.Settings.get_default()
        if gtk_settings:   # be defensive, don't know if this can fail
            gtk_theme = gtk_settings.get_property('gtk-theme-name')
            return gtk_theme
        return None

    def get_image_filename(self, image_filename):
        """
        Returns an absolute path for a label image.
        This function isn't linked to any gsettings key.'
        """
        return self._get_user_sys_filename(
             filename             = image_filename,
             description          = "image",
             user_filename_func   = lambda x: \
                 os.path.join(self.user_dir,    "layouts", "images", x),
             system_filename_func = lambda x: \
                 os.path.join(self.install_dir, "layouts", "images", x))

    def allow_system_click_type_window(self, allow):
        """ called from hover click button """
        if not self.mousetweaks:
            return

        # This assumes that mousetweaks.click_type_window_visible never
        # changes between activation and deactivation of mousetweaks.
        if allow:
            self.mousetweaks.click_type_window_visible = \
                self.mousetweaks.old_click_type_window_visible
        else:
            # hide the mousetweaks window when onboard's settings say so
            if self.universal_access.hide_click_type_window:

                self.mousetweaks.old_click_type_window_visible = \
                            self.mousetweaks.click_type_window_visible

                self.mousetweaks.click_type_window_visible = False

    def enable_hover_click(self, enable):
        if enable:
            self.allow_system_click_type_window(False)
            self.mousetweaks.set_active(True)
        else:
            self.mousetweaks.set_active(False)
            self.allow_system_click_type_window(True)

    def is_hover_click_active(self):
        return bool(self.mousetweaks) and self.mousetweaks.is_active()

    def is_visible_on_start(self):
        return self.xid_mode or \
               not self.start_minimized and \
               not self.auto_show.enabled

    def is_auto_show_enabled(self):
        return not self.xid_mode and \
               self.auto_show.enabled

    def is_force_to_top(self):
        return self.window.force_to_top or self.is_docking_enabled()

    def is_docking_enabled(self):
        return self.window.docking_enabled

    def is_dock_expanded(self, orientation_co):
        return self.window.docking_enabled and orientation_co.dock_expand

    def check_gnome_accessibility(self, parent = None):
        if not self.xid_mode and \
           not self.gdi.toolkit_accessibility:
            question = _("Enabling auto-show requires Gnome Accessibility.\n\n"
                         "Onboard can turn on accessiblity now, however it is "
                         "recommended that you log out and back in "
                         "for it to reach its full potential.\n\n"
                         "Enable accessibility now?")
            reply = show_confirmation_dialog(question, parent)
            if not reply == True:
                return False

            self.gdi.toolkit_accessibility = True

        return True

    def get_drag_threshold(self):
        threshold = self.universal_access.gskeys["drag_threshold"].value
        if threshold == -1:
            # get the systems DND threshold
            threshold = Gtk.Settings.get_default(). \
                                    get_property("gtk-dnd-drag-threshold")
        return threshold

    def is_icon_palette_in_use(self):
        """
        Show icon palette when there is no other means to unhide onboard.
        Unhiding by unity launcher isn't available in force-to-top mode.
        """
        return self.icp.in_use or self.is_icon_palette_last_unhide_option()

    def is_icon_palette_last_unhide_option(self):
        """
        Is the icon palette the last remaining way to unhide onboard?
        Consider single instance check a way to always unhide onboard.
        """
        return False

    def has_unhide_option(self):
        """
        No native ui visible to unhide onboard?
        There might still be the launcher to unminimize it.
        """
        return self.is_icon_palette_in_use() or self.show_status_icon

    def has_window_decoration(self):
        """ Force-to-top mode doesn't support window decoration """
        return self.window.window_decoration and not self.is_force_to_top()

    def get_sticky_state(self):
        return not self.xid_mode and \
               (self.window.window_state_sticky or self.is_force_to_top())

    def is_inactive_transparency_enabled(self):
        return self.window.enable_inactive_transparency and \
               not self.scanner.enabled
    def is_keep_aspect_ratio_enabled(self):
        return self.window.keep_aspect_ratio or self.options.keep_aspect_ratio

    ####### resize handles #######
    def resize_handles_notify_add(self, callback):
        self.window.resize_handles_notify_add(callback)
        self.icp.resize_handles_notify_add(callback)

    def get_num_resize_handles(self):
        """ Translate array of handles to simplified NumResizeHandles enum """
        handles = self.window.resize_handles
        if len(handles) == 0:
            return NumResizeHandles.NONE
        if len(handles) == 8:
            return NumResizeHandles.ALL
        return NumResizeHandles.SOME

    def set_num_resize_handles(self, num):
        if num == NumResizeHandles.ALL:
            window_handles = list(Handle.RESIZERS)
            icp_handles    = list(Handle.RESIZERS)
        elif num == NumResizeHandles.NONE:
            window_handles = []
            icp_handles    = []
        else:
            window_handles = list(Handle.CORNERS)
            icp_handles    = [Handle.SOUTH_EAST]

        self.window.resize_handles = window_handles
        self.icp.resize_handles = icp_handles

    @staticmethod
    def _string_to_handles(string):
        """ String of handle ids to array of Handle enums """
        ids = string.split()
        handles = []
        for id in ids:
            handle = Handle.RIDS.get(id)
            if not handle is None:
                handles.append(handle)
        return handles

    @staticmethod
    def _handles_to_string(handles):
        """ Array of handle enums to string of handle ids """
        ids = []
        for handle in handles:
            ids.append(Handle.IDS[handle])
        return " ".join(ids)

                #self.set_drag_handles(config.window.resize_handles)
    ####### Snippets editing #######
    def set_snippet(self, index, value):
        """
        Set a snippet in the snippet list.  Enlarge the list if not big
        enough.

        @type  index: int
        @param index: index of the snippet to set.
        @type  value: str
        @param value: Contents of the new snippet.
        """
        if value == None:
            raise TypeError("Snippet text must be str")

        label, text = value
        snippets = dict(self.snippets) # copy to enable callbacks
        _logger.info("Setting snippet %d to '%s', '%s'" % (index, label, text))
        snippets[index] = (label, text)
        self.snippets = snippets

    def del_snippet(self, index):
        """
        Delete a snippet.

        @type  index: int
        @param index: index of the snippet to delete.
        """
        _logger.info("Deleting snippet %d" % index)
        snippets = dict(self.snippets) # copy to enable callbacks
        del snippets[index]
        self.snippets = snippets


    ###### gnome-screensaver, xembedding #####
    def enable_gss_embedding(self, enable):
        if enable:
            self.onboard_xembed_enabled = True
            self.gss.embedded_keyboard_enabled = True
            self.set_xembed_command_string_to_onboard()
        else:
            self.onboard_xembed_enabled = False
            self.gss.embedded_keyboard_enabled = False

    def is_onboard_in_xembed_command_string(self):
        """
        Checks whether the gsettings key for the embeded application command
        contains the entry defined by onboard.
        Returns True if it is set to onboard and False otherwise.
        """
        if self.gss.embedded_keyboard_command.startswith(START_ONBOARD_XEMBED_COMMAND):
            return True
        else:
            return False

    def set_xembed_command_string_to_onboard(self):
        """
        Write command to start the embedded onboard into the corresponding
        gsettings key.
        """
        self.gss.embedded_keyboard_command = START_ONBOARD_XEMBED_COMMAND

    def _get_kbd_render_mixin(self):
        __import__(self._kbd_render_mixin_mod)
        return getattr(sys.modules[self._kbd_render_mixin_mod],
                self._kbd_render_mixin_cls)
    kbd_render_mixin = property(_get_kbd_render_mixin)


    # modeless gksu - disabled until gksu moves to gsettings
    def modeless_gksu_notify_add(self, callback):
        pass
    modeless_gksu = property(lambda self: False)


    def _get_install_dir(self):
        result = None

        # when run from source
        src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        src_data_path = os.path.join(src_path, "data")
        if os.path.isfile(os.path.join(src_data_path, "org.onboard.gschema.xml")):
            # Add the data directory to the icon search path
            icon_theme = Gtk.IconTheme.get_default()
            src_icon_path = os.path.join(src_path, "icons")
            icon_theme.append_search_path(src_icon_path)
            result = src_path
        # when installed to /usr/local
        elif os.path.isdir(LOCAL_INSTALL_DIR):
            result = LOCAL_INSTALL_DIR
        # when installed to /usr
        elif os.path.isdir(INSTALL_DIR):
            result = INSTALL_DIR

        assert(result)  # warn early when the installation dir wasn't found
        return result

    def _get_user_dir(self):
        return os.path.join(os.path.expanduser("~"), USER_DIR)


class ConfigKeyboard(ConfigObject):
    """Window configuration """
    DEFAULT_KEY_ACTION = 1 # Release-only, supports long press
    DEFAULT_KEY_SYNTH  = 0 # XTest
    DEFAULT_TOUCH_INPUT = 2 # multi
    DEFAULT_EVENT_HANDLING = 0 # GTK

    def _init_keys(self):
        self.schema = SCHEMA_KEYBOARD
        self.sysdef_section = "keyboard"

        self.add_key("show-click-buttons", False)
        self.add_key("sticky-key-release-delay", 0.0)
        self.add_key("sticky-key-behavior", {"all" : "cycle"}, 'a{ss}')
        self.add_key("long-press-delay", 0.5)
        self.add_key("default-key-action", self.DEFAULT_KEY_ACTION,
                                           enum={"single-stroke" : 0,
                                                 "delayed-stroke" : 1,
                                                })
        self.add_key("key-synth", self.DEFAULT_KEY_SYNTH, 
                                           enum={"XTest" : 0,
                                                 "AT-SPI" : 1,
                                                })
        self.add_key("touch-input", self.DEFAULT_TOUCH_INPUT, 
                                           enum={"none" : 0,
                                                 "single" : 1,
                                                 "multi" : 2,
                                                })
        self.add_key("event-handling", self.DEFAULT_EVENT_HANDLING, 
                                           enum={"GTK" : 0,
                                                 "XInput" : 1,
                                                })


class ConfigWindow(ConfigObject):
    """Window configuration """
    DEFAULT_DOCKING_EDGE = DockingEdge.BOTTOM

    def _init_keys(self):
        self.schema = SCHEMA_WINDOW
        self.sysdef_section = "window"

        self.add_key("window-state-sticky", True)
        self.add_key("window-decoration", False)
        self.add_key("force-to-top", False)
        self.add_key("keep-aspect-ratio", False)
        self.add_key("transparent-background", False)
        self.add_key("transparency", 0.0)
        self.add_key("background-transparency", 10.0)
        self.add_key("enable-inactive-transparency", False)
        self.add_key("inactive-transparency", 50.0)
        self.add_key("inactive-transparency-delay", 1.0)
        self.add_key("resize-handles", DEFAULT_RESIZE_HANDLES)
        self.add_key("docking-enabled", False)
        self.add_key("docking-edge", self.DEFAULT_DOCKING_EDGE, 
                                     enum={"top"    : DockingEdge.TOP,
                                           "bottom" : DockingEdge.BOTTOM,
                                          })
        self.add_key("docking-shrink-workarea", True)

        self.landscape = ConfigWindow.Landscape(self)
        self.portrait = ConfigWindow.Portrait(self)

        self.children = [self.landscape, self.portrait]

    ##### property helpers #####
    def _convert_sysdef_key(self, gskey, sysdef, value):
        if sysdef == "resize-handles":
            return Config._string_to_handles(value)
        else:
            return ConfigObject._convert_sysdef_key(self, gskey, sysdef, value)

    def _unpack_resize_handles(self, value):
        return Config._string_to_handles(value)

    def _pack_resize_handles(self, value):
        return Config._handles_to_string(value)

    def position_notify_add(self, callback):
        self.landscape.x_notify_add(callback)
        self.landscape.y_notify_add(callback)
        self.portrait.x_notify_add(callback)
        self.portrait.y_notify_add(callback)

    def size_notify_add(self, callback):
        self.landscape.width_notify_add(callback)
        self.landscape.height_notify_add(callback)
        self.portrait.width_notify_add(callback)
        self.portrait.height_notify_add(callback)

    def dock_size_notify_add(self, callback):
        self.landscape.dock_width_notify_add(callback)
        self.landscape.dock_height_notify_add(callback)
        self.portrait.dock_width_notify_add(callback)
        self.portrait.dock_height_notify_add(callback)

    def docking_notify_add(self, callback):
        self.docking_enabled_notify_add(callback)
        self.docking_edge_notify_add(callback)
        self.docking_shrink_workarea_notify_add(callback)

        self.landscape.dock_expand_notify_add(callback)
        self.portrait.dock_expand_notify_add(callback)

    def get_active_opacity(self):
        return 1.0 - self.transparency / 100.0

    def get_inactive_opacity(self):
        return 1.0 - self.inactive_transparency / 100.0

    def get_minimal_opacity(self):
        # Return the lowest opacity the window can have when visible.
        return min(self.get_active_opacity(), self.get_inactive_opacity())

    def get_background_opacity(self):
        return 1.0 - self.background_transparency / 100.0

    class Landscape(ConfigObject):
        def _init_keys(self):
            self.schema = SCHEMA_WINDOW_LANDSCAPE
            self.sysdef_section = "window.landscape"

            self.add_key("x", DEFAULT_X)
            self.add_key("y", DEFAULT_Y)
            self.add_key("width", DEFAULT_WIDTH)
            self.add_key("height", DEFAULT_HEIGHT)
            self.add_key("dock-width", DEFAULT_WIDTH)
            self.add_key("dock-height", DEFAULT_HEIGHT)
            self.add_key("dock-expand", True)

    class Portrait(ConfigObject):
        def _init_keys(self):
            self.schema = SCHEMA_WINDOW_PORTRAIT
            self.sysdef_section = "window.portrait"

            self.add_key("x", DEFAULT_X)
            self.add_key("y", DEFAULT_Y)
            self.add_key("width", DEFAULT_WIDTH)
            self.add_key("height", DEFAULT_HEIGHT)
            self.add_key("dock-width", DEFAULT_WIDTH)
            self.add_key("dock-height", DEFAULT_HEIGHT)
            self.add_key("dock-expand", True)


class ConfigICP(ConfigObject):
    """ Icon palette configuration """

    def _init_keys(self):
        self.schema = SCHEMA_ICP
        self.sysdef_section = "icon-palette"

        self.add_key("in-use", False)
        self.add_key("resize-handles", DEFAULT_RESIZE_HANDLES)

        self.landscape = ConfigICP.Landscape(self)
        self.portrait = ConfigICP.Portrait(self)

        self.children = [self.landscape, self.portrait]

    ##### property helpers #####
    def _convert_sysdef_key(self, gskey, sysdef, value):
        if sysdef == "resize-handles":
            return Config._string_to_handles(value)
        else:
            return ConfigObject._convert_sysdef_key(self, gskey, sysdef, value)

    def _unpack_resize_handles(self, value):
        return Config._string_to_handles(value)

    def _pack_resize_handles(self, value):
        return Config._handles_to_string(value)

    def position_notify_add(self, callback):
        self.landscape.x_notify_add(callback)
        self.landscape.y_notify_add(callback)
        self.portrait.x_notify_add(callback)
        self.portrait.y_notify_add(callback)

    def size_notify_add(self, callback):
        self.landscape.width_notify_add(callback)
        self.landscape.height_notify_add(callback)
        self.portrait.width_notify_add(callback)
        self.portrait.height_notify_add(callback)

    class Landscape(ConfigObject):
        def _init_keys(self):
            self.schema = SCHEMA_ICP_LANDSCAPE
            self.sysdef_section = "icon-palette.landscape"

            self.add_key("x", DEFAULT_ICP_X)
            self.add_key("y", DEFAULT_ICP_Y)
            self.add_key("width", DEFAULT_ICP_WIDTH)
            self.add_key("height", DEFAULT_ICP_HEIGHT)

    class Portrait(ConfigObject):
        def _init_keys(self):
            self.schema = SCHEMA_ICP_PORTRAIT
            self.sysdef_section = "icon-palette.portrait"

            self.add_key("x", DEFAULT_ICP_X)
            self.add_key("y", DEFAULT_ICP_Y)
            self.add_key("width", DEFAULT_ICP_WIDTH)
            self.add_key("height", DEFAULT_ICP_HEIGHT)


class ConfigAutoShow(ConfigObject):
    """ auto_show configuration """

    def _init_keys(self):
        self.schema = SCHEMA_AUTO_SHOW
        self.sysdef_section = "auto-show"

        self.add_key("enabled", False)
        self.add_key("widget-clearance", (25.0, 55.0, 25.0, 40.0), '(dddd)')


class ConfigUniversalAccess(ConfigObject):
    """ universal_access configuration """

    def _init_keys(self):
        self.schema = SCHEMA_UNIVERSAL_ACCESS
        self.sysdef_section = "universal-access"

        self.add_key("drag-threshold", -1)
        self.add_key("hide-click-type-window", True)
        self.add_key("enable-click-type-window-on-exit", True)

    def _post_notify_hide_click_type_window(self):
        """ called when changed in gsettings (preferences window) """
        mousetweaks = self.parent.mousetweaks

        if not mousetweaks:
            return
        if mousetweaks.is_active():
            if self.hide_click_type_window:
                mousetweaks.click_type_window_visible = False
            else:
                mousetweaks.click_type_window_visible = \
                            mousetweaks.old_click_type_window_visible


class ConfigTheme(ConfigObject):
    """ Theme configuration """

    def _init_keys(self):
        self.schema = SCHEMA_THEME
        self.sysdef_section = "theme-settings"

        self.add_key("color-scheme", DEFAULT_COLOR_SCHEME,
                     prop="color_scheme_filename")
        self.add_key("background-gradient", 0.0)
        self.add_key("key-style", "flat")
        self.add_key("roundrect-radius", 0.0)
        self.add_key("key-size", 100.0)
        self.add_key("key-stroke-width", 100.0)
        self.add_key("key-fill-gradient", 0.0)
        self.add_key("key-stroke-gradient", 0.0)
        self.add_key("key-gradient-direction", 0.0)
        self.key_label_font_key = \
        self.add_key("key-label-font", "")      # font for current theme
        self.key_label_overrides_key = \
        self.add_key("key-label-overrides", {}, "as") # labels for current theme
        self.add_key("key-shadow-strength", 20.0)
        self.add_key("key-shadow-size", 5.0)

    ##### property helpers #####
    def theme_attributes_notify_add(self, callback):
        self.background_gradient_notify_add(callback)
        self.key_style_notify_add(callback)
        self.roundrect_radius_notify_add(callback)
        self.key_size_notify_add(callback)
        self.key_stroke_width_notify_add(callback)
        self.key_fill_gradient_notify_add(callback)
        self.key_stroke_gradient_notify_add(callback)
        self.key_gradient_direction_notify_add(callback)
        self.key_label_font_notify_add(callback)
        self.key_label_overrides_notify_add(callback)
        self.key_style_notify_add(callback)
        self.key_shadow_strength_notify_add(callback)
        self.key_shadow_size_notify_add(callback)

    def _can_set_color_scheme_filename(self, filename):
        if not os.path.exists(filename):
            _logger.warning(_format("color scheme '{filename}' does not exist", \
                                    filename=filename))
            return False
        return True

    def _unpack_key_label_overrides(self, value):
        return self.unpack_string_list(value, "a{s[ss]}")

    def _pack_key_label_overrides(self, value):
        return self.pack_string_list(value)

    def get_key_label_overrides(self):
        gskey = self.key_label_overrides_key

        # merge with default value from onboard base config
        value = dict(self.parent.key_label_overrides)
        value.update(gskey.value)

        return value

    def get_key_label_font(self):
        gskey = self.key_label_font_key

        value = gskey.value
        if not value:
            # get default value from onboard base config instead
            value = self.parent.key_label_font

        return value


class ConfigLockdown(ConfigObject):
    """ Lockdown/Kiosk mode configuration """

    def _init_keys(self):
        self.schema = SCHEMA_LOCKDOWN
        self.sysdef_section = "lockdown"

        self.add_key("disable-click-buttons", False)
        self.add_key("disable-hover-click", False)
        self.add_key("disable-dwell-activation", False)
        self.add_key("disable-preferences", False)
        self.add_key("disable-quit", False)
        self.add_key("disable-touch-handles", False)
        self.add_key("disable-keys", [["CTRL", "LALT", "F[0-9]+"]], 'aas')

    def lockdown_notify_add(self, callback):
        self.disable_click_buttons_notify_add(callback)
        self.disable_hover_click_notify_add(callback)
        self.disable_preferences_notify_add(callback)
        self.disable_quit_notify_add(callback)


class ConfigGSS(ConfigObject):
    """ gnome-screen-saver configuration keys"""

    def _init_keys(self):
        self.schema = SCHEMA_GSS
        self.sysdef_section = "gnome-screen-saver"

        self.add_key("embedded-keyboard-enabled", True)
        self.add_key("embedded-keyboard-command", "")


class ConfigGDI(ConfigObject):
    """ Key to enable Gnome Accessibility"""

    def _init_keys(self):
        self.schema = SCHEMA_GDI
        self.sysdef_section = "gnome-desktop-interface"

        self.add_key("toolkit-accessibility", False)
        self.add_key("gtk-theme", "", writable=False)  # read-only for safety


class ConfigGDA(ConfigObject):
    """ Key to check if a11y keyboard is enabled """

    def _init_keys(self):
        self.schema = SCHEMA_GDA
        self.sysdef_section = "gnome-desktop-a11y-applications"

        # read-only for safety
        self.add_key("screen-keyboard-enabled", False, writable=False)


class ConfigScanner(ConfigObject):
    """ Scanner configuration """

    DEFAULT_INTERVAL          = 1.20
    DEFAULT_INTERVAL_FAST     = 0.05
    DEFAULT_MODE              = 0 # AutoScan
    DEFAULT_CYCLES            = 2
    DEFAULT_BACKTRACK         = 5
    DEFAULT_ALTERNATE         = False
    DEFAULT_USER_SCAN         = False
    DEFAULT_DEVICE_NAME       = "Default"
    DEFAULT_DEVICE_KEY_MAP    = {}
    DEFAULT_DEVICE_BUTTON_MAP = { 1: 0, 3: 5 } # Button 1: Step, Button 3: Activate
    DEFAULT_FEEDBACK_FLASH    = True

    def _init_keys(self):
        self.schema = SCHEMA_SCANNER
        self.sysdef_section = "scanner"

        self.add_key("enabled", False)
        self.add_key("mode", self.DEFAULT_MODE, enum={"Autoscan" : 0,
                                                      "Overscan" : 1,
                                                      "Stepscan" : 2,
                                                      "Directed" : 3})
        self.add_key("interval", self.DEFAULT_INTERVAL)
        self.add_key("interval-fast", self.DEFAULT_INTERVAL_FAST)
        self.add_key("cycles", self.DEFAULT_CYCLES)
        self.add_key("backtrack", self.DEFAULT_BACKTRACK)
        self.add_key("alternate", self.DEFAULT_ALTERNATE)
        self.add_key("user-scan", self.DEFAULT_USER_SCAN)
        self.add_key("device-name", self.DEFAULT_DEVICE_NAME)
        self.add_key("device-detach", False)
        self.add_key("device-key-map", self.DEFAULT_DEVICE_KEY_MAP, 'a{ii}')
        self.add_key("device-button-map", self.DEFAULT_DEVICE_BUTTON_MAP, 'a{ii}')
        self.add_key("feedback-flash", self.DEFAULT_FEEDBACK_FLASH)
