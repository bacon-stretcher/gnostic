from construct import Struct, Int8ub, Int16ub, Bytes, Byte, Padding, Switch, Int32ub

# Constant definition for Network Layer Protocol Identifiers (NLPID)
NLPID_CLNP = 0x81
NLPID_ESIS = 0x82
NLPID_ISIS = 0x83
NLPID_TP4 = 0x84 # often not used this way, but we will define them

CLNPHeader = Struct(
    "nlpid" / Int8ub,             # Network Layer Protocol Identifier (0x81 for CLNP)
    "length_indicator" / Int8ub,  # Length of the header
    "version" / Int8ub,           # Version (typically 1)
    "ttl" / Int8ub,               # Time to Live
    "type_flags" / Int8ub,        # Type code and flags
    "segment_length" / Int16ub,   # Total length including header and data
    "checksum" / Int16ub,         # Header checksum
    "dest_address_length" / Int8ub,
    "dest_address" / Bytes(lambda ctx: ctx.dest_address_length),
    "src_address_length" / Int8ub,
    "src_address" / Bytes(lambda ctx: ctx.src_address_length),
    # Optional part
    # "data_unit_identifier" / Int16ub,
    # "segment_offset" / Int16ub,
    # "total_length" / Int16ub,
)
