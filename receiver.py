
from socket import *
import hashlib
import zlib
import sys

################# CRC-encoding ##################

def encode_to_crc(data):
    hash = 0
    hash = zlib.crc32(data, hash)
    return "%08X" % (hash & 0xFFFFFFFF)

#################################################

####### Primary variables initialization ########

# Initializing sender's (this computer) address

MY_IP = input("Set your IP: ")
MY_PORT = int(input("Set your port: "))
ME = (MY_IP, MY_PORT)

# Initializing target's address
TARGET_IP = input("Set target IP: ")
TARGET_PORT = int(input("Set target port: "))
TARGET = (TARGET_IP, TARGET_PORT)

# Uncomment this for testing
'''
ME = ("127.0.0.1", 4023)
TARGET = ("127.0.0.1", 4024)
'''

# Create socket
my_socket = socket(AF_INET, SOCK_DGRAM)
my_socket.bind(ME)

STD_PACKSIZE = 2048  # standard package size
SUCCESS = "SUCCESS ".encode()  # sent on successfull data transfer
FAIL = "FAIL ".encode()  # sent on failed data transfer
last_pack = "init"  # last package received

# standard crc-code size
WINDOW_SIZE = 10
INDEX_SIZE = 5 
CRC_LEN = sys.getsizeof((encode_to_crc(b"GAY")).encode())

##################################################

############### Parse a package ##################

def parse_pack(pack, packsize):
    pack_num = pack[:INDEX_SIZE].decode("utf-8")
    try:
        pack_num = int(pack_num)
    except ValueError:
        print("Malformed pack!")
        return (None, None, None)
    data = pack[INDEX_SIZE:packsize-CRC_LEN]
    crc_code = pack[packsize-CRC_LEN:].decode("utf-8")
    crc_code = crc_code.replace("#CRC-code#", "")
    return (pack_num, data, crc_code)

##################################################

########## Function for receiving data ###########

def receive_data(info = False):
    global last_pack
    global received_packs

    if info:  # print info about receiving data if provided
        print("Receiving:", info)

    received = False
    while not received:
        receiving_file = not info

        try:
            if receiving_file:
                my_socket.settimeout(0.5)

            data = my_socket.recvfrom(STD_PACKSIZE)[0]
            packsize = sys.getsizeof(data)

            # Parse the package
            if receiving_file:
                num, data, crc_code = parse_pack(data, packsize)
            else:
                receiving = data[:9].decode("utf-8")
                if receiving != info:
                    print("Wrong package!")
                    data = None
                data = data[9:].decode("utf-8")
                data = data.split("#CRC-code#")
                print(data[0])
                crc_code = data[1]
                data = data[0].encode() 

            try:
                if data == None:
                    raise timeout
                if encode_to_crc(data) != crc_code:
                    print("CRC-test failed")
                    raise timeout
            except UnicodeDecodeError:
                print("UDE, CRC-test failed")
                raise timeout

            if data in received_packs or data == last_pack:  # if there was loss of acknowledgment
                print("Acknowledgment was lost")
                if receiving_file:
                    my_socket.sendto(SUCCESS + str(num).encode(), TARGET)
                else:
                    my_socket.sendto(SUCCESS, TARGET)
                continue
            else:
                if receiving_file:
                    my_socket.sendto(SUCCESS + str(num).encode(), TARGET)
                    received_packs[num] = data
                else:
                    my_socket.sendto(SUCCESS, TARGET)

                if info:
                    print("Received:", info)
                last_pack = data
                received = True
                return data
        
        except timeout:  # file wasn't received or was malformed
            if info:
                print(info, "wasn't received properly, trying again")
                my_socket.sendto(FAIL, TARGET)

##################################################

################# File transfer ##################

received_packs = {}

# Receive file name and send confirmation
file_name = receive_data("file_name")
file_name = file_name.decode("utf-8")
print("File name:", file_name.strip())

# Receive file size and send confirmation
pack_check = receive_data("file_size")
pack_check = int(pack_check.decode("utf-8"))
print("Should receive ", pack_check, "packages.")

# Create MD5 sumcheck
my_md5 = hashlib.md5()

# Receive the file
file = open(file_name.strip(), 'wb')
pack_counter = 0 # counter of packages received

data = receive_data()
while True:
    pack_counter += 1
    print("Received package", pack_counter)
    if pack_counter == pack_check:
        break
    data = receive_data()

for i in range(1, len(received_packs) + 1):
    my_md5.update(received_packs[i])
    file.write(received_packs[i])


if pack_counter == pack_check: # if received all packages
    print("All packages received successfully!")
print("File size:", pack_counter)
file.close()

##################################################

############## File MD-5 checksum ################

# Receive file MD5-checksum from sender
received = False
while not received:
    try:
        my_socket.settimeout(0.5)
        md5_check = my_socket.recvfrom(STD_PACKSIZE)[0]
        packsize = sys.getsizeof(md5_check)
        receiving = md5_check[:9]
        md5_crc = md5_check[packsize-CRC_LEN:].decode("utf-8")
        md5_check = md5_check[9:packsize-CRC_LEN]
        md5_check = md5_check.decode("utf-8").replace("#CRC-CODE#", "").encode()
        if receiving.decode("utf-8") == "file_hash" and \
                md5_crc == encode_to_crc(md5_check):
            my_socket.sendto(SUCCESS, TARGET)
        else:
            raise timeout
        received = True
    except timeout:
        print("Failed to receive, try once again.")
        my_socket.sendto(FAIL, TARGET)

# Compare received MD5-checksum and my checksum
if md5_check.decode("utf-8") == my_md5.hexdigest():
    print("MD5 encryption test passed!")
else:
    print("Should have received:\n", my_md5.hexdigest())
    print("Received:\n", md5_check.decode("utf-8"))

##################################################

my_socket.close()
