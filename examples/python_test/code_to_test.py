def initialize():
    global out, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10
    global x11, x12, x13, x14, x15, x16, x17, x18, x19, x20

    out = False

    x1 = True
    x2 = True
    x3 = True
    x4 = True
    x5 = True
    x6 = True
    x7 = True
    x8 = True
    x9 = True
    x10 = True
    x11 = True
    x12 = True
    x13 = True
    x14 = True
    x15 = True
    x16 = True
    x17 = True
    x18 = True
    x19 = True
    x20 = True


def process():
    global out, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10
    global x11, x12, x13, x14, x15, x16, x17, x18, x19, x20

    out = (
        ((x1 and (x2 or x3)) or ((x4 and x5) or (x6 and (x7 or x8))))
        and
        (((x9 or x10) and (x11 or (x12 and x13))) or ((x14 and (x15 or x16)) or ((x17 or x18) and (x19 or x20))))
    )