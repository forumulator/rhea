
from __future__ import absolute_import
from __future__ import print_function

from copy import deepcopy
from myhdl import *
from ..regfile import Register
from .._clock import Clock
from .._reset import Reset

# a count of the number of memory-map peripherals
_mm_per = 0
_mm_list = {}

class MemMapController(object):
    def __init__(self, data_width=8, address_width=16):
        self.addr = Signal(intbv(0)[address_width:])
        self.wdata = Signal(intbv(0)[data_width:])
        self.rdata = Signal(intbv(0)[data_width:])
        self.read = Signal(bool(0))
        self.write = Signal(bool(0))
        self.done = Signal(bool(0))


class MemMap(object):
    """ Base class for the different memory-map interfaces.
    This is a base class for the various memory-mapped (control and status (CSR)
    register interfaces.
    """

    def __init__(self, data_width, address_width):
        self.data_width = data_width
        self.address_width = address_width
        self.names = {}
        self.regfiles = {}

        self.clock = Clock(bool(0))
        self.reset = Reset(0, active=1, async=False)

        self._write = False
        self._read = False
        self._address = 0
        self._data = 0
        self._write_data = -1  # holds the data written
        self._read_data = -1   # holds the data read

        # bus transaction timeout in clock ticks
        self.timeout = 100

    @property
    def is_write(self):
        return self._write

    @property
    def is_read(self):
        return self._read

    def get_read_data(self):
        return self._read_data

    def get_write_data(self):
        return self._write_data

    def get_address(self):
        return self._address

    def start_transaction(self, write, read, address, data=None):
        self._write = write
        self._read = read
        self._address = address
        if write:
            self._write_data = data
        elif read:
            self._read_data = data

    def end_transaction(self, data=None):
        if self._read and data is not None:
            self._read_data = data
        self._write = False
        self._read = False

    def write(self, addr, val):
        raise NotImplementedError

    def read(self, addr):
        raise NotImplementedError

    def ack(self, data=None):
        raise NotImplementedError

    def _add_bus(self, name):
        """ globally keep track of all per bus
        """
        global _mm_per, _mm_list
        nkey = "{:04d}".format(_mm_per) if name is None else name
        _mm_list[name] = self
        _mm_per += 1

    # @todo: make name and base_address attributes of regfile
    def add(self, glbl, regfile, name='', base_address=0):
        """ add a peripheral register-file to the bus
        """
        # want a copy of the register-file so that the
        # address can be adjusted.
        arf = deepcopy(regfile)

        for k,v in arf.__dict__.iteritems():
            if isinstance(v, Register):
                v.addr += base_address

        if self.regfiles.has_key(name):
            self.names[name] +=1
            name = name.upper() + "_{:03d}".format(self.names[name])
        else:
            self.names = {name : 0}
            name = name.upper() + "_000"

        self.regfiles[name] = arf       

        # @todo: return the peripheral generator
        g = self.m_per_interface(glbl, regfile, name, base_address)

        return g

    def m_per_interface(self, glbl, regfile, name, base_address=0):
         """ override
         :param glbl: global signals, clock and reset
         :param regfile: register file interfacing to.
         :param name: name of this interface
         :param base_address: base address for this register file
         :return:
         """
         pass


    def m_controller_basic(self, ctl):
        """
        Bus controllers (masters) are typically custom and
        built into whatever the controller is (e.g a processor).
        This is a simple example with a simple interface to
        invoke bus cycles.

        :param ctl:
        :return:
        """
        mm = self
        States = enum('Idle', 'Write', 'WriteAck', 'Read', 'ReadAck', 'Done')
        state = Signal(States.Idle)
        TOMAX = 33
        tocnt = Signal(intbv(0, min=0, max=TOMAX))

        @always(mm.clock.posedge)
        def rtl_assign():
            mm.address.next = ctl.addr
            mm.writedata.next = ctl.wdata

        @always_seq(wb.clock.posedge, reset=wb.reset)
        def rtl():
            # ~~~[Idle]~~~
            if state == States.Idle:
                if ctl.write:
                    state.next = States.Write
                    ctl.done.next = False
                elif ctl.read:
                    state.next = States.Read
                    ctl.done.next = False
                else:
                    ctl.done.next = True

            # ~~~[Write]~~~
            elif state == States.Write:
                if not wb.ack_o:
                    wb.we_i.next = True
                    wb.cyc_i.next = True
                    wb.stb_i.next = True
                    state.next = States.WriteAck
                    tocnt.next = 0

            # ~~~[WriteAck]~~~
            elif state == States.WriteAck:
                if wb.ack_o:
                    wb.we_i.next = False
                    wb.cyc_i.next = False
                    wb.stb_i.next = False
                    state.next = States.Done

            # ~~~[Done]~~~
            elif state == States.Done:
                ctl.done.next = True
                if not (ctl.write or ctl.read):
                    state.next = States.Idle

            else:
                assert False, "Invalid state %s" % (state,)

        return rtl_assign, rtl
