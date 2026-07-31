import re

# Read the QMK font file
with open("glcdfont_lily.c", "r") as f:
    data = f.read()

# Extract all hex bytes from the font array
hex_bytes = re.findall(r'0x[0-9A-Fa-f]{2}', data)
hex_bytes = [int(h, 16) for h in hex_bytes]

# QMK 6x8 font has 6 bytes per character
chars = [hex_bytes[i:i+6] for i in range(0, len(hex_bytes), 6)]

# Function to convert 6x8 -> 8x8 by adding padding
def convert_char(char6):
    char8 = []
    char8.append(0x00)
    for byte in char6:
        # Shift left 1 bit to pad to 8 bits (optional, can also pad right)
        char8.append(byte)
    # Add two empty columns (0x00) to make 8 columns total
    char8.append(0x00)

    return char8

# Convert all characters
chars8 = [convert_char(c) for c in chars]

# Flatten the list back to a single array
font8 = [b for c in chars8 for b in c]

# Write the new font to a C header
with open("font_8x8.c", "w") as f:
    f.write("#include \"progmem.h\"\n")
    f.write("const unsigned char font[] PROGMEM = {\n")
    for i, b in enumerate(font8):
        f.write(f"0x{b:02X}, ")
        if (i + 1) % 8 == 0:
            f.write("\n")
    f.write("};\n")

print("Conversion complete! Saved as font_8x8.h")
