#!/usr/bin/env python3

from repcl import RepCl
from veccl import VecCl
import random
import time

'''
This program compares the performance of
vector clocks and replay clocks
'''

PROC_COUNT = 8

VECCL_COUNTER_WIDTH = 8

REPCL_FIELD_WIDTH = 64
REPCL_INTERVAL = 1
REPCL_EPSILON = 1

repcl = [RepCl(i, PROC_COUNT, REPCL_FIELD_WIDTH, 1, 1) for i in range(PROC_COUNT)]
veccl = [VecCl(i, PROC_COUNT, VECCL_COUNTER_WIDTH) for i in range(PROC_COUNT)]

while True:
    proc_id = random.randint(0, PROC_COUNT - 1)
    other_proc_id = random.randint(0, PROC_COUNT - 1)

    if proc_id == other_proc_id:
        repcl[proc_id].advance()
        veccl[proc_id].advance()
    else:
        repcl[proc_id].merge(repcl[other_proc_id])
        veccl[proc_id].merge(veccl[other_proc_id])

    print(repcl)
    print(veccl)
    print()

    time.sleep(0.8)
