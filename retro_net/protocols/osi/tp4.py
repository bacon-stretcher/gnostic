from construct import Struct, Int8ub, Int16ub, Bytes, Enum, GreedyBytes

# Constant definition for TP4 Protocol classes
TP4_CLASS = 4

TP4Header = Struct(
    "length_indicator" / Int8ub,
    "pdu_type" / Int8ub,     # e.g., CR, CC, DR, DC, DT
    "dst_ref" / Int16ub,     # Destination Reference
    "src_ref" / Int16ub,     # Source Reference (only for some PDUs, but simplifying for now)
    "class_option" / Int8ub, # Class and options
    "variable_part" / Bytes(lambda ctx: ctx.length_indicator - 6 if ctx.length_indicator >= 6 else 0)
)
