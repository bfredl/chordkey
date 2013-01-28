# -*- coding: utf-8 -*-
""" GTK keyboard widget """

from __future__ import division, print_function, unicode_literals

import sys
import time
from math import sin, pi

from gi.repository         import GLib, Gdk, Gtk

from ChordKey.utils         import Rect, Timer, FadeTimer, roundrect_arc
from ChordKey.utils         import brighten, roundrect_curve, gradient_line, \
                                drop_shadow
from ChordKey.WindowUtils   import WindowManipulator, Handle, DockingEdge, \
                                  limit_window_position, \
                                  get_monitor_rects
from ChordKey.TouchInput    import TouchInput, InputSequence
from ChordKey.Keyboard      import EventType
from ChordKey.KeyboardWidget import KeyboardWidget
from ChordKey.KeyGtk        import Key, RectKey
from ChordKey.KeyCommon     import LOD
from ChordKey               import KeyCommon
from ChordKey.TouchHandles  import TouchHandles
#from ChordKey.AtspiAutoShow import AtspiAutoShow

### Logging ###
import logging
_logger = logging.getLogger("KeyboardWidget")
###############

### Config Singleton ###
from ChordKey.Config import Config
config = Config()
########################

LEFT, RIGHT = 0, 1

class SubPane:
    def update_layout(self, rect, cols, rows):
        self.rect = rect
        self.key_width = float(rect.w)/cols
        self.key_height = float(rect.h)/rows
        self.cols, self.rows = cols, rows

    def key_rect(self, col, row):
        return Rect(self.rect.x+self.key_width*col, self.rect.y+self.key_height*row, self.key_width, self.key_height)

    def find_key(self, x, y):
        c = int((x-self.rect.x)/self.key_width)
        c = max(0,min(self.cols-1,c))
        r = int((y-self.rect.y)/self.key_height)
        r = max(0,min(self.rows-1,r))
        return c, r
    
class ChordKeyboardWidget(KeyboardWidget):
    def __init__(self, keyboard):
        KeyboardWidget.__init__(self,keyboard)
        self.panes = [SubPane() for i in range(2)]
        self.keyboard = keyboard
        self.active_pointers = set()

    def calculate_layout(self, rect):
        dim = self.keyboard.dimensions()
        r = rect
        keywidth = 50
        left_kdb_len = dim.left_cols*keywidth
        right_kdb_len = dim.left_cols*keywidth
        lrect = Rect(0,r[1],left_kdb_len,r[3])
        self.panes[LEFT].update_layout(lrect, dim.left_cols, dim.rows)
        rpos = rect.w-right_kdb_len
        rrect = Rect(rpos,r[1],right_kdb_len,r[3])
        self.panes[RIGHT].update_layout(rrect, dim.right_cols, dim.rows)
        
        self.mid_rect = Rect(left_kdb_len,r[1],rpos-left_kdb_len,r[3])
    
    def draw_keyboard(self, context, draw_rect):
        for side,panes in enumerate(self.panes):
            if draw_rect.intersects(panes.rect):
                self.draw_pane(side,context,draw_rect)

    def draw_pane(self, side, context, draw_rect):
        p = self.panes[side]
        r = draw_rect
        xmin, ymin = p.find_key(r.x,r.y)
        xmax, ymax = p.find_key(r.x+r.w,r.y+r.h)
        for x in range(xmin,xmax+1):
            for y in range(ymin,ymax+1):
                self.draw_key(side,x,y,context)

    def draw_key(self, side, c, r, context):
        rect = self.panes[side].key_rect(c,r)
        draw_rect = rect.deflate(3)
        roundness = config.theme_settings.roundrect_radius 
        if roundness:
            roundrect_curve(context, draw_rect, roundness)
        else:
            context.rectangle(*draw_rect)
        state = self.get_key_state((side,c,r))
        if state:
            fill = [0.8,0.1,0.0,0.9]
        else:
            fill = [0.2,0,0.8,0.5]
        context.set_source_rgba(*fill)
        context.fill()

    def redraw_key(self, key):
        if key is None:
            return
        side, c, r = key
        rect = self.panes[side].key_rect(c,r)
        self.queue_draw_area(*rect)

    def find_key(self, x, y):
        for i,pane in enumerate(self.panes):
            if pane.rect.is_point_within((x,y)):
                c, r = pane.find_key(x, y)
                return i,c,r
        return None

    
    def get_key_state(self, key):
        for seq in self.active_pointers:
            if seq.active_key == key:
                return True
        return False

    def on_ptr_down(self, seq):
        p = seq.point
        for pane in self.panes:
            if pane.rect.is_point_within(p):
                self.active_pointers.add(seq)
                break
        if seq in self.active_pointers:
            seq.active_key = None
            self.on_ptr_move(seq)
            if seq.active_key is not None:
                pass#self.on_key_down(seq.active_key)
            return True
        return False

    def on_ptr_move(self, seq):
        if not seq in self.active_pointers:
            return False
        old_active = seq.active_key
        seq.active_key = self.find_key(*seq.point)
        if seq.active_key != old_active:
            self.redraw_key(old_active)
            self.redraw_key(seq.active_key)
        return True

    
    def on_ptr_up(self, seq):
        if not seq in self.active_pointers:
            return False
        self.active_pointers.remove(seq)
        if seq.active_key is not None:
            self.redraw_key(seq.active_key)
        return True


                

