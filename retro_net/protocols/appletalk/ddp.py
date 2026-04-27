from construct import Struct, Int16ub, Int8ub, BitStruct, BitsInteger

# DDP (Datagram Delivery Protocol) Header
# Extended DDP Header is 13 bytes

DDPHeader = Struct(
    "flags_hop_length" / BitStruct(
        "reserved" / BitsInteger(2),
        "hop_count" / BitsInteger(4),
        "length" / BitsInteger(10)
    ),
    "checksum" / Int16ub,
    "dest_network" / Int16ub,
    "src_network" / Int16ub,
    "dest_node" / Int8ub,
    "src_node" / Int8ub,
    "dest_socket" / Int8ub,
    "src_socket" / Int8ub,
    "type" / Int8ub
)
