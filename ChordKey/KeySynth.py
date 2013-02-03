# -*- coding: utf-8 -*-

from __future__ import division, print_function, unicode_literals

import sys
import gc

from gi.repository import GObject, Gtk, Gdk, Atspi

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
from ChordKey.Config import get_config
config = get_config()
class KeySynthVirtkey:
    """ Synthesize key strokes with python-virtkey """

    def __init__(self, vk):
        self._vk = vk

    def cleanup(self):
        self._vk = None

    def press_unicode(self, char):
        if sys.version_info.major == 2:
            code_point = self.utf8_to_unicode(char)
        else:
            code_point = ord(char)
        self._vk.press_unicode(code_point)

    def release_unicode(self, char):
        if sys.version_info.major == 2:
            code_point = self.utf8_to_unicode(char)
        else:
            code_point = ord(char)
        self._vk.release_unicode(code_point)

    def press_keysym(self, keysym):
        self._vk.press_keysym(keysym)

    def release_keysym(self, keysym):
        self._vk.release_keysym(keysym)

    def press_keycode(self, keycode):
        self._vk.press_keycode(keycode)

    def release_keycode(self, keycode):
        self._vk.release_keycode(keycode)

    def lock_mod(self, mod):
        self._vk.lock_mod(mod)

    def unlock_mod(self, mod):
        self._vk.unlock_mod(mod)

    def press_key_string(self, keystr):
        """
        Send key presses for all characters in a unicode string
        and keep track of the changes in input_line.
        """
        capitalize = False

        keystr = keystr.replace("\\n", "\n")

        if self._vk:   # may be None in the last call before exiting
            for ch in keystr:
                if ch == "\b":   # backspace?
                    keysym = get_keysym_from_name("backspace")
                    self.press_keysym  (keysym)
                    self.release_keysym(keysym)

                elif ch == "\x0e":  # set to upper case at sentence begin?
                    capitalize = True

                elif ch == "\n":
                    # press_unicode("\n") fails in gedit.
                    # -> explicitely send the key symbol instead
                    keysym = get_keysym_from_name("return")
                    self.press_keysym  (keysym)
                    self.release_keysym(keysym)
                else:             # any other printable keys
                    self.press_unicode(ch)
                    self.release_unicode(ch)

        return capitalize


class KeySynthAtspi(KeySynthVirtkey):
    """ Synthesize key strokes with AT-SPI """

    def __init__(self, vk):
        super(KeySynthAtspi, self).__init__(vk)

    def press_key_string(self, string):
        #print("press_key_string")
        Atspi.generate_keyboard_event(0, string, Atspi.KeySynthType.STRING)

    def press_keycode(self, keycode):
        #print("press_keycode")
        Atspi.generate_keyboard_event(keycode, "", Atspi.KeySynthType.PRESS)

    def release_keycode(self, keycode):
        #print("release_keycode")
        Atspi.generate_keyboard_event(keycode, "", Atspi.KeySynthType.RELEASE)

