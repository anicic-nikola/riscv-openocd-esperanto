import socket
import struct
import time
import ipdb
import binascii

HOST = 'localhost'
PORT = 5555

# Commands
READ_COMMAND = 0x00
WRITE_COMMAND = 0x01

# Response codes
RESPONSE_OK = 0x00
RESPONSE_ERROR = 0x01

      
# --- Simulated Register State ---
NUM_GPRS = 32  # 32 general-purpose registers in RISC-V

gprs = [0] * NUM_GPRS

dcsr = 0x40000003
dpc = 0x00000000



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
DMI_SBCS = 0x38 # System Bus Access Control and Status

DMI_DTMCS_OFFSET_DEBUG = 0x0000

# This needs to be changed, a temp hack to reply to the OpenOCD, probably some issue with 
# the kernel buffer, but it works somehow. Some clearing of the buffer is needed, or 
# better managing of the messages, either by size, or by some delimiter of the message.
DMI_TEST = 0x10040000

dmi_mem = {
    DMI_TEST: 0x0041,
    DMI_DTMCS_OFFSET_DEBUG: 0x0000, # 0x00000000 is the default value for all registers, 0x0000 is the address offset for the DTMCS register
    DMI_DMCONTROL: 0x0001,  # Initially, let's say the hart is running
    DMI_DMSTATUS: 0x0202,  # Indicate all harts are running, version 0.13 (version=2)
    DMI_HARTINFO: 0x0000,  # No hartsel, 1 data register
    DMI_ABSTRACTCS: 0x0000,  # No errors, no busy, 1 command register
    DMI_COMMAND: 0x0000,  # No command active
    DMI_ABSTRACTAUTO: 0x0000,  # No auto-increment
    DMI_DATA0: 0x0000,
    DMI_DATA1: 0x0000,
    DMI_PROGBUF0: 0x0000,
    DMI_SBCS: 0x0000,
}

# This is a hack to clear the kernel buffer
# It is necessary because the kernel buffer is not cleared by the socket
# and it can cause problems with the DMI protocol  in some cases, so better be safe
def clear_kernel_buffer(sock):
    sock.setblocking(False)
    
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
    except BlockingIOError:
        pass
    finally:
        sock.setblocking(True)


def handle_dmi_read(address, conn):
    """Handles DMI read requests."""
    # ipdb.set_trace()
    if address in dmi_mem:
        data = dmi_mem[address]
        print(f"DMI Read: Addr=0x{address:02X}, Data=0x{data:08X}")
        # ipdb.set_trace()
        if address == DMI_DTMCS_OFFSET_DEBUG:
            # clear_kernel_buffer(conn)
            data = 0x1331
            print(f"  DTMCS offset debug: Returning: 0x{data:08X}")

        elif address == DMI_DMCONTROL:
            data = 0x41  # Example: Set dmactive (bit 31) and dmireset (bit 0)
            print(f"  DTMCONTROL read! Returning: 0x{data:08X}")

        elif address == DMI_DMSTATUS:
            print(f"  DMI_DMSTATUS read! Current value: 0x{data:08X}")
            # Define field values
            version = 0x2             # version 0.13 (4 bits)
            confstrptrvalid = 0x0
            hasresethaltreq = 1
            authbusy = 0
            authenticated = 1
            anyhalted = 1
            allhalted = 0
            anyrunning = 0
            allrunning = 0
            anyunavail = 1
            allunavail = 0
            anynonexistent = 0
            allnonexistent = 1
            anyresumeack = 1
            allresumeack = 1
            anyhavereset = 0
            allhavereset = 0
            impebreak = 0x0

            # construct the 32-bit data value
            data = (version & 0x0f) | \
                ((confstrptrvalid & 0x01) << 4) | \
                ((hasresethaltreq & 0x01) << 5) | \
                ((authbusy & 0x01) << 6) | \
                ((authenticated & 0x01) << 7) | \
                ((anyhalted & 0x01) << 8) | \
                ((allhalted & 0x01) << 9) | \
                ((anyrunning & 0x01) << 10) | \
                ((allrunning & 0x01) << 11) | \
                ((anyunavail & 0x01) << 12) | \
                ((allunavail & 0x01) << 13) | \
                ((anynonexistent & 0x01) << 14) | \
                ((allnonexistent & 0x01) << 15) | \
                ((anyresumeack & 0x01) << 16) | \
                ((allresumeack & 0x01) << 17) | \
                ((anyhavereset & 0x01) << 18) | \
                ((allhavereset & 0x01) << 19) | \
                ((impebreak & 0x03) << 20) | \
                (0 << 31)  # bit 31 is fixed to 0

            print(f"  DMI_DMSTATUS read! Constructed value: 0x{data:08X}")
        # Pack the 32-bit data only once:
        response_data = struct.pack(">I", data) 
        # Construct the response by concatenating status and data:
        response = struct.pack(">B", RESPONSE_OK) + response_data
        time.sleep(0.1)
        print(f"Sending response: {response!r}")  # !r for printable representation
        print(f"Response in hex: {binascii.hexlify(response)}")
        conn.sendall(response)
        return data
    else:
        print(f"DMI Read: Addr=0x{address:02X} - Address not found!")
        return None

def handle_dmi_write(address, data):
    print(f"DMI Write: Addr=0x{address:02X}, Data=0x{data:08X}")
    # ipdb.set_trace()
    if address == DMI_DMCONTROL:
        print(f"  DMI_DMCONTROL write! Data: 0x{data:08X}")
        # Implement basic DMCONTROL handling (e.g., halt, resume)
        dmi_mem[DMI_DMCONTROL] = data # Write data here
        print(f"  DMI_DMSTATUS before modification: 0x{dmi_mem[DMI_DMSTATUS]:08X}")

        DMSTATUS_ALL_RUNNING_MASK = 0x3
        DMSTATUS_ALL_RESUMEACK_MASK = 0x3
        DMSTATUS_ALL_HAVERESET_MASK = 0x300
        DMSTATUS_ALL_RESUME_MASK = 0x300
        DMSTATUS_ALL_RESET_MASK = 0x400
        DMSTATUS_VERSION_MASK = 0x3
        DMSTATUS_VERSION_0_13 = 0x2

        if (data >> 31) & 1:
            print("Debug request set")
            # dmi_mem[DMI_DMSTATUS] = (dmi_mem[DMI_DMSTATUS] & ~0x3) | 0x2  # Set all running to 0 and all resumeack to 1
            dmi_mem[DMI_DMSTATUS] &= ~(DMSTATUS_ALL_RUNNING_MASK)
            dmi_mem[DMI_DMSTATUS] |= (DMSTATUS_ALL_RESUMEACK_MASK & 0x2)
        if (data >> 30) & 1:
            print("Halt request set")
            # dmi_mem[DMI_DMSTATUS] = (dmi_mem[DMI_DMSTATUS] & ~0x300) | 0x200  # Set all resume to 0 and all have been halted to 1
            dmi_mem[DMI_DMSTATUS] &= ~(DMSTATUS_ALL_RESUME_MASK)
            dmi_mem[DMI_DMSTATUS] |= (DMSTATUS_ALL_HAVERESET_MASK & 0x200)
        if (data >> 0) & 1:
            print("Hart reset request set")
            # dmi_mem[DMI_DMSTATUS] = (dmi_mem[DMI_DMSTATUS] & ~0x400) | 0x400  # Set all reset to 1
            dmi_mem[DMI_DMSTATUS] |= (DMSTATUS_ALL_RESET_MASK & 0x400)
        if (data >> 1) & 1:
            print("Acknowledge hart reset request set")
            # dmi_mem[DMI_DMSTATUS] = (dmi_mem[DMI_DMSTATUS] & ~0x400)  # Set all reset to 0
            dmi_mem[DMI_DMSTATUS] &= ~(DMSTATUS_ALL_RESET_MASK)

        # We need to always ensure the version field is correct:
        dmi_mem[DMI_DMSTATUS] &= ~DMSTATUS_VERSION_MASK  # Clear version bits
        dmi_mem[DMI_DMSTATUS] |= DMSTATUS_VERSION_0_13  # Set version to 0.13
    elif address == DMI_COMMAND:
        # Implement abstract command handling
        print(f"DMI_COMMAND 0x{DMI_COMMAND} address sets the data now to {data}.")
        dmi_mem[DMI_COMMAND] = data # Write data here
        cmderr = execute_abstract_command(data)
        dmi_mem[DMI_ABSTRACTCS] = (dmi_mem[DMI_ABSTRACTCS] & ~0x7) | cmderr

    else:
        # ipdb.set_trace()
        dmi_mem[address] = data  # Now data is the original value 
        
def execute_abstract_command(command):
    """Executes abstract commands (simplified for this example)."""
    global dcsr, dpc
    command_type = (command >> 24) & 0xFF
    print(f"Executing abstract command: 0x{command_type:02X}")
  
    # Access Register command as per 
    # https://riscv.org/wp-content/uploads/2024/12/riscv-debug-release.pdf, page 22, table 3.2
    if command_type == 0:    
        '''
        This command gives the debugger access to CPU registers and allows it to execute the Program
        Buffer. It performs the following sequence of operations:
            1. If write is clear and transfer is set, then copy data from the register specified by regno into the
            arg0 region of data, and perform any side effects that occur when this register is read from
            M-mode.
            2. If write is set and transfer is set, then copy data from the arg0 region of data into the register
            specified by regno, and perform any side effects that occur when this register is written from
            M-mode.
            3. If aarpostincrement is set, increment regno.
            4. Execute the Program Buffer, if postexec is set.
        '''
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
                    gprs[reg_num - 0x1000] = dmi_mem[DMI_DATA0]
                    print(f"  Writing 0x{dmi_mem[DMI_DATA0]:08X} to GPR {reg_num - 0x1000}")
                elif reg_num == 0x4:
                    dpc = dmi_mem[DMI_DATA0]
                    print(f"  Writing 0x{dmi_mem[DMI_DATA0]:08X} to DPC")
                elif reg_num == 0x7b0:
                    dcsr = dmi_mem[DMI_DATA0] & 0xFFFFFFFF
                    print(f"  Writing 0x{dcsr:08X} to DCSR")
                else:
                    print(f"  Write to register {reg_num} not implemented")
            else:
                # Read from register
                if reg_num >= 0x1000 and reg_num <= 0x101F:
                    data = gprs[reg_num - 0x1000]
                    print(f"  Reading GPR {reg_num - 0x1000}, returning 0x00000000")
                    dmi_mem[DMI_DATA0] = data
                elif reg_num == 0x4:
                    print(f"  Reading DPC, returning 0x00000000")
                    dmi_mem[DMI_DATA0] = dpc 
                elif reg_num == 0x7b0:
                    print(f"  Reading DCSR, returning 0x{dcsr:08X}")
                    dmi_mem[DMI_DATA0] = dcsr
                else:
                    print(f"  Read from register {reg_num} not implemented")
        return 0  # No error
    else:
        print(f"  Command type {command_type} not implemented")
        return 7  # Command not implemented

def main1():
    def handle_connection(conn):
        buffer = b""
        while True:
            # Read the length of the message (4 bytes for a 32-bit length)
            while len(buffer) < 4:
                data = conn.recv(1024)
                if not data:
                    return
                buffer += data

            message_length = struct.unpack(">I", buffer[:4])[0]
            buffer = buffer[4:]

            # Read the rest of the message
            while len(buffer) < message_length:
                data = conn.recv(1024)
                if not data:
                    return
                buffer += data

            # Process the complete message
            command, address, data_length = struct.unpack(">BIB", buffer[:6])

            if command == WRITE_COMMAND:
                if message_length == 10:
                    data = struct.unpack(">I", buffer[6:10])[0]
                    print(f"Write: Address={address:#010x}, Data={data:#010x}, Length={data_length}")
                    handle_dmi_write(address, data)
                    # Send a response (if needed)
                    response = struct.pack(">B", RESPONSE_OK) # Example: 0 for success
                    conn.sendall(struct.pack(">I", len(response)) + response)
                else:
                    print("Error: Incorrect message length for write operation")

            elif command == READ_COMMAND:
                if message_length == 6:
                    print(f"Read: Address={address:#010x}, Length={data_length}")
                    handle_dmi_read(address, conn)
                else:
                    print("Error: Incorrect message length for read operation")

            else:
                print(f"Unknown command: {command}")

            buffer = buffer[message_length:]

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server listening on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            with conn:
                print(f"Connected by {addr}")
                handle_connection(conn)


def main2():
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
                        # ipdb.set_trace()
                        data = conn.recv(1024)
                        if not data:
                            break
                        print(f"Received raw data: {data.hex()}")
                        buffer += data

                        while len(buffer) >= 6:
                            command, address, data_length = struct.unpack(">BIB", buffer[:6])
                            print(f"Unpacked received command: 0x{command:01X}")
                            print(f"Unpacked received address: 0x{address:04X}")
                            print(f"Unpacked received data_length: 0x{data_length:01X}")
                            if command == READ_COMMAND:
                                # ipdb.set_trace()
                                data = handle_dmi_read(address, conn)
                                print(f"Unpacked READ data is {data}")
                                print(f"READ COMMAND received, the whole buffer is: {buffer}")
                                buffer = buffer[6:]
                                print(f"READ COMMAND received, stripped buffer is: {buffer}")

                            elif command == WRITE_COMMAND:
                                if len(buffer) >= 10:
                                    # ipdb.set_trace()
                                    data = struct.unpack(">I", buffer[6:10])[0]
                                    print(f"Unpacked WRITE data is {data}")
                                    handle_dmi_write(address, data)
                                    conn.sendall(struct.pack(">BI", RESPONSE_OK, 0))
                                    print(f"WRITE COMMAND received, the whole buffer is: {buffer}")
                                    buffer = buffer[10:]
                                    print(f"WRITE COMMAND received, stripped buffer is: {buffer}")
                                else:
                                    break

                            else:
                                print (f"Received buffer with unknown command, the whole buffer is: {buffer}")
                                print(f"Invalid command: {command}")
                                conn.sendall(struct.pack(">BI", RESPONSE_ERROR, 0))
                                buffer = buffer[6:]
                        if not buffer:
                            # If buffer is empty, receive at least 6 bytes
                            print("**** Buffer is empty, receiving 6 bytes now.")
                            received_data = conn.recv(6)
                        else:
                            # If buffer has some data, check for and remove stray '@'
                            if buffer == b'@':
                                print("Removing stray '@' from buffer")
                                buffer = b''  # Clear the buffer
                            # Receive at least 1 byte to make progress
                            received_data = conn.recv(1)

                        if not received_data:
                            break  # Connection closed

                        # buffer = b''
                        # buffer += received_data
                        print("Appending the new received data to the buffer ****")
                        buffer = received_data

                    except ConnectionResetError:
                        print("Client disconnected")
                        break
                buffer = b''

main2()

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