from construct import Struct, Int8ub, Enum, Array, Byte, PascalString, BitStruct, BitsInteger, Int16ub

NBP_SOCKET = 2

NBPFunction = Enum(BitsInteger(4),
    BrRq=1, # Broadcast Request
    LkUp=2, # Lookup
    LkUpReply=3 # Lookup Reply
)

# NBP Tuple: network (2 bytes), node (1 byte), socket (1 byte), enumerator (1 byte), object (string), type (string), zone (string)
NBPTuple = Struct(
    "network" / Int16ub,
    "node" / Int8ub,
    "socket" / Int8ub,
    "enumerator" / Int8ub,
    "object_name" / PascalString(Byte, "utf8"),
    "type_name" / PascalString(Byte, "utf8"),
    "zone_name" / PascalString(Byte, "utf8")
)

# NBP Header: function/tuple_count (1 byte), nbp_id (1 byte)
NBPHeader = Struct(
    "flags" / BitStruct(
        "function" / NBPFunction,
        "tuple_count" / BitsInteger(4)
    ),
    "nbp_id" / Int8ub,
    "tuples" / Array(lambda this: this.flags.tuple_count, NBPTuple)
)
