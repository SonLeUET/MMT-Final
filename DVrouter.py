####################################################
# DVrouter.py
# Name:
# HUID:
#####################################################
import base64
import math
import pickle
from typing import Any, Optional # kiểu dữ liệu
from packet import Packet

from router import Router

_Addr = Any
_Port = Any
_Cost = int
 
# Constants
_INFINITY = math.inf

class _ForwardingTableEntry:
    def __init__(self, cost: _Cost, next_hop: Optional[_Addr] = None, port: Optional[_Port] = None):
        self.cost = cost
        self.maybe_next_hop = next_hop
        self.maybe_port = port
 
class _NeighborEntry:
    def __init__(self, cost: _Cost, port: _Port):
        self.cost = cost
        self.port = port
 
class _DistanceVectorEntry:
    def __init__(self, cost: _Cost, next_hop: _Addr):
        self.cost = cost
        self.next_hop = next_hop
 
 
def _serialize(obj: Any) -> str:
    bytes_ = pickle.dumps(obj) # tạo bytes tuần tự hóa cho obj
    str_ = base64.b64encode(bytes_).decode() # chuyển bytes thành ASCII-safe string
    return str_
 
 
def _deserialize(str_: str) -> Any:
    bytes_ = base64.b64decode(str_.encode()) # giải Base64 thành bytes
    obj = pickle.loads(bytes_) # phục hồi object gốc, là dict của _DistanceVectorEntry
    return obj

class DVrouter(Router):
    """Distance vector routing protocol implementation.

    Add your own class fields and initialization code (e.g. to create forwarding table
    data structures). See the `Router` base class for docstrings of the methods to
    override.
    """

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        # TODO
        #   add your own class fields and initialization code here
        pass

    def handle_packet(self, port: _Port, packet: Packet):
        if packet.is_traceroute:
            dst = packet.dst_addr
            entry = self.__forwarding_table.get(dst)
            if entry and entry.cost < _INFINITY and entry.maybe_port is not None:
                self.send(entry.maybe_port, packet)
        else:
            # Routing packet
            distance_vector: dict[_Addr, _DistanceVectorEntry] = _deserialize(packet.content)
            neighbor = packet.src_addr
 
            for addr, dv_entry in distance_vector.items():
                # If poison reverse indicates unreachable
                if dv_entry.cost == _INFINITY:
                    pass
                else:
                    # bellman ford
                    neigh_cost = self.__neighbors_by_addrs[neighbor].cost
                    new_cost = min(dv_entry.cost + neigh_cost, _INFINITY)
                    entry = self.__forwarding_table.get(addr)
                    if not entry or new_cost < entry.cost:
                        port_to_neighbor = self.__neighbors_by_addrs[neighbor].port
                        self.__forwarding_table[addr] = _ForwardingTableEntry(cost=new_cost, next_hop=neighbor, port=port_to_neighbor)

 


    def handle_new_link(self, port: _Port, endpoint: _Addr, cost: _Cost):
        # Add neighbor
        self.__neighbor_addrs_by_ports[port] = endpoint
        self.__neighbors_by_addrs[endpoint] = _NeighborEntry(cost=cost, port=port)
        # Initialize forwarding entry to neighbor
        entry = self.__forwarding_table.get(endpoint)
        if not entry or entry.cost != cost:
            self.__forwarding_table[endpoint] = _ForwardingTableEntry(cost=cost, next_hop=endpoint, port=port)
            self.__broadcast_to_neighbors()
 
    def handle_remove_link(self, port: _Port):
        neighbor = self.__neighbor_addrs_by_ports.pop(port)
        self.__neighbors_by_addrs.pop(neighbor, None)
        # Invalidate routes via this port
        for addr, entry in list(self.__forwarding_table.items()):
            if entry.maybe_port == port:
                self.__forwarding_table[addr] = _ForwardingTableEntry(cost=_INFINITY, next_hop=None, port=None)
        self.__broadcast_to_neighbors()

    def handle_time(self, time_ms):
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self.__broadcast_to_neighbors()
 
    def __repr__(self):
        return f"DVrouter(addr={self.addr}, table={{" + \
               ", ".join(f"{addr}:{entry.cost}" for addr, entry in self.__forwarding_table.items()) + "}})"
 
    def __broadcast_to_neighbors(self):
        for neighbor_addr, neighbor in self.__neighbors_by_addrs.items():
            # Poison reverse: if our next_hop for addr is this neighbor, advertise INFINITY
            dv: dict[_Addr, _DistanceVectorEntry] = {}
            for addr, entry in self.__forwarding_table.items():
                advertised_cost = _INFINITY if (entry.maybe_next_hop == neighbor_addr and addr != neighbor_addr) else entry.cost
                dv[addr] = _DistanceVectorEntry(cost=advertised_cost, next_hop=entry.maybe_next_hop)
            content = _serialize(dv)
            packet = Packet(Packet.ROUTING, self.addr, neighbor_addr, content)
            self.send(neighbor.port, packet)
