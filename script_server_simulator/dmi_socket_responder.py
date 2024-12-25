import socket
import struct
import time
import ipdb

HOST = 'localhost'
PORT = 5555

# Commands
READ_COMMAND = 0x00
WRITE_COMMAND = 0x01

# Response codes
RESPONSE_OK = 0x00
RESPONSE_ERROR = 0x01

# --- DMI Registers (RISC-V Debug Spec 0.13) ---
# These are the essential registers for basic functionality
DMI_DMCONTROL = 0x10  # Debug Module Control
DMI_DMSTATUS = 0x11  # Debug Module Status
DMI_HARTINFO = 0x12  # Hart Information
DMI_ABSTRACTCS = 0x16  # Abstract Control and Status
DMI_COMMAND = 0x17  # Abstract Command
DMI_ABSTRACTAUTO = 0x18  # Abstract Autoincrement
DMI_DATA0 = 0x04  # Data register 0 (for abstract commands)
DMI_DATA1 = 0x05  # Data register 1 (for abstract commands)
DMI_PROGBUF0 = 0x20  # Program Buffer 0 (for program buffer access)

dmi_mem = {
    DMI_DMCONTROL: 0x00000001,  # Initially, let's say the hart is running
    DMI_DMSTATUS: 0x00000201,  # Indicate all harts are running, version 0.13
    DMI_HARTINFO: 0x00000000,  # No hartsel, 1 data register
    DMI_ABSTRACTCS: 0x00000000,  # No errors, no busy, 1 command register
    DMI_COMMAND: 0x00000000,  # No command active
    DMI_ABSTRACTAUTO: 0x00000000,  # No auto-increment
    DMI_DATA0: 0x00000000,
    DMI_DATA1: 0x00000000,
    DMI_PROGBUF0: 0x00000000,
}

def handle_dmi_read(address, conn):
    """Handles DMI read requests."""
    if address in dmi_mem:
        data = dmi_mem[address]
        print(f"DMI Read: Addr=0x{address:02X}, Data=0x{data:08X}")
        ipdb.set_trace()
        if address == DMI_DMCONTROL:
            print(f"  DTMCONTROL read! Returning: 0x{data:08X}")
            data = 0x41  # Example: Set dmactive (bit 31) and dmireset (bit 0)
        # Pack the 32-bit data only once:
        response_data = struct.pack(">I", data) 
        # Construct the response by concatenating status and data:
        response = struct.pack(">B", RESPONSE_OK) + response_data
        time.sleep(0.1)
        print(f"Sending response: {response!r}")  # !r for printable representation
        conn.sendall(response)
        return data
    else:
        print(f"DMI Read: Addr=0x{address:02X} - Address not found!")
        return None

def handle_dmi_write(address, data):
    print(f"DMI Write: Addr=0x{address:02X}, Data=0x{data:08X}")
    ipdb.set_trace()
    if address == DMI_DMCONTROL:
        # Implement basic DMCONTROL handling (e.g., halt, resume)
        dmi_mem[DMI_DMCONTROL] = data # Write data here
        if (data >> 31) & 1:
            print("Debug request set")
            dmi_mem[DMI_DMSTATUS] = (dmi_mem[DMI_DMSTATUS] & ~0x3) | 0x2  # Set all running to 0 and all resumeack to 1
        if (data >> 30) & 1:
            print("Halt request set")
            dmi_mem[DMI_DMSTATUS] = (dmi_mem[DMI_DMSTATUS] & ~0x300) | 0x200  # Set all resume to 0 and all have been halted to 1
        if (data >> 0) & 1:
            print("Hart reset request set")
            dmi_mem[DMI_DMSTATUS] = (dmi_mem[DMI_DMSTATUS] & ~0x400) | 0x400  # Set all reset to 1
        if (data >> 1) & 1:
            print("Acknowledge hart reset request set")
            dmi_mem[DMI_DMSTATUS] = (dmi_mem[DMI_DMSTATUS] & ~0x400)  # Set all reset to 0
    elif address == DMI_COMMAND:
        # Implement abstract command handling
        dmi_mem[DMI_COMMAND] = data # Write data here
        cmderr = execute_abstract_command(data)
        dmi_mem[DMI_ABSTRACTCS] = (dmi_mem[DMI_ABSTRACTCS] & ~0x7) | cmderr
    else:
        ipdb.set_trace()
        dmi_mem[address] = data  # Now data is the original value 
        
def execute_abstract_command(command):
    """Executes abstract commands (simplified for this example)."""
    command_type = (command >> 24) & 0xFF
    print(f"Executing abstract command: 0x{command_type:02X}")

    if command_type == 0:  # Access Register
        # Extract parameters
        reg_num = (command >> 0) & 0xFFFF
        aarsize = (command >> 16) & 0x7
        write = (command >> 23) & 0x1
        transfer = (command >> 20) & 0x1
        postexec = (command >> 19) & 0x1

        print(f"  Register: 0x{reg_num:04X}, aarsize: {aarsize}, write: {write}, transfer: {transfer}, postexec: {postexec}")

        if transfer:
            if write:
                # Write to register
                if reg_num >= 0x1000 and reg_num <= 0x101F:
                    print(f"  Writing 0x{dmi_mem[DMI_DATA0]:08X} to GPR {reg_num - 0x1000}")
                elif reg_num == 0x4:
                    print(f"  Writing 0x{dmi_mem[DMI_DATA0]:08X} to DPC")
                else:
                    print(f"  Write to register {reg_num} not implemented")
            else:
                # Read from register
                if reg_num >= 0x1000 and reg_num <= 0x101F:
                    print(f"  Reading GPR {reg_num - 0x1000}, returning 0x00000000")
                    dmi_mem[DMI_DATA0] = 0x00000000
                elif reg_num == 0x4:
                    print(f"  Reading DPC, returning 0x00000000")
                    dmi_mem[DMI_DATA0] = 0x00000000
                else:
                    print(f"  Read from register {reg_num} not implemented")
        return 0  # No error
    else:
        print(f"  Command type {command_type} not implemented")
        return 7  # Command not implemented

# --- Main Server Loop ---
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    print(f"Server listening on {HOST}:{PORT}")
    while True:
        conn, addr = s.accept()
        with conn:
            print(f"Connected by {addr}")
            buffer = b''
            while True:
                try:
                    data = conn.recv(1024)
                    if not data:
                        break
                    print(f"Received raw data: {data.hex()}")
                    buffer += data

                    while len(buffer) >= 6:
                        command, address, data_length = struct.unpack(">BIB", buffer[:6])
                        print(f"Unpacked received address: 0x{address:08X}")

                        if command == READ_COMMAND:
                            data = handle_dmi_read(address, conn)
                            buffer = buffer[6:]

                        elif command == WRITE_COMMAND:
                            if len(buffer) >= 10:
                                ipdb.set_trace()
                                data = struct.unpack(">I", buffer[6:10])[0]
                                handle_dmi_write(address, data)
                                conn.sendall(struct.pack(">BI", RESPONSE_OK, 0))
                                buffer = buffer[10:]
                            else:
                                break  # Not enough data yet

                        else:
                            print(f"Invalid command: {command}")
                            conn.sendall(struct.pack(">BI", RESPONSE_ERROR, 0))
                            buffer = buffer[6:]
                except ConnectionResetError:
                    print("Client disconnected")
                    break

# This works somehow
# =============================================================================================

# import socket
# import struct
# import time

# HOST = 'localhost'
# PORT = 5555

# with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#     s.bind((HOST, PORT))
#     s.listen()
#     print(f"Server listening on {HOST}:{PORT}")
#     while True:
#         conn, addr = s.accept()
#         with conn:
#             print(f"Connected by {addr}")
#             while True:
#                 data = conn.recv(1024)
#                 if not data:
#                     break
#                 print(f"Received raw data: {data.hex()}")

#                 # Hardcoded dtmcontrol read request handling
#                 if data.startswith(b'\x00\x04\x00\x00\x00\x00'):
#                     print("DTMCONTROL read request detected!")
#                     # Valid dtmcontrol value with version 0:
#                     dtmcontrol_value = 0x00000001
#                     response_data = struct.pack(">I", dtmcontrol_value)
#                     response = struct.pack(">B", 0) + response_data  # Status OK (0)
#                     time.sleep(0.001)  # Introduce a delay
#                     conn.sendall(response)
#                     print(f"Sent response: {response.hex()}")