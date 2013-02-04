from itertools import product
from ChordKey.Keyboard import Mods
def prodrange(*args):
    return product(*[range(a) for a in args])

def configure(kbd):
    kcode = kbd.keycode_action
    chkey = kbd.char_action
    mod = kbd.mod_action
    RET  = kcode(36, '↵')
    BKSP  = kcode(22, '⟻')
    DEL  = kcode(119, 'Del')
    INS  = kcode(118, 'Ins')
    TAB   = kcode(23, '⇆')
    HOME  = kcode(110, 'Home')
    END   = kcode(115, 'End')
    LEFT  = kcode(113, '←')
    RIGHT = kcode(114, '→')
    UP    = kcode(111, '↑')
    DOWN  = kcode(116, '↓')
    ESC  = kcode(9, 'Esc')
    SUPER  = mod(Mods.SUPER, '❖')
    CTRL  = mod(Mods.CTRL, 'Ctrl')
    ALT  = mod(Mods.ALT, 'Alt')
    SPACE = kcode(65, '⸤  ⸥')
    ALFA  = kcode(116, 'Alfa')
    NUM  = kcode(116, 'Num')
    PGUP  = kcode(112, 'PgUp')
    PGDN  = kcode(117, 'PgDn')

    HIDE = kbd.hide_action("[x]")
    #  left     lower      upper
    #  right   llllluuuuu   llllluuuuu
    lrpairs = ["rhsntuioae","",        
              "[]\=-()',.",'{}?+_<>";:',
              "vwpkgfmdlc","",
              "0123456789","|!@#$%^&*\|",
              "`zqxbjyåäö", "~"]


    s_left = [BKSP, HOME, END, ESC, HIDE,
                 TAB,  LEFT, RIGHT, DEL, NUM] 
                 

    s_right = [SUPER, ALT,  PGUP,    UP, RET,
                  CTRL, INS,   PGDN, DOWN, SPACE] 
             

    m = {}
    def putpair(lc,lr,rc,rr, a):
        lkey,rkey  = (0,lc,lr), (1,rc,rr)
        m[lkey,rkey] = a
        m[rkey,lkey] = a
        

    for (lcol,lrow),chars in zip(prodrange(5,2),lrpairs):
        for (rrow, rcol),ch in zip(prodrange(2,5),chars):
            putpair(lcol,1-lrow,rcol,rrow,chkey(ch))
            if ch.isalnum() and lrow == 0:
                putpair(lcol,lrow,rcol,rrow,chkey(ch.upper()))
                m[(0,rcol,rrow),(0,lcol,1-rrow)] = chkey(ch, mods=[Mods.CTRL], label = "C-" + ch.upper())
                m[(1,rcol,rrow),(1,lcol,1-rrow)] = chkey(ch, mods=[Mods.SUPER], label = "❖-" + ch.upper())
    
    for (row,col),left,right in zip(prodrange(2,5),s_left,s_right):
        m[(0,col,row),] = left
        m[(1,col,row),] = right

    return m


