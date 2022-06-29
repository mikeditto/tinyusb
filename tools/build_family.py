import os
import glob
import sys
import subprocess
import time
from multiprocessing import Process

import build_utils

SUCCEEDED = "\033[32msucceeded\033[0m"
FAILED = "\033[31mfailed\033[0m"
SKIPPED = "\033[33mskipped\033[0m"

success_count = 0
fail_count = 0
skip_count = 0
exit_status = 0

total_time = time.monotonic()

build_format = '| {:29} | {:30} | {:18} | {:7} | {:6} | {:6} |'
build_separator = '-' * 106

def filter_with_input(mylist):
    if len(sys.argv) > 1:
        input_args = list(set(mylist).intersection(sys.argv))
        if len(input_args) > 0:
            mylist[:] = input_args

# If examples are not specified in arguments, build all
all_examples = []
for dir1 in os.scandir("examples"):
    if dir1.is_dir():
        for entry in os.scandir(dir1.path):
            if entry.is_dir():
                all_examples.append(dir1.name + '/' + entry.name)
filter_with_input(all_examples)
all_examples.sort()

# If family are not specified in arguments, build all
all_families = []
for entry in os.scandir("hw/bsp"):
    if entry.is_dir() and os.path.isdir(entry.path + "/boards") and entry.name not in ("esp32s2", "esp32s3"):
        all_families.append(entry.name)
            
filter_with_input(all_families)
all_families.sort()

def build_family(example, family):
    all_boards = []
    for entry in os.scandir("hw/bsp/{}/boards".format(family)):
        if entry.is_dir() and entry.name != 'pico_sdk':
            all_boards.append(entry.name)
    filter_with_input(all_boards)
    all_boards.sort()

    plist = []
    for board in all_boards:
        p = Process(target=build_board, args=(example, board))
        plist.append(p)
        p.start()

    for p in plist:
        p.join()
    
def build_board(example, board):
    global success_count, fail_count, skip_count, exit_status
    start_time = time.monotonic()
    flash_size = "-"
    sram_size = "-"

    # Check if board is skipped
    if build_utils.skip_example(example, board):
        success = SKIPPED
        skip_count += 1
        print(build_format.format(example, board, success, '-', flash_size, sram_size))
    else:   
        #subprocess.run("make -C examples/{} BOARD={} clean".format(example, board), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        build_result = subprocess.run("make -j -C examples/{} BOARD={} all".format(example, board), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        if build_result.returncode == 0:
            success = SUCCEEDED
            success_count += 1
            (flash_size, sram_size) = build_size(example, board)
            subprocess.run("make -j -C examples/{} BOARD={} copy-artifact".format(example, board), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        else:
            exit_status = build_result.returncode
            success = FAILED
            fail_count += 1

        build_duration = time.monotonic() - start_time
        print(build_format.format(example, board, success, "{:.2f}s".format(build_duration), flash_size, sram_size))

        if build_result.returncode != 0:
            print(build_result.stdout.decode("utf-8"))

def build_size(example, board):
    elf_file = 'examples/{}/_build/{}/*.elf'.format(example, board)
    size_output = subprocess.run('size {}'.format(elf_file), shell=True, stdout=subprocess.PIPE).stdout.decode("utf-8")
    size_list = size_output.split('\n')[1].split('\t')
    flash_size = int(size_list[0])
    sram_size = int(size_list[1]) + int(size_list[2])
    return (flash_size, sram_size)

if __name__ == '__main__':
    print(build_separator)
    print(build_format.format('Example', 'Board', '\033[39mResult\033[0m', 'Time', 'Flash', 'SRAM'))

    for example in all_examples:
        print(build_separator)
        for family in all_families:
            build_family(example, family)

    total_time = time.monotonic() - total_time
    print(build_separator)
    print("Build Summary: {} {}, {} {}, {} {} and took {:.2f}s".format(success_count, SUCCEEDED, fail_count, FAILED, skip_count, SKIPPED, total_time))
    print(build_separator)

    sys.exit(exit_status)
