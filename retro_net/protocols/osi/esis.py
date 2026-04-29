from construct import Struct, Int8ub, Int16ub, Bytes, GreedyBytes

ESISHeader = Struct(
    "nlpid" / Int8ub,             # Network Layer Protocol Identifier (0x82 for ES-IS)
    "length_indicator" / Int8ub,  # Header length
    "version" / Int8ub,           # Version
    "id_length" / Int8ub,         # System ID length
    "type" / Int8ub,              # PDU type (e.g., ESH, ISH)
    "holding_time" / Int16ub,     # Holding time
    "checksum" / Int16ub,         # Checksum
    "source_address_length" / Int8ub,
    "source_address" / Bytes(lambda ctx: ctx.source_address_length),
    "options" / Bytes(lambda ctx: ctx.length_indicator - (9 + ctx.source_address_length) if ctx.length_indicator > (9 + ctx.source_address_length) else 0)
)
