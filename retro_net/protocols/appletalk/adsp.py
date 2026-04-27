import enum
from construct import Struct, Int16ub, Int32ub, BitStruct, BitsInteger, Flag

# ADSP Control Codes (if control flag is 1)
class ADSPControlCode(enum.IntEnum):
    PROBE_OR_ACK = 0
    OPEN_CONN_REQ = 1
    OPEN_CONN_ACK = 2
    OPEN_CONN_REQ_ACK = 3
    OPEN_CONN_DENY = 4
    CLOSE_CONN = 5
    FORWARD_RESET = 6
    FORWARD_RESET_ACK = 7
    RETRANSMIT = 8

ADSPHeader = Struct(
    "src_conn_id" / Int16ub,
    "dest_conn_id" / Int16ub,
    "seq_num" / Int32ub,
    "ack_num" / Int32ub,
    "window_size" / Int16ub,
    "descriptor" / BitStruct(
        "control" / Flag,
        "ack_req" / Flag,
        "eom" / Flag,
        "attention" / Flag,
        "control_code" / BitsInteger(4)
    )
)

class ADSPState(enum.Enum):
    CLOSED = 0
    LISTENING = 1
    OPENING = 2
    OPEN = 3
    CLOSING = 4

class ADSPConnection:
    """
    State variables needed for an ADSP connection.
    """
    def __init__(self, local_conn_id: int):
        self.state = ADSPState.CLOSED

        # Connection IDs
        self.local_conn_id = local_conn_id
        self.remote_conn_id = 0

        # Sequence numbers and windows
        self.send_seq = 0
        self.recv_seq = 0
        self.send_window = 0
        self.recv_window = 4096  # Example default receive window size
