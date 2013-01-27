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

class Keyboard:
    def __init__(self):
        self.configured = None

        self._key_synth = None
        self._key_synth_virtkey = None
        self._key_synth_atspi = None

        self.reset()

    def reset(self):
        pass


    def dimensions(self):
        return self
    


