# -*- coding: utf-8 -*-

from __future__ import division, print_function, unicode_literals

import sys
import gc

from gi.repository import GObject, Gtk, Gdk, Atspi

from ChordKey              import KeyCommon
from ChordKey.MouseControl import MouseController
from ChordKey.utils        import Timer, Modifiers, parse_key_combination
#from ChordKey.canonical_equivalents import *
from ChordKey.KeySynth import KeySynthAtspi, KeySynthVirtkey

try:
    from ChordKey.utils import run_script, get_keysym_from_name, dictproperty
except DeprecationWarning:
    pass

### Config Singleton ###
from ChordKey.Config import get_config
config = get_config()
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

class Mods:
    SHIFT = 1
    CAPS = 2
    CTRL = 4
    ALT = 8
    NUMLK = 15
    MOD3 = 32
    SUPER = 64
    ALTGR = 128

MOD_LATCHED, MOD_LOCKED = range(2)
    
# should be treated as "inner classes" of ChordKeyboard 
class Action:
    def __init__(self,label,invoke=None):
        self.label = label
        if invoke is not None:
            self.invoke = invoke

    #abstract invoke(self, view): 
    #   return True if typed (should unlatch)
    #   False if modifier (don't unlatch other mods)

class TypeAction(Action):
    def __init__(self,label,kbd,key_type,key_code, mods=()):
        Action.__init__(self, label)
        self.keyboard = kbd # FIXME: cleaner?: make synth global
        self.key_type = key_type
        self.code = key_code
        self.mods = mods

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

    def invoke(self, view):
        key_synth = self.keyboard._key_synth
        for mod in self.mods:
            key_synth.lock_mod(mod)
        self._send_key_press()
        self._send_key_release()
        for mod in self.mods:
            key_synth.unlock_mod(mod)
        return True

# TODO: specify Sticky/latchy/lazyness
class ModAction(Action):
    def __init__(self,kbd,label,mod,key_code=None, mode=None):
        Action.__init__(self, label)
        self.keyboard = kbd 
        self.mod = mod
        self.key_code = key_code
        self.mode = mode

    def invoke(self, view):
        key_synth = self.keyboard._key_synth
        mods = self.keyboard.mods
        status = mods.get(self.mod,None)
        if status is None:
            key_synth.lock_mod(self.mod)
            mods[self.mod] = MOD_LATCHED
        elif status == MOD_LATCHED:
            mods[self.mod] = MOD_LOCKED
        elif status == MOD_LOCKED:
            key_synth.unlock_mod(self.mod)
            del mods[self.mod]
        return False # don't consume mods
        

class ChordKeyboard:
    def __init__(self):
        from ChordKey.testLayout import configure
        self.mapping = configure(self)
        self.configured = True

        self.waiting = []
        self.mods = {}

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
        return self.mapping.get(tuple(key_seq),None)

    def invoke_action(self, key_seq,view=None):
        a = self.get_action(key_seq)
        if a is not None:
            status = a.invoke(view)
            if status:
                self.unlatch_mods()
            return True
        else:
            return False

    def get_action_label(self, key_seq):
        a = self.get_action(key_seq)
        if a is not None:
            return a.label
        else:
            return None

    
    def char_action(self,ch, mods=(),label=None):
        if label is None:
            label = ch
        a = TypeAction(label,self,KeyCommon.CHAR_TYPE,ch,mods)
        return a

    def keycode_action(self, code, label):
        return TypeAction(label,self,KeyCommon.KEYCODE_TYPE,code)

    def mod_action(self, mod, label, key_code=None, mode=None):
        return ModAction(self, label, mod, key_code, mode)

    def hide_action(self,label):
        return Action(label, invoke=lambda v: v.set_visible(False))

    def unlatch_mods(self):
        for mod,status in list(self.mods.items()):
            if status == MOD_LATCHED:
                del self.mods[mod]
                self._key_synth.unlock_mod(mod)


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

    




