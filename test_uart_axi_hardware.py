#!/usr/bin/env python3
"""
UART-AXI Hardware Test Script

Tests the UART to AXI bridge functionality:
- GPIO reads (buttons)
- GPIO writes (LEDs)
- Memory writes and reads

Usage:
    python test_uart_axi_hardware.py /dev/ttyUSB1
"""

import serial
import sys
import time

# Protocol constants
CMD_WRITE = 0x10
CMD_READ = 0x11
GPIO_ADDRESS = 0xF0000000
MEM_BASE = 0x00000000

def create_write_command(addr, data_bytes):
    """Create a write command packet."""
    packet = [CMD_WRITE, len(data_bytes)]
    # Address (big-endian)
    packet.extend([
        (addr >> 24) & 0xFF,
        (addr >> 16) & 0xFF,
        (addr >> 8) & 0xFF,
        addr & 0xFF
    ])
    packet.extend(data_bytes)
    return packet

def create_read_command(addr, num_bytes):
    """Create a read command packet."""
    packet = [CMD_READ, num_bytes]
    # Address (big-endian)
    packet.extend([
        (addr >> 24) & 0xFF,
        (addr >> 16) & 0xFF,
        (addr >> 8) & 0xFF,
        addr & 0xFF
    ])
    return packet

def word_to_bytes(word):
    """Convert 32-bit word to bytes (little-endian)."""
    return [
        word & 0xFF,
        (word >> 8) & 0xFF,
        (word >> 16) & 0xFF,
        (word >> 24) & 0xFF
    ]

def bytes_to_word(byte_list):
    """Convert bytes to 32-bit word (little-endian)."""
    return (byte_list[0] | 
            (byte_list[1] << 8) | 
            (byte_list[2] << 16) | 
            (byte_list[3] << 24))

def test_gpio_leds(ser):
    """Test all LED patterns."""
    print("\n" + "="*60)
    print("LED TEST - Testing all 5 LEDs")
    print("="*60)
    print("\nNote: Watch the physical LEDs on your board!")
    print("(GPIO reads return BUTTON state, not LED state)")
    
    # Test individual LEDs
    led_tests = [
        (0b00001, "LED[1] only"),
        (0b00010, "LED[2] only"),
        (0b00100, "LED[3] only"),
        (0b01000, "LED[4] only"),
        (0b10000, "LED[5] only"),
        (0b11111, "All LEDs ON"),
        (0b00000, "All LEDs OFF"),
        (0b10101, "Alternating pattern 1"),
        (0b01010, "Alternating pattern 2"),
        (0b11110, "LED[5:2] ON"),
        (0b00111, "LED[3:1] ON"),
    ]
    
    for pattern, description in led_tests:
        print(f"\nSetting LEDs: 0b{pattern:05b} - {description}")
        print(f"  → Check if physical LEDs match this pattern!")
        data = word_to_bytes(pattern)
        cmd = create_write_command(GPIO_ADDRESS, data)
        
        ser.write(cmd)
        ser.flush()  # Ensure data is sent
        time.sleep(0.5)  # Longer delay to see the pattern
        
        # Clear any responses
        if ser.in_waiting > 0:
            ser.read(ser.in_waiting)
    
    print("\n✓ LED test complete - verify LEDs changed on hardware")
    print("  If LEDs didn't change, check your hardware connections")

def test_gpio_buttons(ser):
    """Test button reading."""
    print("\n" + "="*60)
    print("BUTTON TEST - Reading button states")
    print("="*60)
    print("\nReading GPIO continuously...")
    print("Press buttons on your board - changes will be displayed")
    print("(Press Ctrl+C to stop)")
    print("\nNote: Buttons are active-high, so pressed = 1")
    
    # Clear any pending data
    ser.reset_input_buffer()
    
    try:
        last_buttons = None
        read_count = 0
        
        while True:
            read_cmd = create_read_command(GPIO_ADDRESS, 4)
            ser.write(read_cmd)
            ser.flush()
            time.sleep(0.1)  # Wait for response
            
            if ser.in_waiting >= 4:
                response = list(ser.read(4))
                read_value = bytes_to_word(response)
                buttons = read_value & 0x0F
                
                # Always show first read and any changes
                if last_buttons is None or buttons != last_buttons:
                    timestamp = time.strftime("%H:%M:%S")
                    print(f"[{timestamp}] Buttons: 0b{buttons:04b} (0x{buttons:X}) = ", end="")
                    
                    if buttons == 0:
                        print("[No buttons pressed]")
                    else:
                        pressed = []
                        for i in range(4):
                            if buttons & (1 << i):
                                pressed.append(f"BTN{i}")
                        print(f"[{', '.join(pressed)}]")
                    
                    last_buttons = buttons
                
                read_count += 1
                if read_count % 20 == 0:
                    print(f"  ... {read_count} reads completed, still monitoring ...")
            else:
                print("⚠ Warning: No response from device")
            
            time.sleep(0.2)
            
    except KeyboardInterrupt:
        print(f"\n✓ Button test complete ({read_count} reads total)")
        if last_buttons == 0:
            print("⚠ Note: No button presses detected.")
            print("  Check: 1) Are buttons connected? 2) Button polarity correct?")

def test_memory(ser):
    """Test memory read/write functionality."""
    print("\n" + "="*60)
    print("MEMORY TEST - Testing 4KB memory")
    print("="*60)
    
    test_cases = [
        (0x00000000, 0xDEADBEEF, "First address"),
        (0x00000FFC, 0xCAFEBABE, "Last address"),
        (0x00000800, 0x12345678, "Middle address"),
        (0x00000004, 0xAAAAAAAA, "Second word"),
        (0x00000100, 0x55555555, "Page boundary"),
    ]
    
    all_passed = True
    
    for addr, test_data, description in test_cases:
        print(f"\nTesting {description} (0x{addr:08X}):")
        print(f"  Writing: 0x{test_data:08X}")
        
        # Write
        write_data = word_to_bytes(test_data)
        write_cmd = create_write_command(addr, write_data)
        ser.write(write_cmd)
        time.sleep(0.1)
        
        # Read back
        read_cmd = create_read_command(addr, 4)
        ser.write(read_cmd)
        time.sleep(0.1)
        
        if ser.in_waiting >= 4:
            response = list(ser.read(4))
            read_value = bytes_to_word(response)
            print(f"  Read:    0x{read_value:08X}")
            
            if read_value == test_data:
                print(f"  ✓ PASS")
            else:
                print(f"  ✗ FAIL - Data mismatch!")
                all_passed = False
        else:
            print(f"  ✗ FAIL - No response")
            all_passed = False
    
    # Pattern test - write and verify multiple locations
    print("\nPattern test - writing sequential data...")
    for i in range(0, 64, 4):
        addr = MEM_BASE + i
        data = 0x10000000 + i
        write_cmd = create_write_command(addr, word_to_bytes(data))
        ser.write(write_cmd)
        time.sleep(0.02)
    
    print("Verifying pattern...")
    mismatches = 0
    for i in range(0, 64, 4):
        addr = MEM_BASE + i
        expected = 0x10000000 + i
        read_cmd = create_read_command(addr, 4)
        ser.write(read_cmd)
        time.sleep(0.05)
        
        if ser.in_waiting >= 4:
            response = list(ser.read(4))
            read_value = bytes_to_word(response)
            if read_value != expected:
                print(f"  ✗ Mismatch at 0x{addr:08X}: expected 0x{expected:08X}, got 0x{read_value:08X}")
                mismatches += 1
                all_passed = False
    
    if mismatches == 0:
        print(f"  ✓ All 16 locations verified correctly")
    else:
        print(f"  ✗ {mismatches} locations had mismatches")
    
    if all_passed:
        print("\n✓ All memory tests PASSED")
    else:
        print("\n✗ Some memory tests FAILED")
    
    return all_passed

def interactive_mode(ser):
    """Interactive mode for manual testing."""
    print("\n" + "="*60)
    print("INTERACTIVE MODE")
    print("="*60)
    print("\nCommands:")
    print("  led <pattern>  - Set LED pattern (e.g., 'led 0b10101' or 'led 21')")
    print("  buttons        - Read button state once")
    print("  monitor        - Continuously monitor buttons (Ctrl+C to stop)")
    print("  write <addr> <data> - Write to memory (hex, e.g., 'write 0x100 0xDEAD')")
    print("  read <addr>    - Read from memory (hex)")
    print("  sweep          - LED sweep animation")
    print("  blink          - Blink all LEDs")
    print("  quit           - Exit")
    
    while True:
        try:
            cmd = input("\n> ").strip().lower()
            
            if cmd == "quit":
                break
            
            elif cmd.startswith("led "):
                pattern_str = cmd[4:].strip()
                if pattern_str.startswith("0b"):
                    pattern = int(pattern_str, 2)
                else:
                    pattern = int(pattern_str)
                
                pattern &= 0x1F
                print(f"Setting LEDs to 0b{pattern:05b}")
                write_cmd = create_write_command(GPIO_ADDRESS, word_to_bytes(pattern))
                ser.write(write_cmd)
                ser.flush()
                time.sleep(0.1)
            
            elif cmd == "buttons" or cmd == "read buttons":
                ser.reset_input_buffer()
                read_cmd = create_read_command(GPIO_ADDRESS, 4)
                ser.write(read_cmd)
                ser.flush()
                time.sleep(0.15)
                
                if ser.in_waiting >= 4:
                    response = list(ser.read(4))
                    value = bytes_to_word(response)
                    buttons = value & 0x0F
                    print(f"GPIO value: 0x{value:08X}")
                    print(f"  Buttons: 0b{buttons:04b} (", end="")
                    if buttons == 0:
                        print("none pressed)")
                    else:
                        pressed = [f"BTN{i}" for i in range(4) if buttons & (1<<i)]
                        print(f"{', '.join(pressed)} pressed)")
                else:
                    print(f"⚠ No response (bytes available: {ser.in_waiting})")
            
            elif cmd == "monitor":
                print("Monitoring buttons... (Ctrl+C to stop)")
                try:
                    last = None
                    while True:
                        ser.reset_input_buffer()
                        read_cmd = create_read_command(GPIO_ADDRESS, 4)
                        ser.write(read_cmd)
                        ser.flush()
                        time.sleep(0.15)
                        
                        if ser.in_waiting >= 4:
                            response = list(ser.read(4))
                            value = bytes_to_word(response)
                            buttons = value & 0x0F
                            if buttons != last:
                                print(f"0b{buttons:04b}", end=" ", flush=True)
                                last = buttons
                        time.sleep(0.1)
                except KeyboardInterrupt:
                    print("\nMonitoring stopped")
            
            elif cmd == "sweep":
                print("LED sweep animation...")
                for _ in range(3):
                    for i in range(5):
                        pattern = 1 << i
                        ser.write(create_write_command(GPIO_ADDRESS, word_to_bytes(pattern)))
                        ser.flush()
                        time.sleep(0.1)
                    for i in range(3, -1, -1):
                        pattern = 1 << i
                        ser.write(create_write_command(GPIO_ADDRESS, word_to_bytes(pattern)))
                        ser.flush()
                        time.sleep(0.1)
                ser.write(create_write_command(GPIO_ADDRESS, word_to_bytes(0)))
                ser.flush()
                print("Done")
            
            elif cmd == "blink":
                print("Blinking LEDs...")
                for _ in range(5):
                    ser.write(create_write_command(GPIO_ADDRESS, word_to_bytes(0x1F)))
                    ser.flush()
                    time.sleep(0.2)
                    ser.write(create_write_command(GPIO_ADDRESS, word_to_bytes(0x00)))
                    ser.flush()
                    time.sleep(0.2)
                print("Done")
            
            elif cmd.startswith("write "):
                parts = cmd.split()
                if len(parts) == 3:
                    addr = int(parts[1], 16)
                    data = int(parts[2], 16)
                    print(f"Writing 0x{data:08X} to 0x{addr:08X}")
                    write_cmd = create_write_command(addr, word_to_bytes(data))
                    ser.write(write_cmd)
                    ser.flush()
                    time.sleep(0.1)
                else:
                    print("Usage: write <addr> <data>")
            
            elif cmd.startswith("read "):
                parts = cmd.split()
                if len(parts) == 2:
                    addr = int(parts[1], 16)
                    ser.reset_input_buffer()
                    read_cmd = create_read_command(addr, 4)
                    ser.write(read_cmd)
                    ser.flush()
                    time.sleep(0.15)
                    
                    if ser.in_waiting >= 4:
                        response = list(ser.read(4))
                        value = bytes_to_word(response)
                        print(f"Read from 0x{addr:08X}: 0x{value:08X}")
                    else:
                        print(f"⚠ No response (bytes available: {ser.in_waiting})")
                else:
                    print("Usage: read <addr>")
            
            else:
                print("Unknown command. Type a command or 'quit' to exit.")
        
        except KeyboardInterrupt:
            print("\nExiting interactive mode")
            break
        except Exception as e:
            print(f"Error: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_uart_axi_hardware.py <serial_port>")
        print("Example: python test_uart_axi_hardware.py /dev/ttyUSB1")
        sys.exit(1)
    
    port = sys.argv[1]
    
    print("="*60)
    print("UART-AXI Hardware Test")
    print("="*60)
    print(f"Port: {port}")
    print(f"Baud: 115200")
    
    try:
        ser = serial.Serial(
            port=port,
            baudrate=115200,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1
        )
        
        print("✓ Serial port opened")
        time.sleep(0.5)
        
        # Clear any pending data
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.1)
        
        print("\n" + "="*60)
        print("TESTING BASIC COMMUNICATION")
        print("="*60)
        
        # Quick test - read memory address 0
        print("\nQuick test: Reading memory at 0x00000000...")
        read_cmd = create_read_command(0x00000000, 4)
        ser.write(read_cmd)
        ser.flush()
        time.sleep(0.2)
        
        if ser.in_waiting >= 4:
            response = list(ser.read(4))
            value = bytes_to_word(response)
            print(f"✓ Communication working! Read: 0x{value:08X}")
        else:
            print("✗ No response - check connections and baud rate")
            print(f"  Bytes available: {ser.in_waiting}")
            return
        
        # Run tests
        test_gpio_leds(ser)
        test_memory(ser)
        test_gpio_buttons(ser)
        interactive_mode(ser)
        
        ser.close()
        print("\n✓ All tests complete!")
        
    except serial.SerialException as e:
        print(f"✗ Serial port error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        if 'ser' in locals() and ser.is_open:
            ser.close()
        sys.exit(0)

if __name__ == "__main__":
    main()
