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

from cocotbext.axi import AxiLiteBus, AxiLiteMaster, AxiStreamSink, AxiStreamMonitor, AxiStreamBus
from cocotbext.uart import UartSource, UartSink

from pytest_utils.decorators import max_score, visibility, tags, leaderboard
   
import random
random.seed(42)

from functools import reduce

timescale = "1ps/1ps"

tests = ['reset_test'
         ,'simple_test']

@pytest.mark.parametrize("example_p", [1])
@pytest.mark.parametrize("simulator", ["verilator", "icarus"])
@max_score(0)
def test_all(simulator, example_p):
    parameters = dict(locals())
    del parameters['simulator']
    runner(simulator, timescale, tbpath, parameters, pymodule="test_uart_axi")

@pytest.mark.parametrize("example_p", [1])
@pytest.mark.parametrize("test_name", tests)
@pytest.mark.parametrize("simulator", ["verilator", "icarus"])
@max_score(0)
def test_each(simulator, test_name, example_p):
    parameters = dict(locals())
    del parameters['test_name']
    del parameters['simulator']
    runner(simulator, timescale, tbpath, parameters, testname=test_name, pymodule="test_uart_axi")

def create_write_command(addr, data_bytes):
    
    packet = []
    packet.append(0x10)  
    packet.append(len(data_bytes))  
    
    packet.append((addr >> 24) & 0xFF)
    packet.append((addr >> 16) & 0xFF)
    packet.append((addr >> 8) & 0xFF)
    packet.append(addr & 0xFF)
    
    packet.extend(data_bytes)
    
    return packet

def create_read_command(addr, num_bytes):
    
    packet = []
    packet.append(0x11)  
    packet.append(num_bytes) 
    
    packet.append((addr >> 24) & 0xFF)
    packet.append((addr >> 16) & 0xFF)
    packet.append((addr >> 8) & 0xFF)
    packet.append(addr & 0xFF)
    
    return packet

def word_to_bytes(word):
    """Convert 32-bit word to list of bytes (little-endian)."""
    return [
        word & 0xFF,
        (word >> 8) & 0xFF,
        (word >> 16) & 0xFF,
        (word >> 24) & 0xFF
    ]

def bytes_to_word(byte_list):
    """Convert list of bytes to 32-bit word (little-endian)."""
    return (byte_list[0] | 
            (byte_list[1] << 8) | 
            (byte_list[2] << 16) | 
            (byte_list[3] << 24))

@cocotb.test()
async def reset_test(dut):
    clk_i = dut.clk_i
    reset_i = dut.reset_i

    await clock_start_sequence(clk_i, 83334, 'ps') # 12 MHz
    await reset_sequence(clk_i, reset_i, 10)
    
    dut._log.info("Reset test completed successfully")
    await ClockCycles(clk_i, 100)
    
@cocotb.test()
async def simple_test(dut):
    clk_i = dut.clk_i
    reset_i = dut.reset_i
    buttons_i = dut.buttons_i
    led_o = dut.led_o

    dut._log.info("=== UART-AXI System Test ===")
    dut._log.info("Setting up UART interfaces...")
    
    src = UartSource(dut.rx_serial_i, baud=115200, bits=8, stop_bits=1)
    snk = UartSink(dut.tx_serial_o, baud=115200, bits=8, stop_bits=1)

    dut._log.info("Starting clock (12 MHz) and reset...")
    await clock_start_sequence(clk_i, 83334, 'ps') 
    await reset_sequence(clk_i, reset_i, 10)
    await FallingEdge(reset_i)
    
    dut._log.info("Waiting for system stabilization...")
    await ClockCycles(clk_i, 500)

    dut._log.info("\nTEST 1: GPIO READ (Buttons)")
    buttons_i.value = 0b0101
    await ClockCycles(clk_i, 10)
    
    gpio_addr = 0xF0000000
    read_cmd = create_read_command(gpio_addr, 4)
    
    dut._log.info(f"Sending read command: {[hex(b) for b in read_cmd]}")
    await src.write(read_cmd)
    await src.wait()
    dut._log.info("Command sent, waiting for full processing and transmission...")
    
    await Timer(1, 'ms')
    
    try:
        read_data = await with_timeout(snk.read(count=4), 1, 'ms')
        read_value = bytes_to_word(read_data)
        dut._log.info(f"Received: 0x{read_value:08X}, buttons={read_value&0xF:04b}")
        assert (read_value & 0xF) == 0b0101, f"Button mismatch!"
        dut._log.info("GPIO READ test PASSED")
    except Exception as e:
        dut._log.error(f"GPIO READ test FAILED: {e}")
        try:
            state = int(dut.u_dbg_bridge.state_q.value)
            dut._log.error(f"Debug bridge state: {state}")
        except:
            pass
        raise

    dut._log.info("\nTEST 2: GPIO WRITE (LEDs)")
    led_pattern = 0b11010
    write_data = word_to_bytes(led_pattern)
    write_cmd = create_write_command(gpio_addr, write_data)
    
    dut._log.info(f"Writing LED pattern: 0b{led_pattern:05b}")
    await src.write(write_cmd)
    await src.wait()
    await Timer(500, 'us')  
    
    led_value = int(led_o.value)
    dut._log.info(f"LED output: 0b{led_value:05b}")
    assert led_value == led_pattern, f"LED mismatch!"
    dut._log.info("GPIO WRITE test PASSED")

    dut._log.info("\nTEST 3: Memory Write (0x00000000)")
    mem_addr = 0x00000000
    test_data = 0xDEADBEEF
    write_data = word_to_bytes(test_data)
    write_cmd = create_write_command(mem_addr, write_data)
    
    dut._log.info(f"Writing 0x{test_data:08X} to 0x{mem_addr:08X}")
    await src.write(write_cmd)
    await src.wait()
    await Timer(500, 'us')  
    dut._log.info("Memory WRITE complete")

    dut._log.info("\nTEST 4: Memory Read (0x00000000)")
    read_cmd = create_read_command(mem_addr, 4)
    await src.write(read_cmd)
    await src.wait()
    await Timer(1, 'ms') 
    
    try:
        read_data = await with_timeout(snk.read(count=4), 1, 'ms')
        read_value = bytes_to_word(read_data)
        dut._log.info(f"Read: 0x{read_value:08X}")
        assert read_value == test_data, f"Memory mismatch!"
        dut._log.info("Memory READ test PASSED")
    except Exception as e:
        dut._log.error(f"Memory READ test FAILED: {e}")
        raise

    dut._log.info("\nTEST 5: Last Memory Address (0x00000FFC)")
    mem_addr = 0x00000FFC
    test_data = 0xCAFEBABE
    write_data = word_to_bytes(test_data)
    write_cmd = create_write_command(mem_addr, write_data)
    
    await src.write(write_cmd)
    await src.wait()
    await Timer(500, 'us') 
    
    read_cmd = create_read_command(mem_addr, 4)
    await src.write(read_cmd)
    await src.wait()
    await Timer(1, 'ms')  
    
    try:
        read_data = await with_timeout(snk.read(count=4), 1, 'ms')
        read_value = bytes_to_word(read_data)
        dut._log.info(f"Read: 0x{read_value:08X}")
        assert read_value == test_data, f"Last address mismatch!"
        dut._log.info("Last address test PASSED")
    except Exception as e:
        dut._log.error(f"Last address test FAILED: {e}")
        raise

    dut._log.info("ALL TESTS PASSED!")
