from construct import Struct, Int8ub, Int16ub, Bytes, GreedyBytes

ISISHeader = Struct(
    "nlpid" / Int8ub,             # Network Layer Protocol Identifier (0x83 for IS-IS)
    "length_indicator" / Int8ub,  # Header length
    "version" / Int8ub,           # Version/Protocol ID Extension
    "id_length" / Int8ub,         # System ID length
    "pdu_type" / Int8ub,          # PDU Type
    "version2" / Int8ub,          # Version
    "reserved" / Int8ub,          # Reserved
    "max_area_addresses" / Int8ub,# Maximum Area Addresses
    # Common header ends here, specific PDU follows (e.g., Hello, LSP, CSNP, PSNP)
    # We will use variable bytes to catch the rest of the header for now
    "variable_part" / Bytes(lambda ctx: ctx.length_indicator - 8 if ctx.length_indicator >= 8 else 0)
)
