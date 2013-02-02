# SPACE,ret,bksl,tab
# eaoeiu
# rhtns
# .,;:
# dlc
# 0123456789
# +=-_/?\|
# pyfqjkxbmwv
# ()[]{}<>
# ~!@#$%^&*
from itertools import product

def prodrange(*args):
    return product(*[range(a) for a in args])

def configure(kbd):
    kcode = kbd.keycode_action
    chkey = kbd.char_action
    ret  = kcode(36, '↵')
    bksp  = kcode(22, '⟻')
    DEL  = kcode(119, 'Del')
    ins  = kcode(118, 'Ins')
    tab   = kcode(23, '⇆')
    home  = kcode(110, 'Home')
    end   = kcode(115, 'End')
    LEFT  = kcode(113, '←')
    RIGHT = kcode(114, '→')
    UP    = kcode(111, '↑')
    DOWN  = kcode(116, '↓')
    esc  = kcode(9, 'Esc')
    SUPER  = kcode(116, '❖')
    ctrl  = kcode(116, 'Ctrl')
    alt  = kcode(116, 'Alt')
    space = kcode(65, '⸤  ⸥')
    alfa  = kcode(116, 'Alfa')
    num  = kcode(116, 'Num')
    pgup  = kcode(112, 'PgUp')
    pgdown  = kcode(117, 'PgDn')

    #  left     lower      upper
    #  right   llllluuuuu   llllluuuuu
    lrpairs = ["rhsntuioae","",        
              "[]\=-()',.",'{}?+_<>";:',
              "vwpkgfmdlc","",
              "0123456789","~!@#$%^&*\|",
              "`zqxbjyåäö", "´"]


    s_left = [bksp, home, end, esc, alfa,
                 tab,  LEFT, RIGHT, DEL, num] 
                 

    s_right = [SUPER, alt,  pgup,    UP, ret,
                  ctrl, ins,   pgdown, DOWN, space] 
             

    m = {}
    def putpair(lc,lr,rc,rr, a):
        lkey,rkey  = (0,lc,lr), (1,rc,rr)
        print(lkey, rkey, a.code)
        m[lkey,rkey] = a
        m[rkey,lkey] = a
        

    for (lcol,lrow),chars in zip(prodrange(5,2),lrpairs):
        for (rrow, rcol),ch in zip(prodrange(2,5),chars):
            putpair(lcol,1-lrow,rcol,rrow,chkey(ch))
            if ch.isalnum() and lrow == 0:
                putpair(lcol,lrow,rcol,rrow,chkey(ch.upper()))
    
    for (row,col),left,right in zip(prodrange(2,5),s_left,s_right):
        m[(0,col,row),] = left
        m[(1,col,row),] = right

    return m


