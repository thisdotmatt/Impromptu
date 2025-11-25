import json
from typing import Tuple
from collections import defaultdict, deque
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from ltspice import Ltspice
import ast
import re
import time
import base64
from io import BytesIO
import requests

def formatSSEMessage(event) -> str:
    return f"data: {json.dumps(event)}\n\n"


async def checkTracesUnderMaxCurrent(
    spiceObj: Ltspice, max_current: float = 3.0
) -> Tuple[bool, str | None, float | None]:
    # good way to determine whether a given netlist has a short circuit
    # returns a list of:
    # 1. Boolean of whether there was a violating trace
    # 2. the problem trace identifier (e.g. I(n001))
    # 3. the violating current
    for trace in spiceObj.variables:
        if trace.startswith("I"):  # is current
            current_elem = spiceObj.get_data(name=trace)
            max_curr = abs(current_elem.max())
            if max_curr > max_current:
                return (False, trace, max_curr)
    return (True, None, None)


async def checkTracesUnderMaxVoltage(
    spiceObj: Ltspice, max_voltage: float = 20.0
) -> Tuple[bool, str | None, float | None]:
    # good way to determine whether a given netlist has exceeded the voltage specified by the system
    # returns a list of:
    # 1. Boolean of whether there was a violating trace
    # 2. the problem trace identifier (e.g. V(n001))
    # 3. the violating voltage
    for trace in spiceObj.variables:
        if trace.startswith("V"):  # is current
            current_elem = spiceObj.get_data(name=trace)
            max_vol = abs(current_elem.max())
            if max_vol > max_voltage:
                return (False, trace, max_vol)
    return (True, None, None)

async def validateNetlist(spiceObj):
    results = {
        "short_ok": True,
        "voltage_ok": True,
        "problems": []
    }

    short_check, problem_trace, problem_current = await checkTracesUnderMaxCurrent(spiceObj=spiceObj)
    if not short_check:
        results["short_ok"] = False
        results["problems"].append(
            f"Short circuit detected on {problem_trace} with current {problem_current}"
        )

    voltage_check, problem_trace, problem_voltage = await checkTracesUnderMaxVoltage(spiceObj=spiceObj)
    if not voltage_check:
        results["voltage_ok"] = False
        results["problems"].append(
            f"High voltage detected on {problem_trace}: {problem_voltage}V"
        )

    return results

class Dbg:
    """
    Simple debugging helper. Wrap all debug prints through this so you can turn
    them on/off globally. When enabled, logs to a file instead of stdout.
    """
    def __init__(self, on: bool = False, logfile: str = "pnr_debug.log"):
        self.on = on
        self.step = 0
        self.logfile = logfile
        self._fh = open(self.logfile, "w") if self.on else None

    def _write(self, msg: str):
        if not self.on:
            return
        if self._fh is not None:
            self._fh.write(msg + "\n")
            self._fh.flush()

    def p(self, *args):
        """Conditional debug print to the log file."""
        if self.on:
            self._write(" ".join(str(a) for a in args))

    def tick(self, msg: str = ""):
        """Increment an internal step counter and log a message."""
        self.step += 1
        if self.on:
            self._write(f"[{self.step}] {msg}")

class UF:
    """
    Union-Find (Disjoint Set) structure used to track which holes are
    electrically connected together.
    """
    def __init__(self):
        self.parent = {}
        self.rank = {}

    def add(self, x):
        """Ensure x is present in the structure as its own set."""
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0

    def find(self, x):
        """Find the representative for x with path compression."""
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        """Union the sets containing a and b by rank."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            self.parent[ra] = rb
        elif self.rank[ra] > self.rank[rb]:
            self.parent[rb] = ra
        else:
            self.parent[rb] = ra
            self.rank[ra] += 1


class Breadboard:
    """
    Geometric and electrical model of a breadboard.

    - The central area consists of two 5-hole strips per row, separated by a trough.
    - On each side there are vertical power rails: V+ and GND.
    - Some columns are "gaps" with no holes (just visual spacing).
    """
    def __init__(self, rows=40, wire_lengths=(1, 3, 5)):
        self.rows = rows

        # Main board geometry
        self.cols_left = 5
        self.cols_right = 5
        self.trough_cols = (5, 6)
        self.total_cols = self.cols_left + 2 + self.cols_right

        # Allowed wire jumper lengths (in hole-to-hole distance)
        self.wire_lengths = sorted(set(wire_lengths))

        # Geometry containers
        self.holes = set()         # All board holes (excluding rails)
        self.rails_v = set()       # All V+ rail holes
        self.rails_g = set()       # All GND rail holes

        # Mapping from hole -> its 5-hole strip (for the main board)
        self.strip_of_hole = {}
        # Mapping from rail hole -> 'V+' or 'GND'
        self.rail_of_hole = {}

        # Occupancy: hole -> (type, id)
        #   type: 'empty', 'comp_body', 'comp_pin', 'wire_end', 'wire_body'
        #   id:   component name or wire segment id
        self.occ = {}

        # Disjoint-set structure to track connectivity
        self.uf = UF()

        # Realistic rails: left and right vertical rails, each separated
        # from the board by a 2-hole gap (no actual holes there).
        self.left_rail_cols = (-4, -3)   # V+ (col -4), GND (col -3) on far left
        self.left_gap_cols = (-2, -1)    # 2 empty columns before main board
        self.right_gap_cols = (self.total_cols, self.total_cols + 1)
        self.right_rail_cols = (self.total_cols + 2, self.total_cols + 3)

        self._build_geometry()
        self._init_uf()

    # --------------------------------------------------------------------- #
    # Geometry construction
    # --------------------------------------------------------------------- #
    def _build_geometry(self):
        """Construct the fixed geometry of the board: holes, rails, strips."""
        self.holes.clear()
        self.rails_v.clear()
        self.rails_g.clear()
        self.strip_of_hole.clear()
        self.rail_of_hole.clear()
        self.occ.clear()

        # Main board holes (exclude trough columns)
        for r in range(self.rows):
            for c in range(self.total_cols):
                if c in self.trough_cols:
                    continue
                self.holes.add((r, c))

        # Add left rails (vertical): V+ then GND
        for r in range(self.rows):
            self.rails_v.add((r, self.left_rail_cols[0]))  # V+ left
            self.rails_g.add((r, self.left_rail_cols[1]))  # GND left

        # Add right rails (vertical): V+ then GND
        for r in range(self.rows):
            self.rails_v.add((r, self.right_rail_cols[0]))  # V+ right
            self.rails_g.add((r, self.right_rail_cols[1]))  # GND right

        # 5-hole strips per row: left half 0..4, right half 7..11
        for r in range(self.rows):
            left_strip = [(r, c) for c in range(self.cols_left)]
            right_strip = [
                (r, c)
                for c in range(self.trough_cols[1] + 1,
                               self.trough_cols[1] + 1 + self.cols_right)
            ]
            for hole in left_strip:
                self.strip_of_hole[hole] = tuple(left_strip)
            for hole in right_strip:
                self.strip_of_hole[hole] = tuple(right_strip)

        # Mark rail hole types
        for hole in self.rails_v:
            self.rail_of_hole[hole] = "V+"
        for hole in self.rails_g:
            self.rail_of_hole[hole] = "GND"

        # Initialize occupancy for all *real* holes (board + rails).
        # Gap columns have NO holes and therefore no entries in occ.
        for hole in (self.holes | self.rails_v | self.rails_g):
            self.occ[hole] = ("empty", None)

    def _union_all(self, holes):
        """Union all holes in the list into a single connected set."""
        if not holes:
            return
        base = holes[0]
        for h in holes[1:]:
            self.uf.union(base, h)

    def _init_uf(self):
        """
        Initialize the union-find with:
        - each board hole and rail hole
        - each board 5-hole strip as one connected group
        - each vertical rail as one connected group
        """
        self.uf = UF()
        for hole in (self.holes | self.rails_v | self.rails_g):
            self.uf.add(hole)

        # Unite each 5-hole strip
        seen_strips = set()
        for hole in self.holes:
            strip = self.strip_of_hole.get(hole)
            if not strip or strip in seen_strips:
                continue
            seen_strips.add(strip)
            self._union_all(list(strip))

        # Unite rails
        self._union_all(list(self.rails_v))
        self._union_all(list(self.rails_g))

    def rebuild_union_find(self, nets):
        """
        Reset union-find to the bare board (strips + rails), then add connectivity
        from all existing wire segments in the given nets.
        """
        self._init_uf()
        for net in nets.values():
            for seg in net.seg_paths:
                for i in range(len(seg) - 1):
                    self.uf.union(seg[i], seg[i + 1])

    # --------------------------------------------------------------------- #
    # Occupancy / claim helpers
    # --------------------------------------------------------------------- #
    def claim_component(self, comp_id, body_holes, pin_holes):
        """
        Mark a component's body and pin holes as occupied.

        Returns True if successful, or False if any hole was already in use.
        """
        for hole in body_holes + pin_holes:
            if self.occ[hole][0] != "empty":
                return False

        for hole in body_holes:
            self.occ[hole] = ("comp_body", comp_id)
        for hole in pin_holes:
            self.occ[hole] = ("comp_pin", comp_id)
        return True

    def release_component(self, body_holes, pin_holes):
        """Mark a component's body and pin holes back to empty."""
        for hole in body_holes + pin_holes:
            self.occ[hole] = ("empty", None)

    def claim_wire_segment(self, seg_id, path_holes):
        """
        Claim all real holes along a straight wire path.
        Endpoints are marked as 'wire_end'; interior as 'wire_body'.
        """
        if len(path_holes) < 2:
            return False

        # must all be empty
        for hole in path_holes:
            if self.occ[hole][0] != "empty":
                return False

        for i, hole in enumerate(path_holes):
            if i == 0 or i == len(path_holes) - 1:
                self.occ[hole] = ("wire_end", seg_id)
            else:
                self.occ[hole] = ("wire_body", seg_id)
        return True

    def release_wire_segment(self, path_holes):
        """Mark a wire segment's holes back to empty."""
        for hole in path_holes:
            self.occ[hole] = ("empty", None)

    # --------------------------------------------------------------------- #
    # Utilities for nets and routing
    # --------------------------------------------------------------------- #
    def hole_set_for_net_anchor(self, anchor):
        """Return the set of holes corresponding to special anchors like 'V+' or 'GND'."""
        if anchor == "V+":
            return set(self.rails_v)
        if anchor == "GND":
            return set(self.rails_g)
        return set()

    def frontier_of_anchor(self, anchor):
        """
        Frontier for an anchor like 'V+' or 'GND' = all empty holes on that rail.
        """
        return [h for h in self.hole_set_for_net_anchor(anchor)
                if self.occ[h][0] == "empty"]

    def frontier_of_hole(self, hole):
        """
        Return empty holes on the same 5-hole strip or rail as `hole` (excluding `hole`).
        These are candidate "landing spots" for wires leaving that node.
        """
        if hole in self.rails_v or hole in self.rails_g:
            rail = self.rails_v if hole in self.rails_v else self.rails_g
            return [h for h in rail if self.occ[h][0] == "empty"]

        strip = self.strip_of_hole.get(hole)
        if not strip:
            return []
        return [h for h in strip if self.occ[h][0] == "empty" and h != hole]


class Passive:
    """
    Primitive two-pin component (resistor, capacitor, inductor, LED, etc.).

    We only care about:
    - Name (identifier)
    - Length in holes
    - Orientation ('h' or 'v')
    - Nets connected to each pin (net_a, net_b)
    """
    def __init__(self, name, length, orientation="h"):
        self.name = name
        self.length = length
        self.orientation = orientation

        # These are filled in as part of placement
        self.anchor = None
        self.body = []
        self.pins = []

        # Nets this component connects to
        self.net_a = None
        self.net_b = None

    def legal_placements(self, bb: Breadboard):
        """
        Enumerate all legal placements of this component on the given breadboard.

        We assume the part is a straight line of `length` holes in either
        horizontal or vertical orientation, entirely on the left or right half.
        We also require that each pin's strip has at least one other empty hole
        to land a jumper wire.
        """
        placements = []

        # Step direction for this component's orientation
        dr, dc = ((0, 1) if self.orientation == "h" else (1, 0))

        for hole in bb.holes:
            r, c = hole
            end_r = r + dr * (self.length - 1)
            end_c = c + dc * (self.length - 1)

            if (end_r, end_c) not in bb.occ:
                continue

            body = [(r + dr * i, c + dc * i) for i in range(self.length)]

            # Determine which side of the trough the part lies on
            if all(x[1] < bb.trough_cols[0] for x in body):
                side = "L"
            elif all(x[1] > bb.trough_cols[1] for x in body):
                side = "R"
            else:
                side = None

            if side is None:
                # Reject placements straddling the trough
                continue

            pins = [body[0], body[-1]]

            # Require at least one other empty hole on each pin's strip
            strip0 = bb.strip_of_hole.get(pins[0])
            strip1 = bb.strip_of_hole.get(pins[1])

            if strip0:
                free0 = sum(
                    1 for h2 in strip0
                    if bb.occ[h2][0] == "empty" and h2 not in pins
                )
                if free0 < 1:
                    continue

            if strip1:
                free1 = sum(
                    1 for h2 in strip1
                    if bb.occ[h2][0] == "empty" and h2 not in pins
                )
                if free1 < 1:
                    continue

            placements.append((hole, tuple(body), tuple(pins)))

        return placements

    # Backwards-compatible alias
    def legalPlacements(self, bb: Breadboard):
        """Compatibility wrapper around legal_placements."""
        return self.legal_placements(bb)


class Net:
    """
    A named electrical node ("net").
    - terms: list of hole coordinates that should be connected together
    - fixed_anchors: special identifiers like 'V+' or 'GND' to tie the net to rails
    - seg_paths: list of wire segments; each is a list of hole coordinates along a straight jumper
    """
    def __init__(self, name):
        self.name = name
        self.terms = []
        self.fixed_anchors = []
        self.seg_paths = []


class PnR:
    """
    Place-and-Route engine for breadboard circuits.

    Given:
    - a Breadboard instance
    - a dictionary of Net objects
    - a list of Passive components
    - a mapping of component pins -> net names

    It attempts to:
    1) Place each component at a legal location on the board (backtracking search).
    2) Route each net with straight jumper wires of allowed lengths.
    3) Check that there are no shorts between distinct nets.
    """
    def __init__(self, bb: Breadboard, nets: dict, comps: list, dbg: Dbg = None, max_segments=3):
        self.bb = bb
        self.nets = nets
        self.comps = comps

        # component_name -> (pin_a_hole, pin_b_hole)
        self.pin_of_comp = {}

        # simple counter to give each wire segment a unique id
        self.seg_id_ctr = 1

        self.dbg = dbg or Dbg(False)
        self.max_segments = max(1, max_segments)

    # ------------------------------------------------------------------ #
    # Routing helpers
    # ------------------------------------------------------------------ #
    def holes_along_edge(self, edge):
        """
        Given an edge (two aligned hole coordinates), enumerate all real
        holes along that straight line, including endpoints.
        """
        (r1, c1), (r2, c2) = edge
        dr = r2 - r1
        dc = c2 - c1
        length = max(abs(dr), abs(dc))

        # Step direction: purely vertical or purely horizontal
        if dr != 0:
            step = (1 if dr > 0 else -1, 0)
        else:
            step = (0, 1 if dc > 0 else -1)

        path = []
        for i in range(length + 1):
            hole = (r1 + step[0] * i, c1 + step[1] * i)
            if hole in self.bb.occ:
                path.append(hole)

        return path

    def commit_path(self, net: Net, path_edges):
        """
        Commit a wire path for the given net (may be multiple segments).
        """
        if not path_edges:
            return False

        seg_holes_all = []
        for a, b in path_edges:
            (r1, c1), (r2, c2) = a, b
            if not (r1 == r2 or c1 == c2):
                return False

            holes = self.holes_along_edge((a, b))

            # Block traversing other rails as interior points
            for idx, h in enumerate(holes):
                rk = self.bb.rail_of_hole.get(h)
                if rk:
                    is_endpoint = (idx == 0) or (idx == len(holes) - 1)
                    if not is_endpoint:
                        return False
                    if net.name in ('V+', 'GND'):
                        if rk != net.name:
                            return False
                    else:
                        # internal nets must not terminate on rails
                        return False

            # Ensure all real holes on this edge are empty
            for h in holes:
                if self.bb.occ[h][0] != "empty":
                    return False

            seg_holes_all.append(holes)

        # Claim segments
        for holes in seg_holes_all:
            seg_id = f"seg{self.seg_id_ctr}"
            self.seg_id_ctr += 1
            if not self.bb.claim_wire_segment(seg_id, holes):
                for claimed in net.seg_paths[-len(seg_holes_all):]:
                    self.bb.release_wire_segment(claimed)
                    net.seg_paths.pop()
                return False
            net.seg_paths.append(holes)
            for i in range(len(holes) - 1):
                self.bb.uf.union(holes[i], holes[i + 1])

        return True

    def release_net_wires(self, net: Net):
        """Release all jumper wires belonging to this net."""
        for path_holes in net.seg_paths:
            self.bb.release_wire_segment(path_holes)
        net.seg_paths.clear()

    def net_satisfied(self, net: Net):
        """
        Check if all terminals (and any fixed anchors) of this net share
        the same union-find representative.
        """
        reps = set()

        for t in net.terms:
            reps.add(self.bb.uf.find(t))

        for anchor in net.fixed_anchors:
            holes = self.bb.hole_set_for_net_anchor(anchor)
            for h in holes:
                reps.add(self.bb.uf.find(h))
                break

        return len(reps) == 1

    def _aligned(self, a, b):
        """Return True if a and b are aligned horizontally or vertically."""
        (r1, c1), (r2, c2) = a, b
        return r1 == r2 or c1 == c2

    def _length_ok(self, a, b):
        """
        Check that a and b are aligned and at a distance allowed by
        the board's permitted wire lengths.
        """
        (r1, c1), (r2, c2) = a, b
        if not self._aligned(a, b):
            return False
        L = abs(r1 - r2) + abs(c1 - c2)
        return L in self.bb.wire_lengths

    def find_straight_edge(self, src_frontier, dst_frontier):
        """
        Try to find a straight wire between any src and dst frontier holes.
        """
        pairs = []
        for s in src_frontier:
            for d in dst_frontier:
                if self._aligned(s, d):
                    L = abs(s[0] - d[0]) + abs(s[1] - d[1])
                    pairs.append((L, s, d))

        if not pairs:
            return None

        pairs.sort(key=lambda x: x[0])

        for L, src, dst in pairs:
            if not self._length_ok(src, dst):
                continue

            path_holes = self.holes_along_edge((src, dst))
            if all(self.bb.occ[h][0] == "empty" for h in path_holes):
                return [(src, dst)]

        return None

    def shortest_path_by_segments(self, src_frontier, dst_frontier, max_visit=2000):
        """BFS over legal straight segments."""
        g = {}
        for h in self.bb.holes | self.bb.rails_v | self.bb.rails_g:
            if self.bb.occ[h][0] == "empty":
                neighbors = []
                for L in self.bb.wire_lengths:
                    for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                        neighbor = (h[0] + dr * L, h[1] + dc * L)
                        if neighbor in self.bb.occ and self.bb.occ[neighbor][0] == "empty":
                            neighbors.append(neighbor)
                g[h] = neighbors

        q = deque()
        seen = {}
        for s in src_frontier:
            if s in g:
                q.append(s)
                seen[s] = None

        dst_set = set(d for d in dst_frontier if d in g)
        target = None
        visits = 0

        while q:
            u = q.popleft()
            visits += 1
            if visits > max_visit:
                return None
            if u in dst_set:
                target = u
                break
            for v in g.get(u, []):
                if v not in seen:
                    seen[v] = u
                    q.append(v)

        if target is None:
            return None

        # Reconstruct path
        rev = []
        cur = target
        while cur is not None:
            rev.append(cur)
            cur = seen[cur]
        rev.reverse()

        # Convert to edges
        edges = []
        a = rev[0]
        for b in rev[1:]:
            edges.append((a, b))
            a = b

        return edges

    def find_path_edges(self, src_frontier, dst_frontier):
        """Find a path between source and destination frontiers."""
        if set(src_frontier) & set(dst_frontier):
            return []

        e = self.find_straight_edge(src_frontier, dst_frontier)
        if e:
            return e

        edges = self.shortest_path_by_segments(src_frontier, dst_frontier)
        if edges is None:
            return None

        return edges

    def route_net(self, net: Net):
        """
        Route a single net:
        - Partition all terminals/anchors into connectivity groups.
        - Iteratively connect groups using jumper wires.
        """
        self.bb.rebuild_union_find(self.nets)

        if self.net_satisfied(net):
            return True

        # Group by current connectivity
        rep_groups = defaultdict(list)

        for t in net.terms:
            rep_groups[self.bb.uf.find(t)].append(t)

        if net.fixed_anchors:
            for anchor in net.fixed_anchors:
                for h in self.bb.hole_set_for_net_anchor(anchor):
                    rep_groups[self.bb.uf.find(h)].append(h)
                    break

        groups = list(rep_groups.values())
        if len(groups) <= 1:
            return True

        base_group = groups[0]

        for group in groups[1:]:
            src_frontier = []
            for h in base_group:
                src_frontier.extend(self.bb.frontier_of_hole(h))

            dst_frontier = []
            for h in group:
                dst_frontier.extend(self.bb.frontier_of_hole(h))

            if not src_frontier or not dst_frontier:
                self.dbg.p(f"no frontier: {net.name}")
                self.release_net_wires(net)
                return False

            path = self.find_path_edges(src_frontier, dst_frontier)

            if path is None:
                self.release_net_wires(net)
                return False

            if len(path) == 0:
                base_group = base_group + group
                self.bb.rebuild_union_find(self.nets)
                continue

            if not self.commit_path(net, path):
                self.release_net_wires(net)
                return False

            base_group = base_group + group
            self.bb.rebuild_union_find(self.nets)

        return self.net_satisfied(net)

    def shorts_exist(self):
        """
        Scan all nets that actually have terminals and check if any two
        distinct nets share connectivity.
        """
        names = [name for name, net in self.nets.items() if net.terms]
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                net_i, net_j = names[i], names[j]
                for a in self.nets[net_i].terms:
                    rep_a = self.bb.uf.find(a)
                    for b in self.nets[net_j].terms:
                        if rep_a == self.bb.uf.find(b):
                            self.dbg.p(f"short {net_i}<->{net_j}")
                            return True
        return False

    # ------------------------------------------------------------------ #
    # Placement helpers
    # ------------------------------------------------------------------ #
    def try_place_component(self, comp: Passive, placement):
        """Attempt to claim the holes for a component at a specific placement."""
        anchor_hole, body, pins = placement

        if not self.bb.claim_component(comp.name, list(body), list(pins)):
            return False

        comp.anchor = anchor_hole
        comp.body = list(body)
        comp.pins = list(pins)
        self.pin_of_comp[comp.name] = tuple(pins)
        return True

    def undo_place_component(self, comp: Passive):
        """Undo a component placement and free its holes."""
        if comp.body:
            self.bb.release_component(comp.body, comp.pins)

        comp.anchor = None
        comp.body = []
        comp.pins = []
        self.pin_of_comp.pop(comp.name, None)

    def forward_check(self, comp: Passive, placement):
        """
        Quick feasibility check after placing a component.
        """
        _, _, pins = placement
        pin_a, pin_b = pins
        net_a_name, net_b_name = comp.net_a, comp.net_b

        strip_a = self.bb.strip_of_hole.get(pin_a)
        strip_b = self.bb.strip_of_hole.get(pin_b)

        # Component cannot connect two different nets on the same strip
        if strip_a and strip_b and strip_a == strip_b and net_a_name != net_b_name:
            return False

        def strip_has_other_net(strip, intended_name):
            """Check if this strip has terminals from another net."""
            if not strip:
                return False
            for name, net in self.nets.items():
                if name == intended_name:
                    continue
                for t in net.terms:
                    if self.bb.strip_of_hole.get(t) == strip:
                        return True
            return False

        if strip_has_other_net(strip_a, net_a_name):
            return False
        if strip_has_other_net(strip_b, net_b_name):
            return False

        def target_frontier(net_name):
            if net_name == "V+":
                return self.bb.frontier_of_anchor("V+")
            if net_name == "GND":
                return self.bb.frontier_of_anchor("GND")

            frontier = []
            net = self.nets.get(net_name)
            if not net:
                return frontier

            for t in net.terms:
                frontier.extend(self.bb.frontier_of_hole(t))
            return frontier

        src_a = self.bb.frontier_of_hole(pin_a)
        src_b = self.bb.frontier_of_hole(pin_b)

        dst_a = target_frontier(net_a_name)
        dst_b = target_frontier(net_b_name)

        edge_a = self.find_straight_edge(src_a, dst_a) if dst_a else None
        edge_b = self.find_straight_edge(src_b, dst_b) if dst_b else None

        ok_a = (not dst_a) or (edge_a is not None)
        ok_b = (not dst_b) or (edge_b is not None)

        return ok_a and ok_b

    def order_components(self):
        """
        Order components for placement. Heuristic:
        - First those touching rails (V+ or GND),
        - then longer ones,
        - then by name to keep things deterministic.
        """
        def key(c: Passive):
            rail_weight = (c.net_a in ("V+", "GND")) + (c.net_b in ("V+", "GND"))
            return (-rail_weight, -c.length, c.name)

        return sorted(self.comps, key=key)

    def placement_score(self, comp: Passive, placement):
        """
        Heuristic score for a candidate component placement.
        Lower is better.
        """
        _, _, pins = placement
        pin_a, pin_b = pins

        def dist_to_rail(hole, which):
            """Manhattan distance from hole to the closest rail column."""
            if which == "V+":
                cols = (self.bb.left_rail_cols[0], self.bb.right_rail_cols[0])
            else:
                cols = (self.bb.left_rail_cols[1], self.bb.right_rail_cols[1])

            return min(abs(hole[1] - col) for col in cols)

        score = 0.0

        if comp.net_a in ("V+", "GND"):
            score += 0.3 * dist_to_rail(pin_a, comp.net_a)
        else:
            net_a = self.nets.get(comp.net_a)
            if net_a and net_a.terms:
                score += min(
                    abs(pin_a[0] - t[0]) + abs(pin_a[1] - t[1])
                    for t in net_a.terms
                )

        if comp.net_b in ("V+", "GND"):
            score += 0.3 * dist_to_rail(pin_b, comp.net_b)
        else:
            net_b = self.nets.get(comp.net_b)
            if net_b and net_b.terms:
                score += min(
                    abs(pin_b[0] - t[0]) + abs(pin_b[1] - t[1])
                    for t in net_b.terms
                )

        return score

    # ------------------------------------------------------------------ #
    # Main entry points
    # ------------------------------------------------------------------ #
    def place_and_route(self, net_bindings):
        """
        Main entry point:
        - Bind components to nets.
        - Ensure special rail nets exist if referenced.
        - Backtracking placement.
        - Full routing of all nets.
        """
        # Attach nets to each component from the binding map
        for comp in self.comps:
            net_a, net_b = net_bindings[comp.name]
            comp.net_a, comp.net_b = net_a, net_b

        # Ensure rail nets exist if used anywhere
        rails_used = set()
        for comp in self.comps:
            if comp.net_a in ("V+", "GND"):
                rails_used.add(comp.net_a)
            if comp.net_b in ("V+", "GND"):
                rails_used.add(comp.net_b)

        for rail in rails_used:
            if rail not in self.nets:
                net_obj = Net(rail)
                net_obj.fixed_anchors = [rail]
                self.nets[rail] = net_obj

        # Clear all net state
        for net in self.nets.values():
            net.terms.clear()
            net.seg_paths.clear()

        def bind_pins(comp: Passive):
            """After comp is placed, bind its pin holes into its nets' term lists."""
            pin_a, pin_b = self.pin_of_comp[comp.name]
            if comp.net_a in self.nets:
                self.nets[comp.net_a].terms.append(pin_a)
            if comp.net_b in self.nets:
                self.nets[comp.net_b].terms.append(pin_b)

        ordered_comps = self.order_components()
        return self._place_rec(0, ordered_comps, bind_pins)

    # Backwards-compatible alias
    def placeAndRoute(self, net_bindings):
        """Compatibility wrapper around place_and_route."""
        return self.place_and_route(net_bindings)

    def _place_rec(self, idx, ordered_comps, bind_pins):
        """
        Recursive backtracking over component placements.
        """
        if idx == len(ordered_comps):
            # All components placed, now route all nets
            self.dbg.tick("routing all nets")

            for net in self.nets.values():
                self.release_net_wires(net)

            self.bb.rebuild_union_find(self.nets)

            for net in self.nets.values():
                self.dbg.p(f"route net {net.name}")
                if not self.route_net(net):
                    return False

            if self.shorts_exist():
                self.dbg.p("Short exists")
                return False

            return True

        comp = ordered_comps[idx]
        candidates = comp.legal_placements(self.bb)

        candidates.sort(key=lambda plc: self.placement_score(comp, plc))

        K = 80
        if len(candidates) > K:
            candidates = candidates[:K]

        self.dbg.p(f"[REC] try {comp.name}: {len(candidates)} placements")

        for placement in candidates:
            _, _, pins = placement

            if not self.try_place_component(comp, placement):
                continue

            bind_pins(comp)

            if self.forward_check(comp, placement):
                self.dbg.p(f"placed {comp.name} at {placement[0]}")
                if self._place_rec(idx + 1, ordered_comps, bind_pins):
                    return True
                self.dbg.p(f"backtrack from {comp.name}")
            else:
                self.dbg.p(f"[REC] forward_check FAILED for {comp.name}")

            # Remove pins from their nets
            pin_a_hole, pin_b_hole = self.pin_of_comp[comp.name]
            for net_name, hole in ((comp.net_a, pin_a_hole), (comp.net_b, pin_b_hole)):
                net = self.nets.get(net_name)
                if net and hole in net.terms:
                    net.terms.remove(hole)

            self.undo_place_component(comp)

        return False

    # ------------------------------------------------------------------ #
    # Extracting the solution
    # ------------------------------------------------------------------ #
    def solution(self):
        """Build a dictionary describing the final placement and routing."""
        sol = {"components": {}, "wires": [], "ok": True}

        for comp in self.comps:
            sol["components"][comp.name] = {
                "anchor": comp.anchor,
                "body": comp.body,
                "pins": comp.pins,
                "nets": (comp.net_a, comp.net_b),
            }

        for net in self.nets.values():
            for seg in net.seg_paths:
                sol["wires"].append({"net": net.name, "holes": seg})

        # Sanity check: no hole should be used by multiple things
        used = defaultdict(int)
        for hole, (typ, _) in self.bb.occ.items():
            if typ != "empty":
                used[hole] += 1

        if any(count > 1 for count in used.values()):
            sol["ok"] = False

        return sol


def renderBreadboard(sol, bb: Breadboard, filename=None, show=False, title="Breadboard P&R"):
    """
    Matplotlib renderer for the final breadboard layout.
    Returns base64-encoded PNG string instead of Figure object for JSON serialization.
    """
    rows = bb.rows
    trough_cols = bb.trough_cols

    all_real_holes = bb.holes | bb.rails_v | bb.rails_g
    min_col = min(c for (_, c) in all_real_holes)
    max_col = max(c for (_, c) in all_real_holes)

    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_title(title)

    # Draw holes
    for (r, c) in all_real_holes:
        ax.add_patch(Circle((c, r), 0.08, fill=False, linewidth=0.5))

    # Draw trough as dashed columns
    for c in trough_cols:
        ax.add_patch(
            Rectangle((c - 0.5, -0.5), 1, rows, fill=False, linewidth=1.0, linestyle="--")
        )

    # Draw side gaps
    for c in bb.left_gap_cols:
        ax.add_patch(
            Rectangle((c - 0.5, -0.5), 1, rows, fill=False, linewidth=1.0, linestyle="--")
        )
    for c in bb.right_gap_cols:
        ax.add_patch(
            Rectangle((c - 0.5, -0.5), 1, rows, fill=False, linewidth=1.0, linestyle="--")
        )

    # Label rail columns
    def label_col(col, text):
        ax.text(col, -0.8, text, va="center", ha="center", fontsize=8)

    label_col(bb.left_rail_cols[0], "V+")
    label_col(bb.left_rail_cols[1], "GND")
    label_col(bb.right_rail_cols[0], "V+")
    label_col(bb.right_rail_cols[1], "GND")

    # Outline rail columns
    for col in [*bb.left_rail_cols, *bb.right_rail_cols]:
        ax.add_patch(Rectangle((col - 0.5, -0.5), 1, rows, fill=False, linewidth=0.8))

    # Components
    for name, info in sol.get("components", {}).items():
        # Body
        for (r, c) in info.get("body", []):
            ax.add_patch(Rectangle((c - 0.4, r - 0.4), 0.8, 0.8, alpha=0.35))
        # Pins
        for (r, c) in info.get("pins", []):
            ax.add_patch(Circle((c, r), 0.15, fill=False, linewidth=1.2))

        body = info.get("body", [])
        if body:
            mid = len(body) // 2
            r_lab, c_lab = body[mid]
            ax.text(c_lab, r_lab, name, fontsize=8, ha="center", va="center")

    # Wires: straight line between endpoints, with endpoints highlighted
    for w in sol.get("wires", []):
        holes = w.get("holes", [])
        if len(holes) < 2:
            continue
        (r1, c1), (r2, c2) = holes[0], holes[-1]
        ax.plot([c1, c2], [r1, r2], linewidth=2.0)
        ax.add_patch(Circle((c1, r1), 0.12))
        ax.add_patch(Circle((c2, r2), 0.12))

    ax.set_xlim(min_col - 0.5, max_col + 0.5)
    ax.set_ylim(rows - 0.5, -1.2)
    ax.set_aspect("equal", "box")
    ax.set_xticks(range(min_col, max_col + 1))
    ax.set_yticks(range(0, rows))
    ax.grid(True, which="both", linewidth=0.2, alpha=0.4)
    plt.tight_layout()

    if filename:
        fig.savefig(filename, dpi=200)

    # Convert to base64 PNG for JSON serialization
    buffer = BytesIO()
    fig.savefig(buffer, format='png', dpi=200, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    
    if show:
        plt.show()
    
    plt.close(fig)

    # Return base64 data URI string instead of figure/axes
    return f"data:image/png;base64,{image_base64}"

# ===================================================================== #
# G-CODE GENERATION
# ===================================================================== #

# Printer configuration
MOONRAKER_URL = "http://10.3.141.1/printer/gcode/script"

# Printer and board offsets
X_ORIGIN_PLACEMENT = 107.50
Y_ORIGIN_PLACEMENT = 190
X_ORIGIN_PICKUP = 156.5
Y_ORIGIN_PICKUP = 141.5
PLACE_HEIGHT = 14
PICKUP_HEIGHT = 14
PASSIVE_HEIGHT = 45

# Component pickup coordinates
col_dict = {"R": 0, "C": 2, "L": 4, "LED": 6, "W6": 8}
len_dict = {"R": 6, "C": 6, "L": 6, "LED": 6, "W6": 6}
wires_used = {"W6": 0}


def column_to_x(col_f, pitch=2.54):
    """Convert column index to X coordinate."""
    return col_f * pitch


def row_to_y(row, pitch=2.54):
    """Convert row index to Y coordinate."""
    return row * pitch


def convertCornersToCenter(corners):
    """Calculate center point from corner coordinates."""
    if not corners:
        return 0, 0
    avg_x = sum(p[0] for p in corners) / len(corners)
    avg_y = sum(p[1] for p in corners) / len(corners)
    return avg_x, avg_y


def convertCenterToNominal(centers):
    """Convert center coordinates to nominal board coordinates."""
    nominals = {}
    for name, part in centers.items():
        for center in part:
            nominals[name] = (column_to_x(center[0]), row_to_y(center[1]))
    return nominals


def generate_gcode_from_solution(solution: dict) -> str:
    """
    Generate a COMPLETE G-code script from a PnR solution, matching the
    behavior of the old `run_input` + helpers as seen by the printer.

    - Uses the same coordinate math as:
        - extractComponentPlacements + convertCenterToNominal
        - pickupComponent / pickupWire
        - place()
    - Emits:
        - initial passiveZ()
        - G90 before every move (via sendMoveCommand semantics)
        - VACUUM_ON/OFF exactly like actuateDropper()
    - No sleeps (they were host-side delays, not part of the G-code itself).
    """
    gcode_lines: list[str] = []

    components = solution.get("components", {})
    wires = solution.get("wires", [])

    gcode_lines.append(f"G0 Z{PASSIVE_HEIGHT}")

    for comp_name in sorted(components.keys()):
        comp_data = components[comp_name]
        pins = comp_data.get("pins", [])
        if len(pins) < 2:
            continue

        # ---------- Board placement center (same as extractComponentPlacements) ----------
        # Old code: converted.setdefault(name, []).append(convertCornersToCenter(dict_body["pins"]))
        # where convertCornersToCenter uses p[0] as "x" and p[1] as "y".
        center_x_board, center_y_board = convertCornersToCenter(pins)

        # Old convertCenterToNominal:
        #   nominal_x = column_to_x(center_x)
        #   nominal_y = row_to_y(center_y)
        nominal_x_board = column_to_x(center_x_board)
        nominal_y_board = row_to_y(center_y_board)

        # pickupComponent(id):
        #   part_type = letters, part_num = trailing digits (default 1)
        m = re.match(r"^([A-Z]+)(\d+)$", comp_name)
        if m:
            part_type, part_num = m.group(1), int(m.group(2))
        else:
            part_type, part_num = comp_name, 1

        if part_type not in col_dict or part_type not in len_dict:
            # This is what the old script would effectively "do" (blow up);
            # here we just skip with a warning instead of crashing.
            print(f"[WARNING] Unknown component type {part_type} for {comp_name}, skipping.")
            continue

        # Old pickupComponent center grid:
        # center_X, center_Y = convertCornersToCenter([
        #   (col_dict[part_type], (part_num-1)*(len_dict[part_type]-1)),
        #   (col_dict[part_type], (part_num)  *(len_dict[part_type]-1)),
        # ])
        pickup_center_x, pickup_center_y = convertCornersToCenter(
            [
                (col_dict[part_type],
                 (part_num - 1) * (len_dict[part_type] - 1)),
                (col_dict[part_type],
                 (part_num) * (len_dict[part_type] - 1)),
            ]
        )
        pickup_nom_x = column_to_x(pickup_center_x)
        pickup_nom_y = row_to_y(pickup_center_y)

        # ---------- sendMoveCommand("pickup", (pickup_nom_x, pickup_nom_y)) ----------
        # old sendMoveCommand:
        #   o = [0, 0, 25]
        #   if board=="pickup":
        #       o[0] += X_ORIGIN_PICKUP + X
        #       o[1] =  Y_ORIGIN_PICKUP - Y
        #   G90
        #   G0 F6000 X{round(o[0],3)} Y{round(o[1],3)}
        #   G0 F6000 Z25
        bed_x_pickup = X_ORIGIN_PICKUP + pickup_nom_x
        bed_y_pickup = Y_ORIGIN_PICKUP - pickup_nom_y
        gcode_lines.extend([
            "G90",
            f"G0 F6000 X{round(bed_x_pickup, 3)} Y{round(bed_y_pickup, 3)}",
            "G0 F6000 Z25",
        ])

        # ---------- actuateDropper("pickup") ----------
        # old pickup branch:
        #   G0 Z{PICKUP_HEIGHT}
        #   VACUUM_ON
        #   G0 Z{PASSIVE_HEIGHT}
        gcode_lines.extend([
            f"G0 Z{PICKUP_HEIGHT}",
            "VACUUM_ON",
            f"G0 Z{PASSIVE_HEIGHT}",
        ])

        # ---------- sendMoveCommand("placement", (nominal_x_board, nominal_y_board)) ----------
        bed_x_place = X_ORIGIN_PLACEMENT + nominal_x_board
        bed_y_place = Y_ORIGIN_PLACEMENT - nominal_y_board
        gcode_lines.extend([
            "G90",
            f"G0 F6000 X{round(bed_x_place, 3)} Y{round(bed_y_place, 3)}",
            "G0 F6000 Z25",
        ])

        # ---------- actuateDropper("placement") ----------
        # old placement branch:
        #   G0 Z{PLACE_HEIGHT}
        #   VACUUM_OFF
        #   G0 Z{PASSIVE_HEIGHT}
        gcode_lines.extend([
            f"G0 Z{PLACE_HEIGHT}",
            "VACUUM_OFF",
            f"G0 Z{PASSIVE_HEIGHT}",
        ])

    # so every wire is effectively picked from the same storage location.
    local_wires_used = dict(wires_used)  # start from the same initial values

    for wire in wires:
        holes = wire.get("holes", [])
        if not holes:
            continue
        
        xs = [p[0] for p in holes]
        ys = [p[1] for p in holes]
        if len(set(xs)) > 1:
            varying = xs
        else:
            varying = ys
        wire_length = max(varying) - min(varying) + 1
        wire_type = f"W{wire_length}"

        if wire_type not in col_dict or wire_type not in len_dict:
            print(f"[WARNING] Unknown wire type {wire_type}, skipping wire.")
            continue

        slot_idx = local_wires_used.get(wire_type, 0)
        center_x_pickup, center_y_pickup = convertCornersToCenter(
            [
                (col_dict[wire_type], slot_idx * (len_dict[wire_type] - 1)),
                (col_dict[wire_type], (slot_idx + 1) * (len_dict[wire_type] - 1)),
            ]
        )
        pickup_nom_x = column_to_x(center_x_pickup)
        pickup_nom_y = row_to_y(center_y_pickup)

        bed_x_pickup = X_ORIGIN_PICKUP + pickup_nom_x
        bed_y_pickup = Y_ORIGIN_PICKUP - pickup_nom_y
        gcode_lines.extend([
            "G90",
            f"G0 F6000 X{round(bed_x_pickup, 3)} Y{round(bed_y_pickup, 3)}",
            "G0 F6000 Z25",
        ])
        gcode_lines.extend([
            f"G0 Z{PICKUP_HEIGHT}",
            "VACUUM_ON",
            f"G0 Z{PASSIVE_HEIGHT}",
        ])

        center_x_board, center_y_board = convertCornersToCenter(holes)
        nominal_x_board = column_to_x(center_x_board)
        nominal_y_board = row_to_y(center_y_board)

        bed_x_place = X_ORIGIN_PLACEMENT + nominal_x_board
        bed_y_place = Y_ORIGIN_PLACEMENT - nominal_y_board
        gcode_lines.extend([
            "G90",
            f"G0 F6000 X{round(bed_x_place, 3)} Y{round(bed_y_place, 3)}",
            "G0 F6000 Z25",
        ])
        gcode_lines.extend([
            f"G0 Z{PLACE_HEIGHT}",
            "VACUUM_OFF",
            f"G0 Z{PASSIVE_HEIGHT}",
        ])

    return "\n".join(gcode_lines) + "\n"


_wires_used = {"W6": 0}


def _send_gcode_command(command: str) -> bool:
    """Send a single G-code command to the printer."""
    try:
        payload = {"script": command}
        response = requests.post(MOONRAKER_URL, json=payload, timeout=10)
        if response.status_code == 200:
            return True
        else:
            print(f"[ERROR] Moonraker {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to send command: {e}")
        return False


def execute_gcode_script(gcode: str, delay_between: float = 0.0) -> bool:
    """
    Execute a previously generated G-code script line by line.

    This is the "runner" half of the split:

      solution --> generate_gcode_from_solution(...) --> gcode_string
      gcode_string --> execute_gcode_script(gcode_string)

    Args:
        gcode: Full G-code script as a single string.
        delay_between: optional delay (seconds) between lines, if you
                       want to throttle; default 0 = firehose.

    Returns:
        True on success, False if any line fails to send.
    """
    for raw_line in gcode.splitlines():
        line = raw_line.strip()
        if not line:
            continue  # skip blank lines
        if line.startswith(";"):
            continue  # skip comments, if any

        if not _send_gcode_command(line):
            print(f"[ERROR] Failed sending G-code line: {line!r}")
            return False

        if delay_between > 0:
            time.sleep(delay_between)

    return True
