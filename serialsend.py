import serial
import time

ser = serial.Serial(
    port='/dev/ttyUSB1',   # adjust to your device
    baudrate=115200,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1
)

# 32-bit FPGA codes - LITTLE ENDIAN (LSB first)
# axis_adapter accumulates bytes with first byte in LSB
BIRTHDAY = bytes([0xF2, 0x35, 0xB8, 0x00])   # Sends LSB first to form 0x00B835F2
COCOFFEE = bytes([0xEE, 0xFF, 0xC0, 0xC0])   # Sends LSB first to form 0xC0C0FFEE

print("=== FPGA LED Control Test ===")

# --- Send birthday code ---
print("\n1. Sending BIRTHDAY (little-endian):", BIRTHDAY.hex())
print("   Will form 32-bit word: 0x00B835F2")
print("   Expected: LED turns ON")
ser.write(BIRTHDAY)
time.sleep(0.5)  # Wait for transmission

# Read loopback
rx1 = ser.read(4)
print("   RX loopback:", rx1.hex())

# --- Delay ---
print("\n2. Waiting 3 seconds...")
time.sleep(3)

# --- Send cocoffee code ---
print("\n3. Sending COCOFFEE (little-endian):", COCOFFEE.hex())
print("   Will form 32-bit word: 0xC0C0FFEE")
print("   Expected: LED turns OFF")
ser.write(COCOFFEE)
time.sleep(0.5)  # Wait for transmission

# Read loopback
rx2 = ser.read(4)
print("   RX loopback:", rx2.hex())

print("\n=== Test Complete ===")
print("Check the LED on your FPGA!")

ser.close()
