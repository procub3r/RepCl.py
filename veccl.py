import time

'''
Implementation of Replay Clock that uses dicts to store
offsets and counters between the current process and other
processes. As a result, the bitmap field is not required.
'''
class VecCl:
    def __init__(self, proc_id: int, proc_count: int, counter_bit_width: int) -> None:
        self.proc_id = proc_id   
        self.proc_count = proc_count
        self.counter_bit_width = counter_bit_width
        self.counter_array = [0 for _ in range(proc_count)]

    def __repr__(self) -> str:
        return f'VectorCl(proc_id={self.proc_id}, counters={self.counters})'

    def advance(self, proc_id) -> None:
        if (self.counter_array[proc_id] + 1) < 2**self.counter_bit_width:
            self.counter_array[proc_id] += 1

    def merge(self, other_counter) -> None:
        for i in range(self.proc_count):
            self.counter_array[i] = max(self.counter_array[i], other_counter[i])
        self.advance(self.proc_id)