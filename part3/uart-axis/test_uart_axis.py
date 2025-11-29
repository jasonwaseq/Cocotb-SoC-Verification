import re
import git
import os
import sys
import subprocess
import git

# I don't like this, but it's convenient.
_REPO_ROOT = git.Repo(search_parent_directories=True).working_tree_dir
assert (os.path.exists(_REPO_ROOT)), "REPO_ROOT path must exist"
sys.path.append(os.path.join(_REPO_ROOT, "util"))
from utilities import runner, lint, assert_resolvable, clock_start_sequence, reset_sequence
tbpath = os.path.dirname(os.path.realpath(__file__))

import pytest

import cocotb

from cocotb.clock import Clock
from cocotb.regression import TestFactory
from cocotb.utils import get_sim_time
from cocotb.triggers import Timer, ClockCycles, RisingEdge, FallingEdge, with_timeout, First
from cocotb.types import LogicArray, Range

from cocotb_test.simulator import run

from cocotbext.axi import AxiLiteBus, AxiLiteMaster, AxiStreamSink, AxiStreamSource, AxiStreamBus
from cocotbext.uart import UartSource, UartSink

from pytest_utils.decorators import max_score, visibility, tags, leaderboard
   
import random
random.seed(42)

from functools import reduce

timescale = "1ps/1ps"

tests = ['reset_test'
         ,'simple_test'
         ,'birthday_led_test']

@pytest.mark.parametrize("example_p", [1]) # This is an example parameter.
@pytest.mark.parametrize("simulator", ["verilator", "icarus"])
def test_all(simulator, example_p):
    # This line must be first
    parameters = dict(locals())
    del parameters['simulator']
    runner(simulator, timescale, tbpath, parameters, pymodule="test_uart_axis")

@pytest.mark.parametrize("example_p", [1]) # This is an example parameter.
@pytest.mark.parametrize("test_name", tests)
@pytest.mark.parametrize("simulator", ["verilator", "icarus"])
def test_each(simulator, test_name, example_p):
    # This line must be first
    parameters = dict(locals())
    del parameters['test_name']
    del parameters['simulator']
    runner(simulator, timescale, tbpath, parameters, testname=test_name, pymodule="test_uart_axis")

@cocotb.test()
async def reset_test(dut):

    clk_i = dut.clk_i
    reset_i = dut.reset_i
    example_p = dut.example_p.value # Example

    # These are defined in utilities
    await clock_start_sequence(clk_i, 40) # 40 ns period is basically 25 MHz...
    await reset_sequence(clk_i, reset_i, 10)
    
@cocotb.test()
async def simple_test(dut):

    clk_i = dut.clk_i
    reset_i = dut.reset_i
    example_p = dut.example_p.value # Example

    print("\n" + "="*60)
    print("SIMPLE TEST STARTING")
    print("="*60)

    # This seems backwards, but remember that python is viewing inputs (_i) as "outputs" to drive.
    usrc = UartSource(dut.rx_serial_i, baud=115200, bits=8, stop_bits=1)
    usnk = UartSink(dut.tx_serial_o, baud=115200, bits=8, stop_bits=1)

    await clock_start_sequence(clk_i, 40) # 40 ns period is basically 25 MHz...
    await reset_sequence(clk_i, reset_i, 10)

    await FallingEdge(reset_i)

    print("Reset complete, starting test...")

    test_data = [0x00, 0x01, 0x02, 0x03]
    print(f"Sending: {test_data}")

    await usrc.write(test_data)
    print("Write queued")

    try:
        await with_timeout(usrc.wait(), 100, 'ms')
        print("UART write completed")
    except Exception as e:
        print(f"TIMEOUT on write: {e}")
        print("Check if module has loopback connections!")
        raise

    print("Waiting for data to propagate...")
    await ClockCycles(clk_i, 15000)  

    print("Reading response...")
    try:
        data = await with_timeout(usnk.read(count=4), 100, 'ms')
        print("Read completed")
    except Exception as e:
        print(f"TIMEOUT on read: {e}")
        print("Data was sent but not received back!")
        raise

    received = [int(d) for d in data]
    print(f"Received: {received}")
    
    if received == test_data:
        print("SUCCESS - Loopback working!")
    else:
        print(f"FAILURE - Expected {test_data}, got {received}")
        assert False, "Data mismatch"

    print("Hello CSE x25")
    print(received)

@cocotb.test()
async def birthday_led_test(dut):
    
    clk_i = dut.clk_i
    reset_i = dut.reset_i

    usrc = UartSource(dut.rx_serial_i, baud=115200, bits=8, stop_bits=1)
    usnk = UartSink(dut.tx_serial_o, baud=115200, bits=8, stop_bits=1)

    await clock_start_sequence(clk_i, 40)
    await reset_sequence(clk_i, reset_i, 10)
    await FallingEdge(reset_i)

    print("BIRTHDAY LED TEST")

    await ClockCycles(clk_i, 10)
    led_vec = int(dut.led_o.value)
    led_state = led_vec & 1  
    assert led_state == 0, f"LED should start OFF, got {led_state}"
    print("LED initially OFF")

    print("\nTest 1: Send BIRTHDAY (0x00B835F2) to turn LED ON")
   
    birthday_bytes = [0xF2, 0x35, 0xB8, 0x00]
    print(f"Sending (little-endian): {[hex(b) for b in birthday_bytes]}")
    print(f"Will form 32-bit word: 0x00B835F2")
    
    await usrc.write(birthday_bytes)
    await usrc.wait()
    print("Transmission complete")
    
    await ClockCycles(clk_i, 10000)
    
    led_vec = int(dut.led_o.value)
    led_state = led_vec & 1 
    print(f"LED state after birthday: {led_state}")
    assert led_state == 1, f"LED should be ON after birthday, got {led_state}"
    print("LED turned ON!")

    await ClockCycles(clk_i, 15000)
    data = await usnk.read(count=4)
    received = [int(b) for b in data]
    print(f"Loopback received: {[hex(b) for b in received]}")
    assert received == birthday_bytes, "Loopback verification failed"
    print("Loopback verified")

    print("\nTest 2: Send random data (0xDEADBEEF) - LED stays ON")
    random_bytes = [0xEF, 0xBE, 0xAD, 0xDE]
    print(f"Sending: {[hex(b) for b in random_bytes]}")
    
    await usrc.write(random_bytes)
    await usrc.wait()
    await ClockCycles(clk_i, 10000)
    
    led_vec = int(dut.led_o.value)
    led_state = led_vec & 1
    print(f"LED state after random data: {led_state}")
    assert led_state == 1, f"LED should still be ON, got {led_state}"
    print("LED correctly stayed ON")
    
    await ClockCycles(clk_i, 15000)
    await usnk.read(count=4)

    print("\nTest 3: Send OFF CODE (0xC0C0FFEE) to turn LED OFF")
    off_bytes = [0xEE, 0xFF, 0xC0, 0xC0]
    print(f"Sending: {[hex(b) for b in off_bytes]}")
    
    await usrc.write(off_bytes)
    await usrc.wait()
    await ClockCycles(clk_i, 10000)
    
    led_vec = int(dut.led_o.value)
    led_state = led_vec & 1
    print(f"LED state after off code: {led_state}")
    assert led_state == 0, f"LED should be OFF after off code, got {led_state}"
    print("LED turned OFF!")
    
    await ClockCycles(clk_i, 15000)
    data = await usnk.read(count=4)
    received = [int(b) for b in data]
    print(f"Loopback received: {[hex(b) for b in received]}")
    assert received == off_bytes, "Loopback verification failed"
    print("Loopback verified")

    print("\nTest 4: Send BIRTHDAY again to turn LED back ON")
    print(f"Sending: {[hex(b) for b in birthday_bytes]}")
    
    await usrc.write(birthday_bytes)
    await usrc.wait()
    await ClockCycles(clk_i, 10000)
    
    led_vec = int(dut.led_o.value)
    led_state = led_vec & 1
    print(f"LED state after second birthday: {led_state}")
    assert led_state == 1, f"LED should be ON again, got {led_state}"
    print("LED turned ON again!")
    
    await ClockCycles(clk_i, 15000)
    await usnk.read(count=4)

    print("\nTest 5: Verify other LEDs (2-5) remain OFF")
    led_vec = int(dut.led_o.value)
    for i in range(2, 6):
        led_val = (led_vec >> (i-1)) & 1
        assert led_val == 0, f"LED[{i}] should be OFF, got {led_val}"
    print("All other LEDs correctly OFF")

    print("ALL BIRTHDAY LED TESTS PASSED!")
    print("\nSummary:")
    print("LED turns ON when birthday (0x00B835F2) is received")
    print("LED stays ON with other data")
    print("LED turns OFF when off code (0xC0C0FFEE) is received")
    print("LED can be turned back ON")
    print("Loopback works correctly throughout")