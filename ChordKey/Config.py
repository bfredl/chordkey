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



# enum for simplified number of resize_handles
class NumResizeHandles:
    NONE = 0
    SOME = 1
    ALL  = 2

config = None

def get_config():
    global config
    if config is None:
        config = ConfigObj()
    return config

class ConfigObj:
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

    def __init__(self):
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
            logfile = open("/tmp/chordkey.log", "w")
            sys.stdout = logfile
            sys.stderr = logfile

        logging.basicConfig(**log_params)

        # Add basic config children for usage before the single instance check.
        # All the others are added in self._init_keys().
        self.keyboard         = ConfigKeyboard()
        self.window           = ConfigWindow()
        self.icp_landscape    = IcpPos()
        self.icp_portrait    = IcpPos()
        self.theme_settings   = ConfigTheme()
        self.children = [self.keyboard,
                          self.window,
                          self.icp_landscape,
                          self.icp_portrait,
                          self.theme_settings]


    def init(self):
        """
        Second initialization stage.
        Call this after single instance checking on application start.
        """

        # call base class constructor once logging is available

        # init paths
        self.install_dir = self._get_install_dir()
        self.user_dir = self._get_user_dir()


        # Load system defaults (if there are any, not required).
        # Used for distribution specific settings, aka branding.
        paths = [os.path.join(self.install_dir, SYSTEM_DEFAULTS_FILENAME),
                 os.path.join("/etc/chordkey", SYSTEM_DEFAULTS_FILENAME)]

        self.mousetweaks = Mousetweaks()
        self.children.append(self.mousetweaks)
        self.clickmapper = ClickMapper()

        # initialize all property values
        self.init_properties()

        # Make sure there is a 'Default' entry when tracking the system theme.
        # 'Default' is the theme used when encountering an so far unknown
        # gtk-theme. 'Default' is added on first start and therefore a
        # corresponding system default is respected.
        theme_assocs = self.system_theme_associations.copy()
        if not "Default" in theme_assocs:
            theme_assocs["Default"] = self.theme
            self.system_theme_associations = theme_assocs


        global Theme
        from ChordKey.Appearance import Theme


        # remember state of mousetweaks click-type window
        if self.mousetweaks:
            self.mousetweaks.old_click_type_window_visible = \
                          self.mousetweaks.click_type_window_visible

            if self.mousetweaks.is_active() and \
                self.universal_access.hide_click_type_window:
                self.mousetweaks.click_type_window_visible = False

        # remember if we are running under GDM
        self.running_under_gdm = 'RUNNING_UNDER_GDM' in os.environ


        _logger.debug("Leaving init")

    def cleanup(self):
        # This used to stop dangling main windows from responding
        # when restarting. Restarts don't happen anymore, keep
        # this for now anyway.
        self.clickmapper.cleanup()
        if self.mousetweaks:
            self.mousetweaks.cleanup()

    def final_cleanup(self):
        if self.mousetweaks:
            if self.xid_mode:
                self.mousetweaks.click_type_window_visible = \
                        self.mousetweaks.old_click_type_window_visible
            else:
                if self.enable_click_type_window_on_exit:
                    self.mousetweaks.click_type_window_visible = True
                else:
                    self.mousetweaks.click_type_window_visible = \
                        self.mousetweaks.old_click_type_window_visible

    def init_properties(self):
        def req_init_defaults(obj):
            obj.init_defaults()
            if hasattr(obj,'children'):
                for c in obj.children:
                    req_init_defaults(c)
        req_init_defaults(self)


    def init_defaults(self):
        self.layout = DEFAULT_LAYOUT
        self.theme = DEFAULT_THEME
        self.show_status_icon = True
        self.show_tooltips = True
        self.start_minimized = False
        self.xembed_onboard = False
        self.use_system_defaults= False
        self.system_theme_tracking_enabled = True
        self.system_theme_associations = {}
        self.icp_in_use = True
        self.icp_resize_handles = DEFAULT_RESIZE_HANDLES
        self.auto_show_enabled = False
        self.auto_show_widget_clearance = (25.0, 55.0, 25.0, 40.0)
        self.drag_threshold = -1
        self.hide_click_type_window = True
        self.enable_click_type_window_on_exit = True

    @staticmethod
    def _get_user_sys_filename(filename, description, \
                               final_fallback = None,
                               user_filename_func = None,
                               system_filename_func = None):
        """
        Checks a filenames validity and if necessary expands it to a
        fully qualified path pointing to either the user or system directory.
        User directory has precedence over the system one.
        """

        filepath = filename
        if filename and not os.path.exists(filename):
            # assume filename is just a basename instead of a full file path
            _logger.debug(_format("{description} '{filename}' not found yet, "
                                  "retrying in default paths", \
                                  description=description, filename=filename))

            if user_filename_func:
                filepath = user_filename_func(filename)
                if not os.path.exists(filepath):
                    filepath = ""

            if  not filepath and system_filename_func:
                filepath = system_filename_func(filename)
                if not os.path.exists(filepath):
                    filepath = ""

            if not filepath:
                _logger.info(_format("unable to locate '{filename}', "
                                     "loading default {description} instead",
                                     description=description,
                                     filename=filename))
        if not filepath and not final_fallback is None:
            filepath = final_fallback

        if not os.path.exists(filepath):
            _logger.error(_format("failed to find {description} '{filename}'",
                                  description=description, filename=filename))
            filepath = ""
        else:
            _logger.debug(_format("{description} '{filepath}' found.",
                                  description=description, filepath=filepath))

        return filepath



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
               not self.auto_show_enabled

    def is_auto_show_enabled(self):
        return not self.xid_mode and \
               self.auto_show_enabled

    def is_force_to_top(self):
        return self.window.force_to_top or self.is_docking_enabled()

    def is_docking_enabled(self):
        return self.window.docking_enabled

    def is_dock_expanded(self, orientation_co):
        return self.window.docking_enabled and orientation_co.dock_expand

    def check_gnome_accessibility(self, parent = None):
        return True # FIXME
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
        threshold = self.drag_threshold
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
        return self.icp_in_use or self.is_icon_palette_last_unhide_option()

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
        self.icp_resize_handles_notify_add(callback)

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
        self.icp_resize_handles = icp_handles

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
    
    def icp_position_notify_add(self, callback):
        self.icp_landscape.x_notify_add(callback)
        self.icp_landscape.y_notify_add(callback)
        self.icp_portrait.x_notify_add(callback)
        self.icp_portrait.y_notify_add(callback)

    def icp_size_notify_add(self, callback):
        self.icp_landscape.width_notify_add(callback)
        self.icp_landscape.height_notify_add(callback)
        self.icp_portrait.width_notify_add(callback)
        self.icp_portrait.height_notify_add(callback)

    def _post_notify_hide_click_type_window(self):
        """ called when changed in gsettings (preferences window) """
        mousetweaks = self.mousetweaks

        if not mousetweaks:
            return
        if mousetweaks.is_active():
            if self.hide_click_type_window:
                mousetweaks.click_type_window_visible = False
            else:
                mousetweaks.click_type_window_visible = \
                            mousetweaks.old_click_type_window_visible

class IcpPos:
    def init_defaults(self):
        self.x = DEFAULT_ICP_X
        self.y = DEFAULT_ICP_Y
        self.width = DEFAULT_ICP_WIDTH
        self.height = DEFAULT_ICP_HEIGHT



class ConfigKeyboard:
    """Window configuration """

    def init_defaults(self):
        self.key_synth = 0 #XTest
        self.event_handling = 0 #GTK
        self.long_press_delay = 0.5
        self.touch_input =  2# MultiTouch


class ConfigWindow:
    """Window configuration """
    DEFAULT_DOCKING_EDGE = DockingEdge.BOTTOM
    def __init__(self):
        self.landscape = WindowPos()
        self.portrait = WindowPos()
        self.children = [self.landscape, self.portrait]

    def init_defaults(self):
        self.window_state_sticky = True
        self.window_decoration = False
        self.force_to_top = False
        self.keep_aspect_ratio = False
        self.transparent_background = False
        self.transparency = 0.0
        self.background_transparency = 10.0
        self.enable_inactive_transparency = False
        self.inactive_transparency = 50.0
        self.inactive_transparency_delay = 1.0
        self.resize_handles = DEFAULT_RESIZE_HANDLES
        self.docking_enabled = False
        self.docking_edge = DockingEdge.BOTTOM
        self.docking_shrink_workarea = True


    ##### property helpers #####

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

class WindowPos:
    def init_defaults(self):
        self.x = DEFAULT_X
        self.y = DEFAULT_Y
        self.width = DEFAULT_WIDTH
        self.height = DEFAULT_HEIGHT
        self.dock_width = DEFAULT_WIDTH
        self.dock_height = DEFAULT_HEIGHT
        self.dock_expand = True



class ConfigAutoShow:
    """ auto_show configuration """

    def _init_keys(self):
        self.schema = SCHEMA_AUTO_SHOW
        self.sysdef_section = "auto-show"




class ConfigTheme:
    """ Theme configuration """
    def init_defaults(self):
        self.color_scheme =  DEFAULT_COLOR_SCHEME
        self.background_gradient =  0.0
        self.key_style = "flat"
        self.roundrect_radius =  0.0
        self.key_size =  100.0
        self.key_stroke_width =  100.0
        self.key_fill_gradient =  0.0
        self.key_stroke_gradient =  0.0
        self.key_gradient_direction =  0.0
        self.key_label_font =  ""      # font for current theme
        self.key_shadow_strength =  20.0
        self.key_shadow_size =  5.0

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


if 0:
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


