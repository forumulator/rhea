
from __future__ import division
from __future__ import absolute_import

from myhdl import *
from ..system.regfile import RegisterFile
from ..system.regfile import Register

from _assign import m_assign
from _led_stroby import m_led_stroby
from _led_count import m_led_count
from _led_dance import m_led_dance

# create a simple register file for the "core"
regfile = RegisterFile()
select = Register("select", 0x00, 8, 'rw')
regfile.add_register(select)


def m_led_mm_per(glbl, regbus, leds, base_address=0x8240):
    """
    This (rather silly) core will select different LED
    displays based on the memory-mapped select regiter
    """
    Ndrv = 3 # the number of different drivers

    clock,reset = glbl.clock, glbl.reset
    rleds = Signal(intbv(0)[len(leds):])
    # assign the LED port to the local register
    gas = m_assign(leds, rleds)

    # memory-mapped registers
    greg = regfile.m_per_inteface(clock, reset, regbus,
                                  base_address=base_address)

    # led bus from each driver
    dled = [Signal(intbv(0)[len(leds):]) 
            for _ in range(Ndrv)]

    # instantiate different LED drivers
    gl = [None for _ in range(Ndrv)]
    gl[0] = m_led_stroby(clock, reset, dled[0])
    gl[1] = m_led_count(clock, reset, dled[1])
    gl[1] = m_led_dance(clock, reset, dled[2])

    @always_seq(clock.posedge, reset=rest)
    def rtl():
        for ii in range(Ndrv):
            idx = regfile.select
            rleds.next = dled[idx]


    return gas, gl, greg, rtl
    