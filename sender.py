
from socket import *
import zlib
import os
import hashlib
import sys
import math
import random

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
ME = ("127.0.0.1", 4024)
TARGET = ("127.0.0.1", 4023)
'''

# Create socket
my_socket = socket(AF_INET, SOCK_DGRAM)
my_socket.bind(ME)

WINDOW_SIZE = 10  # amount of packages sent at a time
PACK_SIZE = 1024  # standard package size
SUCCESS = "SUCCESS ".encode()  # received on successfull data transfer 

#################################################

################ CRC-encoding ##################

def encode_to_crc(data):
    hash = 0
    hash = zlib.crc32(data, hash)
    return "%08X" % (hash & 0xFFFFFFFF)

#################################################

########## Function for sending data ############

def send_data(data, encoded = False, redo = False, md5 = False, info = ""):
    received = False
    if not redo:  # if the package is not being sent second time
        if encoded:  # if given data is already encoded
            crc_code = encode_to_crc(data)
            data = data + "#CRC-code#".encode() + crc_code.encode()
        else:  # if given data is not encoded yet
            crc_code = encode_to_crc(data.encode())
            data = data + "#CRC-code#" + crc_code
            if info:
                data = info + data
            data = data.encode()

    if md5:
        print(data)
    my_socket.sendto(data, TARGET)

    try:
        my_socket.settimeout(0.5)
        conf = my_socket.recvfrom(PACK_SIZE)
        if conf[0] != SUCCESS:
            raise timeout
    except timeout:
        print("Confirmation wasn't received, sending again")
        send_data(data, True, True)

def send_data_array(data_array):

    # Send all packages
    for data in data_array.values():
        malform_pack = random.randint(0, 100)
        if malform_pack < 10:
            my_socket.sendto(b"BROKEN_PACK#CRC_CODE#12345678", TARGET)
        else:
            my_socket.sendto(data, TARGET)

    ackn_array = []  # array containing received acknowledgements

    # Receive acknoledgements
    for i in range (0, len(data_array)):
        try:
            my_socket.settimeout(0.5)
            ackn = my_socket.recvfrom(PACK_SIZE)
        except timeout:
            print("Acknoledgement lost")
            continue
        
        try:
            ackn = ackn[0].decode("utf-8").split()
        except UnicodeDecodeError:
            print("Error in acknoledgement decode")
            continue
        if len(ackn) < 2:
            print("Acknoledgment is malformed")
            continue
        status = ackn[0]
        num = ackn[1]

        if (ackn[0] == "SUCCESS"):
            ackn_array.append(int(ackn[1]))
            print("Package", ackn[1], "received successfuly")
        else:
            pass
            print("Package", ackn[1], "damaged or lost")

    # Form an array of lost packages
    lost_data = {}
    for i in data_array.keys():
        if i not in ackn_array:
            lost_data[i] = data_array[i]

    # If some packages were lost, resend
    if len(lost_data) > 0:
        send_data_array(lost_data)

#################################################

################ Form packages ##################

def form_package(data, ind):
    crc_code = encode_to_crc(data)  # calculate crc-code
    
    temp = ind
    capacity = 5
    while temp > 0:  # how many 0 we need to add to get 5-digit number
        capacity -= 1
        temp //= 10
    
    ind = str(ind)
    for i in range (0, capacity):
        ind = "0" + ind

    data = ind.encode() + data + crc_code.encode()  # form package: index + data + crc_code
    return data

#################################################

################ File transfer ##################

# Set file name and send it to target
file_name = input("Print file name: ")
# file_name = "ebis_konem.gif"
send_data(file_name, info="file_name")

# Send file size to target
file_size = str(os.stat(file_name).st_size // PACK_SIZE + 1)
print("File size in packages:", file_size)
send_data(file_size, info="file_size")
file_size = int(file_size)

# Create MD5-checksum
md5 = hashlib.md5()  

# Send the file with selective repeat
file = open(file_name, "rb")
pack_counter = 0 # counter of packages sent

while pack_counter < file_size:
    data_array = {}

    # set current window size to standard window size if there's more packs left
    # else set current window size to amount of packs left
    cur_window = WINDOW_SIZE if file_size - pack_counter > WINDOW_SIZE else file_size - pack_counter

    for i in range(0, cur_window):
        data = file.read(PACK_SIZE)
        md5.update(data)  # increment MD5-checksum
        pack_counter += 1
        data = form_package(data, pack_counter)
        data_array[pack_counter] = data

    send_data_array(data_array)
    print("Frame sent!")

print("Sent", pack_counter, "packages.")
file.close()

#################################################

######### Send file MD5-checksum ################

received = False
while not received:
    md5_crc = "#CRC-CODE#" + encode_to_crc(md5.hexdigest().encode())
    sending_md5 = "file_hash" + md5.hexdigest() + md5_crc
    sending_md5 = sending_md5.encode()
    my_socket.sendto(sending_md5, TARGET)
    try:
        my_socket.settimeout(0.5)
        conf = my_socket.recvfrom(PACK_SIZE)
        if conf[0] == SUCCESS:
            print("Code sent successfully")
            break
        else:
            raise timeout
    except timeout:
        print("Sending again")
        continue
       
#################################################

my_socket.close()
