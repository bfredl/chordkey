# -*- coding: utf-8 -*-

from __future__ import division, print_function, unicode_literals

import sys
import gc

from gi.repository import GObject, Gtk, Gdk, Atspi

#from ChordKey.KeyGtk       import *
from ChordKey              import KeyCommon
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

# should be treated as "inner classes" of ChordKeyboard 
class Action:
    def __init__(self,label,invoke=None):
        self.label = label
        if invoke is not None:
            self.invoke = invoke

class TypeAction(Action):
    def __init__(self,label,kbd,key_type,key_code):
        Action.__init__(self, label)
        self.keyboard = kbd # FIXME: cleaner?: make synth global
        self.key_type = key_type
        self.code = key_code

    def _send_key_press(self):
        key_synth = self.keyboard._key_synth
        ktype =  self.key_type
        if ktype == KeyCommon.CHAR_TYPE:
            key_synth.press_unicode(self.code)
        elif ktype == KeyCommon.KEYSYM_TYPE:
            key_synth.press_keysym(self.code)
        elif ktype == KeyCommon.KEYPRESS_NAME_TYPE:
            key_synth.press_keysym(get_keysym_from_name(self.code))
        elif ktype == KeyCommon.KEYCODE_TYPE:
            key_synth.press_keycode(self.code)

    def _send_key_release(self):
        key_synth = self.keyboard._key_synth
        ktype = self.key_type
        if ktype == KeyCommon.CHAR_TYPE:
            key_synth.release_unicode(self.code)
        elif ktype == KeyCommon.KEYSYM_TYPE:
            key_synth.release_keysym(self.code)
        elif ktype == KeyCommon.KEYPRESS_NAME_TYPE:
            key_synth.release_keysym(get_keysym_from_name(self.code))
        elif ktype == KeyCommon.KEYCODE_TYPE:
            key_synth.release_keycode(self.code);

    def invoke(self):
        self._send_key_press()
        self._send_key_release()
        return True
    

class ChordKeyboard:
    def __init__(self):
        self.configured = None
        self.conf_stupid()

        self.waiting = []

        self._key_synth = None
        self._key_synth_virtkey = None
        self._key_synth_atspi = None

        self.color_scheme = None # FIXME: not here!!!

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

    def get_action(self, key_seq):
        if not self.configured:
            return None
        return self.mapping.get(key_seq,None)

    def invoke_action(self, key_seq):
        a = self.get_action(key_seq)
        if a is not None:
            return a.invoke()
        else:
            return False

    
    def char_action(self,ch):
        a = TypeAction(ch,self,KeyCommon.CHAR_TYPE,ch)
        return a

    def conf_stupid(self):
        self.mapping = {}
        from itertools import product
        for  c1, r1, c2, r2 in product(range(5),range(2),range(5),range(2)):
            c = c2+5*(r2+2*(c1+5*r1))
            c = c + 31
            self.mapping[(0,c1,r1),(1,c2,r2)] = self.char_action(chr(c))
            self.mapping[(1,c2,r2),(0,c1,r1)] = self.char_action(chr(c))
        
        #for  c1, r1, in product(range(5),range(2)):
        #    c = c1+10*(r1+2*(c2+10*r2))
        #    c = c + 31
        #    self.mapping[(0,c1,r1),(1,c2,r2)] = self.char_action(chr(c))
        self.configured = True





