#!/usr/bin/env python3

import sys, os

def parse_int(s):
    if s.startswith('0x'):
        return int(s[2:], 16)
    return int(s)

def parse_end_offset(start_offset, end_offset):
    if end_offset.startswith('+'):
        return start_offset + int(end_offset[1:]) - 1
    return parse_int(end_offset)

bitmask_for_bits = {}
if 1:
    value = 0
    for num_bits in range(1, 64):
        value <<= 1
        value |= 1
        bitmask_for_bits[num_bits] = value

class csv_skipper(object):
    def __init__(self, c):
        self.c = c
        self.line = None
        self.eof = False

    def _read_line(self):
        try:
            line = self.c.__next__()
            while len(line) == 0:
                line = self.c.__next__()
            #print(line)
            return line
        except StopIteration:
            self.eof = True
            return None

    def next(self):
        if self.line is not None:
            line = self.line
            self.line = None
            return line
        return self._read_line()

    def peek(self):
        if self.line is None:
            self.line = self._read_line()
        return self.line

class BitDecoderParser(object):
    def __init__(self):
        pass

    def parse(self, filename):
        import csv
        f = open(filename, 'rt')
        c = csv.reader(open(filename, 'rt'))
        c = csv_skipper(c)
        b = BitDecoder()
        
        try:
            self.parse_fields(c, b)
        except StopIteration:
            pass

        f.close()
        return b

    def parse_fields(self, c, b):
        while not c.eof:
            self.parse_field(c, b)

    def parse_field(self, c, b):
        line = c.next()
        if line is None:
            return

        start_offset = parse_int(line[2])
        end_offset = parse_end_offset(start_offset, line[3])
        field = b.add_field(line[0], line[1], start_offset, end_offset)

        linei = c.peek()
        while not c.eof and linei is not None and linei[0] == '':
            self.parse_bitfield(c, field)
            linei = c.peek()

    def parse_bitfield(self, c, field):
        line = c.next()
        verbose_name = line[1]
        name = line[2]
        start_offset = parse_int(line[3])
        end_offset = parse_end_offset(start_offset, line[4])
        extra = line[5:]
        field.add_bitfield(verbose_name, name, start_offset, end_offset)

class BitDecoderBitField(object):
    def __init__(self, verbose_name, name, start_bit, end_bit):
        self.verbose_name = verbose_name
        self.name = name
        self.start_bit = start_bit
        self.end_bit = end_bit
        self.num_bits = self.end_bit + 1 - self.start_bit
        self.mask = bitmask_for_bits[self.num_bits]

    def decode(self, raw_data):
        val = raw_data >> self.start_bit
        val = val & self.mask
        print("    %s | %s = 0x%x / %d" % (self.verbose_name, self.name, val, val))

class BitDecoderField(object):
    def __init__(self, verbose_name, name, start_offset, end_offset):
        self.verbose_name = verbose_name
        self.name = name
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.num_bytes = self.end_offset + 1 - self.start_offset
        self.num_bits = self.num_bytes * 8
        self.bitfields = None

    def add_bitfield(self, verbose_name, name, start_bit, end_bit):
        if self.bitfields is None:
            self.bitfields = []
        assert(start_bit >= 0)
        assert(end_bit < self.num_bits)

        for bitfield in self.bitfields:
            if bitfield.start_bit < start_bit and end_bit < bitfield.end_bit:
                raise Exception("bitfields overlap")
            if start_bit < bitfield.start_bit and bitfield.end_bit < end_bit:
                raise Exception("bitfields overlap")

        bitfield = BitDecoderBitField(verbose_name, name, start_bit, end_bit)
        self.bitfields.append(bitfield)
        self.bitfields.sort(key=lambda bitfield: bitfield.start_bit)

    def decode_field(self, raw_data):
        print("%s | %s = 0x%x / %d" % (self.verbose_name, self.name, raw_data, raw_data))
        if self.bitfields:
            for bitfield in self.bitfields:
                bitfield.decode(raw_data)

class BitDecoder(object):
    def __init__(self):
        self.fields = []
        self.field_names = set()

    def add_field(self, verbose_name, name, start_offset, end_offset):
        assert(start_offset >= 0)
        assert(name not in self.field_names)
        next_offset = 0
        if len(self.fields) > 0:
            next_offset = self.fields[-1].end_offset + 1
        assert start_offset == next_offset, "start_offset is %d but next_offset should be %d" % (start_offset, next_offset)
        self.field_names.add(name)

        field = BitDecoderField(verbose_name, name, start_offset, end_offset)
        self.fields.append(field)
        return field

    def is_known_field(self, field_name):
        return field_name in self.field_names

    def decode_field(self, field_name, raw_data):
        for field in self.fields:
            if field.name == field_name:
                field.decode_field(raw_data)
                return

    def decode_full(self, raw_data):
        assert(false)

def raw_data(force_hex, arr):
    # we take either a single integer in either hex or decimal
    # TODO: handle array of bytes, need to think how to return things to make sense
    assert(len(arr) == 1)
    if arr[0].startswith('0x'):
        return int(arr[0][2:], 16)
    if force_hex:
        return int(arr[0], 16)
    return int(arr[0])

def load_file(filename):
    parser = BitDecoderParser()
    return parser.parse(filename)

def load_format(name):
    if os.path.exists(name):
        return load_file(name)

    filename = 'data/%s.csv' % name.replace('.', '/')
    return load_file(filename)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        usage()
    force_hex = False
    if '--hex' in sys.argv:
        force_hex = True
        sys.argv = [x for x in sys.argv if x != '--hex']
    data_format = load_format(sys.argv[1])
    if data_format.is_known_field(sys.argv[2]):
        data_format.decode_field(sys.argv[2], raw_data(force_hex, sys.argv[3:]))
    else:
        data_format.decode_full(raw_data(force_hex, sys.argv[2:]))
