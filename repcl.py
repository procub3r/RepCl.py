import time
import numpy as np
import math

class RepCl:
    def __init__(self, proc_id: np.uint64, interval: int, epsilon: float) -> None:
        self.proc_id: np.uint64 = proc_id
        self.interval = interval
        self.epsilon = epsilon
        self.bits_per_offset = math.ceil(math.log2(epsilon))

        self.hlc: np.uint64 = self.get_current_epoch()
        self.offset_bmp: np.uint64 = np.uint64(0)
        self.offsets: np.uint64 = np.uint64(0)
        self.counters: np.uint64 = np.uint64(0)

    def __repr__(self) -> str:
        offset_bmp = bin(self.offset_bmp)[2:].zfill(64)
        offsets = bin(self.offsets)[2:].zfill(64)
        counters = bin(self.counters)[2:].zfill(64)
        return f'RepCl(\n\tproc_id:\t{self.proc_id},\n\thlc:\t\t{self.hlc},\n\toffset_bmp:\t{offset_bmp},\n\toffsets:\t{offsets},\n\tcounters:\t{counters}\n)'

    def get_current_epoch(self) -> np.uint64:
        return np.uint64(time.time() * 1000 / self.interval)

    @staticmethod
    def extract(number, k, p):
        return ((1 << k) - 1) & (number >> p)

    def remove_offset_at_index(self, index):
        # 010 011 101
        #   2   1   0

        # 010 101 111 010 011
        # 000 010 101 000 000 


        new_offset = self.offsets >> self.bits_per_offset
        new_offset = new_offset >> (index * self.bits_per_offset)
        new_offset = new_offset << (index * self.bits_per_offset)

        self.offsets = self.offsets << (64 - (index * self.bits_per_offset))
        self.offsets = self.offsets >> (64 - (index * self.bits_per_offset))

        self.offsets |= new_offset

    def shift(self, new_hlc):
        index = 0

        bitmap = self.offset_bmp
        while (bitmap > 0):
            process_bit: np.uint64 = np.uint64((~(bitmap ^ (~(bitmap - 1))) + 1) >> 1)
            offset_at_index = self.get_offset_at_index(index)
            new_offset = min(new_hlc - (self.hlc - offset_at_index), self.epsilon)

            if (new_offset >= self.epsilon):
                self.remove_offset_at_index(index)
                self.offset_bmp = self.offset_bmp & (~process_bit)
            else:
                self.set_offset_at_index(index, new_offset)
                self.offset_bmp = self.offset_bmp | process_bit

            bitmap = bitmap & (bitmap - 1)
            index += 1

        self.hlc = new_hlc

    def set_offset_at_index(self, index, new_offset):
        if new_offset > (1 << self.bits_per_offset) - 1:
            raise ValueError('Offset value too large')

        mask = np.uint64((1 << self.bits_per_offset) - 1) << (index * self.bits_per_offset)
        mask = ~mask

        self.offsets = self.offsets & mask
        self.offsets = self.offsets | (new_offset << (index * self.bits_per_offset))

    def get_offset_at_index(self, index):
        offset = self.extract(self.offsets, self.bits_per_offset, index * self.bits_per_offset)
        return offset

    @staticmethod
    def hamming_weight(v: np.uint32) -> int:
        v = v - ((v >> 1) & 0x55555555)
        v = np.uint32((v & 0x33333333) + ((v >> 2) & 0x33333333))
        count = ((v + (v >> 4) & 0xF0F0F0F) * 0x1010101) >> 24
        return count

    @staticmethod
    def get_index_from_proc_id(bitmap: np.uint64, proc_id: np.uint64) -> int:
        bmp_lo: np.uint32 = np.uint32(bitmap & ((1 << 32) - 1))
        if proc_id < 32:
            bmp_lo <<= (32 - proc_id)
            return RepCl.hamming_weight(bmp_lo)
        bmp_hi: np.uint32 = np.uint32(bitmap >> 32)
        bmp_hi <<= (64 - proc_id)
        return RepCl.hamming_weight(bmp_hi) + RepCl.hamming_weight(bmp_lo)

    def send_local(self) -> float:
        startime = time.time()

        new_hlc = max(self.hlc, self.get_current_epoch())
        new_offset = new_hlc - self.hlc
        offset_at_pid = self.get_offset_at_index(self.proc_id)

        if (new_hlc == self.hlc and offset_at_pid <= new_offset):
            self.counters += 1
        elif (new_hlc == self.hlc):
            new_offset = min(new_offset, offset_at_pid)

            index = self.get_index_from_proc_id(self.offset_bmp, self.proc_id)
            self.set_offset_at_index(index, new_offset)
            self.offset_bmp |= np.uint64(1 << self.proc_id)

            self.counters = np.uint64(0)
            self.offset_bmp = self.offset_bmp | np.uint64(1 << self.proc_id)
        else:
            self.counters = np.uint64(0)
            self.shift(new_hlc)

            index = self.get_index_from_proc_id(self.offset_bmp, self.proc_id)
            self.set_offset_at_index(index, 0)
            self.offset_bmp |= np.uint64(1 << self.proc_id)

        endtime = time.time()
        return endtime - startime

    def merge_same_epoch(self, other: 'RepCl') -> None:
        self.offset_bmp |= other.offset_bmp
        bitmap = self.offset_bmp
        index = 0
        while bitmap > 0:
            pos_bit = np.uint64((~(bitmap ^ (~(bitmap - 1))) + 1) >> 1)
            new_offset = min(self.get_offset_at_index(index), other.get_offset_at_index(index))
            if new_offset >= self.epsilon:
                self.remove_offset_at_index(index)
                self.offset_bmp &= (~pos_bit)
            else:
                self.set_offset_at_index(index, new_offset)
                self.offset_bmp |= pos_bit

            bitmap &= bitmap - 1
            index += 1

    def equal_offset(self, other: 'RepCl') -> bool:
        if (other.hlc != self.hlc) or (other.offset_bmp != self.offset_bmp) or (other.offsets != self.offsets):
            return False
        return True

    def recv(self, other: 'RepCl') -> float:
        start_time = time.time()  # record start time
        new_hlc = max(self.hlc, other.hlc, self.get_current_epoch())
        a = self
        b = other

        a.shift(new_hlc)
        a.merge_same_epoch(b)

        if self.equal_offset(a) and other.equal_offset(a):
            a.counters = max(a.counters, other.counters)
            a.counters += 1
        elif self.equal_offset(a) and not other.equal_offset(a):
            a.counters += 1
        elif not self.equal_offset(a) and other.equal_offset(a):
            a.counters = other.counters
            a.counters += 1
        else:
            a.counters = np.uint64(0)

        self = a

        index = self.get_index_from_proc_id(self.offset_bmp, self.proc_id)
        self.set_offset_at_index(index, 0)
        self.offset_bmp |= np.uint64(1 << self.proc_id)

        end_time = time.time()  # record end time
        return end_time - start_time
