#!/usr/bin/env python3
"""
Convert a QMK-style 6x8 C font array (6 bytes per glyph) into an 8x8 font
by scaling each glyph horizontally from 6 columns -> 8 columns.

Usage:
    python3 qmk6x8_to_8x8.py input_font.c output_font_8x8.h [--method nearest|linear]

Notes:
- Assumes each glyph is 6 bytes (columns) with 8 rows (bits) per column.
- Keeps vertical size = 8 (no vertical scaling).
- Bits orientation is preserved: bit 0 is row 0, bit 7 is row 7 (same as input).
"""

import re
import sys
import argparse
from math import floor

def parse_args():
    p = argparse.ArgumentParser(description="Rescale 6x8 font to 8x8 (horizontal scaling).")
    p.add_argument("input", nargs="?", default="glcdfont_lily.c" ,help="Input C file containing the font array")
    p.add_argument("output", nargs="?", default="font_8x8_scaled.c",
                   help="Output C header filename (default: font_8x8_scaled.h)")
    p.add_argument("--method", choices=("nearest", "linear"), default="nearest",
                   help="Resampling method for horizontal scaling (default: linear).")
    return p.parse_args()

def extract_hex_bytes(text):
    # Find all 0xXX sequences within the file
    hexs = re.findall(r'0x[0-9A-Fa-f]{2}', text)
    return [int(h, 16) for h in hexs]

def bytes_to_glyphs(byte_list, bytes_per_glyph=6):
    if len(byte_list) % bytes_per_glyph != 0:
        print("Warning: total number of bytes is not divisible by %d." % bytes_per_glyph)
    glyphs = [byte_list[i:i+bytes_per_glyph] for i in range(0, len(byte_list), bytes_per_glyph)]
    return glyphs

def glyph_columns_to_bits(columns):
    # columns: list of ints (each 0-255) length = input width (6)
    # returns bits[col][row] where row 0..7
    bits = []
    for c in columns:
        col_bits = [(c >> r) & 1 for r in range(8)]
        bits.append(col_bits)
    return bits  # shape: [in_w][8]

def bits_to_column_byte(col_bits):
    # col_bits: list of 8 bits for rows 0..7
    b = 0
    for r, bit in enumerate(col_bits):
        if bit:
            b |= (1 << r)
    return b

def resample_glyph_horizontal(bits_in, out_w=8, method="linear"):
    """
    bits_in: list of in_w columns, each column is list of 8 bits (rows)
    returns list of out_w column bytes (ints)
    """
    in_w = len(bits_in)
    out_cols = []

    # mapping factor - map new_x in [0..out_w-1] to src index in [0..in_w-1]
    # we'll use src_f = new_x * (in_w - 1) / (out_w - 1) so endpoints align
    if out_w == 1:
        scale = 0.0
    else:
        scale = (in_w - 1) / (out_w - 1)

    for nx in range(out_w):
        src_f = nx * scale
        if method == "nearest":
            src_idx = int(round(src_f))
            src_idx = max(0, min(in_w - 1, src_idx))
            col_bits = bits_in[src_idx]
            out_cols.append(bits_to_column_byte(col_bits))
        else:  # linear interpolation across columns
            i0 = int(floor(src_f))
            i1 = min(i0 + 1, in_w - 1)
            w1 = src_f - i0
            w0 = 1.0 - w1
            # build new column bit-by-bit using weighted average and threshold 0.5
            new_bits = []
            for row in range(8):
                v0 = bits_in[i0][row]
                v1 = bits_in[i1][row]
                val = w0 * v0 + w1 * v1
                bit = 1 if val >= 0.5 else 0
                new_bits.append(bit)
            out_cols.append(bits_to_column_byte(new_bits))

    return out_cols  # list of ints length out_w

def convert_all_glyphs(glyphs6, method="linear"):
    glyphs8 = []
    for gidx, glyph in enumerate(glyphs6):
        bits = glyph_columns_to_bits(glyph)   # shape [6][8]
        new_cols = resample_glyph_horizontal(bits, out_w=8, method=method)
        glyphs8.append(new_cols)
    return glyphs8

def format_c_array(glyphs8, array_name="font8x8_scaled"):
    flat = [b for g in glyphs8 for b in g]
    lines = []
    lines.append('#include "progmem.h"')
    lines.append("")
    lines.append("const unsigned char %s[] PROGMEM = {" % array_name)
    # print 12-16 bytes per line for readability (here 8 per line is nice)
    for i, b in enumerate(flat):
        if i % 8 == 0:
            lines.append("  ")
        lines[-1] += "0x%02X, " % b
    lines.append("};")
    return "\n".join(lines)

def main():
    args = parse_args()
    with open(args.input, "r", encoding="utf-8") as f:
        txt = f.read()

    hex_bytes = extract_hex_bytes(txt)
    if not hex_bytes:
        print("No hex bytes found in the input file. Make sure it contains 0xXX entries.")
        sys.exit(1)

    glyphs6 = bytes_to_glyphs(hex_bytes, bytes_per_glyph=6)
    print("Found %d glyphs (6 bytes each) in input." % len(glyphs6))

    glyphs8 = convert_all_glyphs(glyphs6, method=args.method)
    out_text = format_c_array(glyphs8, array_name="font8x8_scaled")

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(out_text)

    print("Wrote scaled font to:", args.output)
    print("Method:", args.method)
    print("Each glyph is now 8 bytes (8 columns) -> 8x8.")

if __name__ == "__main__":
    main()
