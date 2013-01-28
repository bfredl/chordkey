# -*- coding: utf-8 -*-

from __future__ import division, print_function, unicode_literals

import sys
import gc

from gi.repository import GObject, Gtk, Gdk, Atspi

#from ChordKey.KeyGtk       import *
#from ChordKey              import KeyCommon
#from ChordKey.KeyCommon    import StickyBehavior
from ChordKey.MouseControl import MouseController
#from ChordKey.Scanner      import Scanner
from ChordKey.utils        import Timer, Modifiers, parse_key_combination
#from ChordKey.canonical_equivalents import *
from ChordKey.KeySynth import KeySynthAtspi, KeySynthVirtkey

try:
    from ChordKey.utils import run_script, get_keysym_from_name, dictproperty
except DeprecationWarning:
    pass

### Config Singleton ###
from ChordKey.Config import Config
config = Config()
########################

### Logging ###
import logging
_logger = logging.getLogger("Keyboard")
###############
# enum of event types for key press/release
class EventType:
    (
        CLICK,
        DOUBLE_CLICK,
        DWELL,
    ) = range(3)

# enum dock mode
class DockMode:
    (
        FLOATING,
        BOTTOM,
        TOP,
    ) = range(3)



class ChordKeyboard:
    def __init__(self):
        self.configured = None

        self._key_synth = None
        self._key_synth_virtkey = None
        self._key_synth_atspi = None

        self.reset()

    def reset(self):
        pass


    def dimensions(self):
        self.left_cols = self.right_cols = 5
        self.rows = 2
        return self

    def cleanup(self):
        pass

    def init_key_synth(self, vk):
        self._key_synth_virtkey = KeySynthVirtkey(vk)
        self._key_synth_atspi = KeySynthAtspi(vk)

        if config.keyboard.key_synth: # == KeySynth.ATSPI:
            self._key_synth = self._key_synth_atspi
        else: # if config.keyboard.key_synth == KeySynth.VIRTKEY:
            self._key_synth = self._key_synth_virtkey


    def on_layout_loaded(self):
        pass

    def set_modifiers(self, *a):
        pass
    


