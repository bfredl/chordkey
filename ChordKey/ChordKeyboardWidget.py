# -*- coding: utf-8 -*-
""" GTK keyboard widget """

from __future__ import division, print_function, unicode_literals

import sys
import time
from math import sin, pi

from gi.repository         import GLib, Gdk, Gtk, Pango, PangoCairo
import cairo

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

#FIXME conf, single or multitouch?
import sys
single_mode = "single" in sys.argv

#DrawState
STATE_NORMAL = 0
STATE_HOVER = 1
STATE_ACTIVATED = 2

PangoUnscale = 1.0 / Pango.SCALE
print( PangoUnscale)
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
        self.waiting = []
        self._pango_layout = Pango.Layout(context=Gdk.pango_context_get())

    def calculate_layout(self, rect):
        dim = self.keyboard.dimensions()
        r = rect
        keywidth = 75
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
        state = self.get_key_drawstate((side,c,r))
        label = self.get_key_label((side,c,r))

        draw_rect = rect.deflate(3)
        roundness = config.theme_settings.roundrect_radius 
        if roundness:
            roundrect_curve(context, draw_rect, roundness)
        else:
            context.rectangle(*draw_rect)
        if state == STATE_HOVER:
            fill = [0.8,0.5,0.0,1.0]
        elif state == STATE_ACTIVATED:
            fill = [0.0,0.6,0.2,0.8]
        else:
            fill = [0.8,0.8,0.8,0.6]
        context.set_source_rgba(*fill)
        context.fill()
        self.draw_text_center(context, label,rect,10,[0,0,0,1])


    def draw_text_center(self, context, text, rect, size, rgba):
        l = self._pango_layout
        l.set_text(text, -1)
        font_description = Pango.FontDescription(config.theme_settings.key_label_font)
        font_description.set_size(int(size*Pango.SCALE))
        l.set_font_description(font_description)
        w, h = l.get_size()   # In Pango units
        w, h = w*PangoUnscale,h*PangoUnscale # in pixels
        x = int(rect.x + (rect.w-w)/2.0)
        y = int(rect.y + (rect.h-h)/2.0)
        #print(x,y)
        context.move_to(x, y)
        context.set_source_rgba(*rgba)
        PangoCairo.show_layout(context, l)


    def redraw_key(self, key):
        if key is None:
            return
        side, c, r = key
        rect = self.panes[side].key_rect(c,r)
        self.queue_draw_area(*rect)

    def redraw_all(self):
        for p in self.panes:
            self.queue_draw_area(*p.rect)

    def find_key(self, x, y):
        for i,pane in enumerate(self.panes):
            if pane.rect.is_point_within((x,y)):
                c, r = pane.find_key(x, y)
                return i,c,r
        return None

    
    def get_key_drawstate(self, key):
        for seq in self.active_pointers:
            if seq.hover_key == key:
                return STATE_HOVER
        if key in self.waiting:
            return STATE_ACTIVATED
        return STATE_NORMAL


    def get_key_label(self, key):
        seq = list(self.waiting)
        if not seq and self.active_pointers:
            p = next(iter(self.active_pointers))
            if p.hover_key is not None:
                seq.append(p.hover_key)

        if key not in seq:
            seq.append(key)
        label = self.keyboard.get_action_label(seq)
        if label is None:
            return ""
        return label

    def on_ptr_down(self, seq):
        p = seq.point
        for pane in self.panes:
            if pane.rect.is_point_within(p):
                self.active_pointers.add(seq)
                break
        if seq in self.active_pointers:
            seq.hover_key = None
            self.on_ptr_move(seq)
            if seq.hover_key is not None:
                #self.redraw_all() #uneconomic but does it for now
                pass#self.on_key_down(seq.hover_key)
            return True
        return False

    def on_ptr_move(self, seq):
        if not seq in self.active_pointers:
            return False
        old_hover = seq.hover_key
        seq.hover_key = self.find_key(*seq.point)
        if seq.hover_key != old_hover:
            #self.redraw_key(old_hover)
            #self.redraw_key(seq.hover_key)
            self.redraw_all() #uneconomic but does it for now
        return True

    
    def on_ptr_up(self, seq):
        if not seq in self.active_pointers:
            return False
        self.active_pointers.remove(seq)
        first_single_press = single_mode and not self.waiting
        if self.active_pointers or first_single_press:
            if seq.hover_key is not None:
                k = seq.hover_key
                self.waiting.append(k)
                #print(self.waiting)
        else: #last seq
            #print("activated")
            key_seq = list(self.waiting) 
            if seq.hover_key not in key_seq:
                key_seq.append(seq.hover_key)
            self.waiting.clear()
            # last touch outside keyboard: cancel action
            if seq.hover_key is not None:
                print(key_seq)
                self.keyboard.invoke_action(key_seq)
            #for key in key_seq:
            #    self.redraw_key(key)
                

        #self.redraw_key(seq.hover_key)
        self.redraw_all()
        return True

    def has_active_sequence(self):
        return len(self.active_pointers ) > 0

                

