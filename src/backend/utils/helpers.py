import json
from typing import Tuple
from collections import defaultdict, deque
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from ltspice import Ltspice

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
    #print(f"Variables: {spiceObj.variables}")
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
    def __init__(self, on=False):
        self.on = on
        self.step = 0
    def p(self, *a):
        if self.on:
            print(*a)
    def tick(self, msg=""):
        self.step += 1
        if self.on:
            print(f"[{self.step}] {msg}")

class UF:
    def __init__(self):
        self.p = {}
        self.r = {}
    def add(self, x):
        if x not in self.p:
            self.p[x] = x
            self.r[x] = 0
    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb: return
        if self.r[ra] < self.r[rb]: self.p[ra] = rb
        elif self.r[ra] > self.r[rb]: self.p[rb] = ra
        else: self.p[rb] = ra; self.r[ra] += 1

class Breadboard:
    def __init__(self, rows=40, wire_lengths=(1,3,5)):
        self.rows = rows
        self.cols_left = 5
        self.cols_right = 5
        self.trough_cols = (5,6)
        self.total_cols = self.cols_left + 2 + self.cols_right
        self.wire_lengths = sorted(set(wire_lengths))
        self.holes = set()
        self.rails_v = set(); self.rails_g = set()
        self.strip_of_hole = {}; self.rail_of_hole = {}
        self.occ = {}
        self.uf = UF()
        # Realistic rails: left and right vertical rails, each separated from the board by a 2-hole gap
        self.left_rail_cols  = (-4, -3)   # (V+, GND) on the far left
        self.left_gap_cols   = (-2, -1)   # 2 non-hole columns between left rails and board
        self.right_gap_cols  = (self.total_cols, self.total_cols+1)          # 2 non-hole columns after board
        self.right_rail_cols = (self.total_cols+2, self.total_cols+3)        # (V+, GND) on the far right

        self._buildGeometry(); self._initUF()

    def _buildGeometry(self):
        self.holes.clear()
        self.rails_v.clear()
        self.rails_g.clear()
        self.strip_of_hole.clear()
        self.rail_of_hole.clear()
        self.occ.clear()

        # main board holes (exclude trough columns 5,6)
        for r in range(self.rows):
            for c in range(self.total_cols):
                if c in self.trough_cols: 
                    continue
                self.holes.add((r,c))

        # add left rails (vertical): V+ then GND
        for r in range(self.rows):
            self.rails_v.add((r, self.left_rail_cols[0]))  # V+ left
            self.rails_g.add((r, self.left_rail_cols[1]))  # GND left

        # add right rails (vertical): V+ then GND
        for r in range(self.rows):
            self.rails_v.add((r, self.right_rail_cols[0]))  # V+ right
            self.rails_g.add((r, self.right_rail_cols[1]))  # GND right

        # 5-hole strips per row: left half 0..4, right half 7..11
        for r in range(self.rows):
            left_strip  = [(r,c) for c in range(self.cols_left)]
            right_strip = [(r,c) for c in range(self.trough_cols[1]+1, self.trough_cols[1]+1+self.cols_right)]
            for h in left_strip:  self.strip_of_hole[h]  = tuple(left_strip)
            for h in right_strip: self.strip_of_hole[h] = tuple(right_strip)

        # mark rail hole types
        for h in self.rails_v: self.rail_of_hole[h] = 'V+'
        for h in self.rails_g: self.rail_of_hole[h] = 'GND'

        # init occupancy for all real holes (board + rails). Gaps have NO holes.
        for h in (self.holes | self.rails_v | self.rails_g):
            self.occ[h] = ('empty', None)

    def _initUF(self):
        self.uf = UF()
        for h in self.holes|self.rails_v|self.rails_g: self.uf.add(h)
        seen = set()
        for h in self.holes:
            s = self.strip_of_hole[h]
            if s in seen: continue
            seen.add(s)
            b = s[0]
            for x in s[1:]: self.uf.union(b,x)
        self._unionAll(list(self.rails_v)); self._unionAll(list(self.rails_g))

    def _unionAll(self, lst):
        if not lst: return
        b = lst[0]
        for x in lst[1:]: self.uf.union(b,x)

    def rebuildUF(self, nets):
        self._initUF()
        for net in nets.values():
            for seg in net.seg_paths:
                for i in range(len(seg)-1):
                    self.uf.union(seg[i], seg[i+1])

    def isEmptyRun(self, start, delta, length):
        r,c = start; dr, dc = delta
        ok = True
        for i in range(1, length+1):
            h = (r+dr*i, c+dc*i)
            if h in self.occ:
                t,_ = self.occ[h]
                if t != 'empty':
                    ok = False
                    break
            # if h not in occ: it's a gap/air; allowed to pass (no hole to occupy)
        return ok

    def emptyNeighborsByLengths(self, h):
        out = []; r,c = h
        if self.occ[h][0] != 'empty': 
            return out
        for L in self.wire_lengths:
            for dr,dc in ((0,1),(0,-1),(1,0),(-1,0)):
                end = (r+dr*L, c+dc*L)
                if self.isEmptyRun(h, (dr,dc), L) and end in self.occ:
                    out.append(end)
        return out

    def claimComp(self, comp_id, body_holes, pin_holes):
        for h in body_holes+pin_holes:
            if self.occ[h][0] != 'empty': 
                return False
        for h in body_holes: self.occ[h] = ('comp_body', comp_id)
        for h in pin_holes: self.occ[h] = ('comp_pin', comp_id)
        return True

    def releaseComp(self, body_holes, pin_holes):
        for h in body_holes+pin_holes:
            self.occ[h] = ('empty', None)

    def claimWireSeg(self, seg_id, path_holes):
        # Claim all real holes along the straight path; endpoints are 'wire_end', interior 'wire_body'
        if len(path_holes) < 2:
            return False
        # must all be empty
        for h in path_holes:
            if self.occ[h][0] != 'empty':
                return False
        for i, h in enumerate(path_holes):
            if i == 0 or i == len(path_holes)-1:
                self.occ[h] = ('wire_end', seg_id)
            else:
                self.occ[h] = ('wire_body', seg_id)
        return True

    def releaseWireSeg(self, path_holes):
        for h in path_holes:
            self.occ[h] = ('empty', None)

    def holeSetForNetAnchor(self, anchor):
        if anchor == 'V+': 
            return set(self.rails_v)
        if anchor == 'GND': 
            return set(self.rails_g)
        return set()

    def canLandMoreOnStrip(self, strip, need):
        free = sum(1 for h in strip if self.occ[h][0]=='empty')
        return free >= need

class Passive:
    """Simple 2-pin passive, pins named A and B"""
    def __init__(self, name, length, orientation='h'):
        self.name = name; self.length = length; self.orientation = orientation
        self.anchor = None; self.body = []; self.pins = []; self.net_a = None; self.net_b=None
    def legalPlacements(self, bb: Breadboard):
        outs = []; dr, dc = ((0,1) if self.orientation=='h' else (1,0))
        for h in bb.holes:
            r,c = h; r2, c2 = r+dr*(self.length-1), c+dc*(self.length-1)
            if (r2,c2) not in bb.occ: continue
            body = [(r+dr*i, c+dc*i) for i in range(self.length)]
            side = 'L' if all(x[1] < bb.trough_cols[0] for x in body) else 'R' if all(x[1] > bb.trough_cols[1] for x in body) else None
            if side is None: continue
            pins = [body[0], body[-1]]
            # require at least one other empty hole on each pin's strip for a jumper to land
            
            s0 = bb.strip_of_hole.get(pins[0]); s1 = bb.strip_of_hole.get(pins[1])
            if s0 and sum(1 for h2 in s0 if bb.occ[h2][0]=='empty' and h2 not in pins) < 1: continue
            if s1 and sum(1 for h2 in s1 if bb.occ[h2][0]=='empty' and h2 not in pins) < 1: continue
            outs.append((h, tuple(body), tuple(pins)))
        return outs

class Net:
    def __init__(self, name):
        self.name = name
        self.terms = []            # holes that belong to the net (component pins)
        self.fixed_anchors = []    # e.g. ['V+'] or ['GND']
        self.seg_paths = []        # list[list[holes]]: each straight segment's holes
        # Optional bus planning (lightweight): choose a "local anchor strip" on first non-rail terminal we see
        self.local_anchor_strip = None

class PnR:
    def __init__(self, bb: Breadboard, nets: dict, comps: list, dbg: Dbg=None, max_segments=3):
        self.bb = bb
        self.nets = nets
        self.comps = comps
        self.pin_of_comp = {}  # comp.name -> (pinA_hole, pinB_hole)
        self.seg_id_ctr = 1
        self.dbg = dbg or Dbg(False)
        self.max_segments = max(1, max_segments)

    # ---------- Graph helpers ----------
    def buildSegmentGraph(self):
        g = {}
        # nodes are empty real holes (board + rails)
        for h in self.bb.holes|self.bb.rails_v|self.bb.rails_g:
            if self.bb.occ[h][0] == 'empty':
                g[h] = self.bb.emptyNeighborsByLengths(h)
        return g

    def holesAlongEdge(self, edge):
        a,b = edge
        r1,c1 = a
        r2,c2 = b
        dr = (r2-r1)
        dc = (c2-c1)
        L = max(abs(dr),abs(dc))
        step = ((1 if dr>0 else -1,0) if dr!=0 else (0,1 if dc>0 else -1))
        holes = []
        for i in range(0, L+1):  # include endpoints
            h = (r1 + step[0]*i, c1 + step[1]*i)
            if h in self.bb.occ:   # only REAL holes can be claimed
                holes.append(h)
        return holes

    def commitPath(self, net: Net, path_edges):
        if not path_edges:
            return False

        seg_holes_all = []
        for a,b in path_edges:
            (r1,c1),(r2,c2) = a,b
            if not (r1==r2 or c1==c2):
                return False

            holes = self.holesAlongEdge((a, b))

            # --- NEW: forbid traversing other rails (and rails as interior points) ---
            for idx, h in enumerate(holes):
                # block any rail hole inside the segment
                rk = self.bb.rail_of_hole.get(h)  # 'V+' / 'GND' / None
                if rk:
                    is_endpoint = (idx == 0) or (idx == len(holes)-1)
                    if not is_endpoint:
                        return False  # cannot pass through a rail column
                    # if endpoint is a rail, it must be the right one for this net
                    if net.name in ('V+','GND'):
                        if rk != net.name:
                            return False
                    else:
                        # internal nets must not terminate on rails
                        return False

            # ensure all real holes on this edge are empty
            for h in holes:
                if self.bb.occ[h][0] != 'empty':
                    return False

            seg_holes_all.append(holes)

        # claim segments (unchanged)
        for holes in seg_holes_all:
            seg_id = f"seg{self.seg_id_ctr}"
            self.seg_id_ctr += 1
            if not self.bb.claimWireSeg(seg_id, holes):
                for claimed in net.seg_paths[-len(seg_holes_all):]:
                    self.bb.releaseWireSeg(claimed)
                    net.seg_paths.pop()
                return False
            net.seg_paths.append(holes)
            for i in range(len(holes)-1):
                self.bb.uf.union(holes[i], holes[i+1])

        return True

    def releaseNetWires(self, net: Net):
        for holes in net.seg_paths: self.bb.releaseWireSeg(holes)
        net.seg_paths.clear()

    def frontierOfHole(self, h):
        if h in self.bb.rails_v or h in self.bb.rails_g:
            rail = self.bb.rails_v if h in self.bb.rails_v else self.bb.rails_g
            return [x for x in rail if self.bb.occ[x][0]=='empty' and x != h]
        s = self.bb.strip_of_hole.get(h)
        if not s: return []
        return [x for x in s if self.bb.occ[x][0]=='empty' and x != h]


    def frontierOfAnchor(self, anchor):
        return [x for x in self.bb.holeSetForNetAnchor(anchor) if self.bb.occ[x][0]=='empty']

    # ---------- Pathfinding ----------
    def _aligned(self, a, b):
        (r1,c1),(r2,c2)=a,b
        return r1==r2 or c1==c2

    def _len_ok(self, a, b):
        (r1,c1),(r2,c2)=a,b
        L = abs(r1-r2) + abs(c1-c2)
        return (r1==r2 or c1==c2) and (L in self.bb.wire_lengths)

    def findStraightEdge(self, src_frontier, dst_frontier):
        """Fast path: single straight jumper between any src and dst frontier hole."""
        pairs = []
        for s in src_frontier:
            for d in dst_frontier:
                if self._aligned(s,d):
                    L = abs(s[0]-d[0]) + abs(s[1]-d[1])
                    pairs.append((L, s, d))
        if not pairs:
            return None
        pairs.sort(key=lambda x: x[0])  # closest first
        for _, s, d in pairs:
            if not self._len_ok(s,d):
                continue
            holes = self.holesAlongEdge((s,d))  # returns only REAL holes along that straight line
            # All real holes on that line must be empty
            usable = True
            for h in holes:
                if self.bb.occ[h][0] != 'empty':
                    usable = False
                    break
            if usable:
                return [(s,d)]
        return None

    def shortestPathBySegments(self, src_frontier, dst_frontier, max_visit=2000):
        """BFS over legal straight segments (graph nodes are empty holes)."""
        g = self.buildSegmentGraph()
        q = deque()
        seen = {}
        for s in src_frontier:
            if s in g: q.append(s); seen[s]=None
        dst_set = set(d for d in dst_frontier if d in g)
        target=None
        visits = 0
        while q:
            u = q.popleft()
            visits += 1
            if visits > max_visit:
                self.dbg.p("bfs_cap")
                return None
            if u in dst_set: target=u; break
            for v in g.get(u, []):
                if v not in seen:
                    seen[v]=u
                    q.append(v)
        if target is None: 
            return None
        # reconstruct path as sequence of nodes (holes), then turn into edges by collapsing collinear runs
        rev=[]
        cur=target
        while cur is not None: rev.append(cur); cur=seen[cur]
        rev.reverse()
        # compress to edges (each must be aligned and length in allowed set by construction)
        edges=[]
        a = rev[0]
        for b in rev[1:]:
            edges.append((a,b))
            a = b
        # Optionally merge consecutive collinear steps if they form a longer legal segment: NOT necessary because
        # edges already represent jumps of allowed lengths (graph arcs are those jumps), so each edge is a straight jumper.
        return edges

    def findPathEdges(self, src_frontier, dst_frontier):
        # already-connected or share a landing hole: no jumper needed
        if set(src_frontier) & set(dst_frontier):
            return []  # signal "no-op" success

        e = self.findStraightEdge(src_frontier, dst_frontier)
        if e: return e
        edges = self.shortestPathBySegments(src_frontier, dst_frontier)
        if edges is None:  # bfs failed
            return None
        return edges  # may be [], meaning "no-op"


    # ---------- Placement helpers ----------
    def orderComps(self):
        """Prefer parts that touch rails and longer parts; cluster by (net_a, net_b)."""
        def key(c):
            rail_weight = (c.net_a in ('V+','GND')) + (c.net_b in ('V+','GND'))
            pair = tuple(sorted((c.net_a, c.net_b)))
            return (-rail_weight, -c.length, pair, c.name)
        return sorted(self.comps, key=key)

    def tryPlaceComp(self, comp: Passive, place):
        anchor, body, pins = place
        if not self.bb.claimComp(comp.name, list(body), list(pins)): 
            return False
        comp.anchor = anchor; comp.body = list(body)
        comp.pins = list(pins)
        self.pin_of_comp[comp.name] = tuple(pins)
        # For non-rail nets: opportunistically choose a local bus strip (first terminal strip)
        for netname, pinhole in ((comp.net_a, pins[0]), (comp.net_b, pins[1])):
            net = self.nets.get(netname)
            if net and not net.fixed_anchors and net.local_anchor_strip is None:
                net.local_anchor_strip = self.bb.strip_of_hole.get(pinhole)
        return True

    def undoPlaceComp(self, comp: Passive):
        if comp.body: 
            self.bb.releaseComp(comp.body, comp.pins)
        comp.anchor=None
        comp.body=[]
        comp.pins=[]
        self.pin_of_comp.pop(comp.name, None)

    def _strip(self, h):
        return self.bb.strip_of_hole.get(h)

    def _strip_has_other_net(self, strip, intended):
        if not strip: return False
        for name, net in self.nets.items():
            if name == intended:
                continue
            for t in net.terms:
                if self._strip(t) == strip:
                    return True
        return False

    def _pin_capacity_ok(self, pin_hole, netname):
        """Ensure there's at least one landing hole available on this pin's strip if we need to run a jumper."""
        srcF = self.frontierOfHole(pin_hole)
        # If there is no need to jumper (because it's already connected to a same-net terminal on same strip), it's OK.
        # We'll handle connectivity in forwardCheck more fully; here just ensure availability.
        if srcF:
            return True
        # If no frontier holes left, but there are multiple same-net pins sharing this strip AND this strip is already connected to rest of net, it's OK.
        # Cheap heuristic: if another terminal of same net sits on this strip, treat capacity as OK (no extra jumper needed to connect within strip).
        strip = self._strip(pin_hole)
        if strip:
            for t in self.nets[netname].terms:
                if self._strip(t) == strip:
                    return True
        return False

    def forwardCheck(self, comp: Passive, place, pin_net_map):
        """Stronger forward check:
           - forbid different nets sharing a strip
           - per-pin reachability to net target via <= max_segments segments
           - crude capacity check on source strip and destination anchor/frontier
        """
        _,_,pins = place
        pinA, pinB = pins
        na, nb = comp.net_a, comp.net_b

        # --- strip conflict guard (no two different nets on one strip) ---
        sA = self._strip(pinA); sB = self._strip(pinB)
        if sA and sB and sA == sB and na != nb:
            return False
        if self._strip_has_other_net(sA, na): 
            return False
        if self._strip_has_other_net(sB, nb): 
            return False

        # Build target frontiers for each net
        def targetFrontier(netname):
            if netname=='V+': 
                return self.frontierOfAnchor('V+')
            if netname=='GND':
                return self.frontierOfAnchor('GND')
            f=[]
            for t in self.nets[netname].terms: f += self.frontierOfHole(t)
            # also include local bus strip empties if set
            lan = self.nets[netname].local_anchor_strip
            if lan:
                f += [x for x in lan if self.bb.occ[x][0]=='empty']
            return f

        # Sources (from each pin's strip)
        srcA = self.frontierOfHole(pinA)
        srcB = self.frontierOfHole(pinB)

        # Quick capacity checks: pin strips should have at least one landing hole if a jumper is needed
        if not self._pin_capacity_ok(pinA, na): return False
        if not self._pin_capacity_ok(pinB, nb): return False

        # Reachability checks with up to max_segments segments
        def canReach(srcF, tf):
            if not tf:                      # no target yet → OK
                return True
            if not srcF:                    # nowhere to start a jumper
                return False
            path = self.findPathEdges(srcF, tf)  # <-- unify logic
            return path is not None and (len(path) == 0 or len(path) <= self.max_segments)

        fa = targetFrontier(na)
        fb = targetFrontier(nb)
        ok_a = canReach(srcA, fa)
        ok_b = canReach(srcB, fb)
        return ok_a and ok_b

    def pathIsHoleSafe(self, path_edges):
        if not path_edges: return False
        # Do not allow two consecutive edges to "double-use" the joint node as an interior duplicate,
        # but as we claim each edge independently this is naturally avoided. Keep simple True here.
        return True

    # ---------- Net connectivity helpers ----------
    def netSatisfied(self, net: Net):
        reps = set()
        for t in net.terms: reps.add(self.bb.uf.find(t))
        for fa in net.fixed_anchors:
            for h in self.bb.holeSetForNetAnchor(fa): reps.add(self.bb.uf.find(h)); break
        # Local anchor strip representative if exists
        if net.local_anchor_strip:
            reps.add(self.bb.uf.find(net.local_anchor_strip[0]))
        return len(reps)==1

    def routeNet(self, net: Net):
        self.bb.rebuildUF(self.nets)
        if self.netSatisfied(net):
            return True

        rep_groups = defaultdict(list)
        for t in net.terms:
            rep_groups[self.bb.uf.find(t)].append(t)

        rail_rep = None
        if net.fixed_anchors:
            for fa in net.fixed_anchors:
                for h in self.bb.holeSetForNetAnchor(fa):
                    rid = self.bb.uf.find(h)
                    rep_groups[rid].append(h)
                    rail_rep = rid
                    break

        if net.local_anchor_strip:
            h0 = net.local_anchor_strip[0]
            rep_groups[self.bb.uf.find(h0)].append(h0)

        groups = list(rep_groups.values())
        if len(groups) <= 1:
            return True

        # <-- Prefer rail as the base group if present
        if rail_rep is not None:
            base = rep_groups[rail_rep]
            others = [g for rid,g in rep_groups.items() if rid != rail_rep]
        else:
            base = groups[0]
            others = groups[1:]

        for group in others:
            src_frontier = []
            for h in base:
                src_frontier += self.frontierOfHole(h)
            dst_frontier = []
            for h in group:
                dst_frontier += self.frontierOfHole(h)

            if not src_frontier or not dst_frontier:
                self.dbg.p(f"no frontier: {net.name}")
                self.releaseNetWires(net)
                return False

            path = self.findPathEdges(src_frontier, dst_frontier)
            # self.dbg.p(f"route {net.name}: |srcF|={len(src_frontier)} |dstF|={len(dst_frontier)} -> {'ok' if path is not None else 'fail'}")

            if path is None:
                self.releaseNetWires(net)
                return False
            if len(path) == 0:
                # already connected / shared landing: just merge groups
                base = base + group
                self.bb.rebuildUF(self.nets)
                continue
            if not self.pathIsHoleSafe(path):
                self.releaseNetWires(net)
                return False
            if not self.commitPath(net, path):
                self.releaseNetWires(net)
                return False

            base = base + group
            self.bb.rebuildUF(self.nets)

        return self.netSatisfied(net)

    # ---------- Main search ----------
    def placeAndRoute(self, pin_net_bindings):
        """pin_net_bindings: dict like {'R1.A':'N1', 'R1.B':'GND', 'R2.A':'N1', 'R2.B':'GND'}"""
        # Attach per-pin nets to components
        for comp in self.comps:
            na = pin_net_bindings.get(f"{comp.name}.A")
            nb = pin_net_bindings.get(f"{comp.name}.B")
            comp.net_a, comp.net_b = na, nb

        # Ensure rail nets exist if referenced
        rails_used = set()
        for comp in self.comps:
            if comp.net_a in ('V+', 'GND'): rails_used.add(comp.net_a)
            if comp.net_b in ('V+', 'GND'): rails_used.add(comp.net_b)
        for rail in rails_used:
            if rail not in self.nets:
                self.nets[rail] = Net(rail)
            self.nets[rail].fixed_anchors = [rail]

        # Reset nets
        for net in self.nets.values():
            net.terms.clear()
            net.seg_paths.clear()
            net.local_anchor_strip = None

        def bindPins(comp):
            a,b = self.pin_of_comp[comp.name]
            if comp.net_a in self.nets and a not in self.nets[comp.net_a].terms:
                self.nets[comp.net_a].terms.append(a)
            if comp.net_b in self.nets and b not in self.nets[comp.net_b].terms:
                self.nets[comp.net_b].terms.append(b)

        comps = self.orderComps()
        return self._placeRec(0, comps, bindPins)

    def _placeRec(self, i, comps, bindPins):
        if i == len(comps):
            # Route all nets
            for net in self.nets.values():
                self.releaseNetWires(net)
            self.bb.rebuildUF(self.nets)
            for net in self.nets.values():
                #self.dbg.p(f"route net {net.name}")
                if not self.routeNet(net): return False
            if self.shortsExist():
                return False
            return True

        comp = comps[i]
        cands = comp.legalPlacements(self.bb)
        # sort by heuristic score
        cands.sort(key=lambda plc: self.placementScore(comp, plc))
        K = 40  # consider more since we can L-route
        if len(cands) > K:
            cands = cands[:K]

        self.dbg.p(f"try {comp.name}: {len(cands)} placements")
        for place in cands:
            if not self.tryPlaceComp(comp, place):
                continue
            bindPins(comp)
            if self.forwardCheck(comp, place, {'A': comp.net_a, 'B': comp.net_b}):
                #self.dbg.p(f"placed {comp.name} at {place[0]} orient={comp.orientation}")
                if self._placeRec(i+1, comps, bindPins):
                    return True
                #self.dbg.p(f"backtrack from {comp.name}")
            # unbind & undo
            a_hole, b_hole = self.pin_of_comp[comp.name]
            for netname, hole in ((comp.net_a, a_hole), (comp.net_b, b_hole)):
                if netname in self.nets:
                    try:
                        self.nets[netname].terms.remove(hole)
                    except ValueError:
                        pass
            self.undoPlaceComp(comp)
        return False

    # ---------- Scoring & checks ----------
    def placementScore(self, comp, place):
        # smaller is better
        _, _, pins = place
        pinA, pinB = pins
        def distToRail(h, which):
            # Manhattan distance to the closest hole on either V+ or GND vertical rail column.
            cols = (self.bb.left_rail_cols[0], self.bb.right_rail_cols[0]) if which=='V+' \
                   else (self.bb.left_rail_cols[1], self.bb.right_rail_cols[1])
            return min(abs(h[1]-col) for col in cols)

        s = 0.0
        # Prefer closeness to rails for rail-bound pins
        if comp.net_a in ('V+','GND'):
            s += distToRail(pinA, comp.net_a)
        else:
            terms = self.nets[comp.net_a].terms
            if terms:
                s += min(abs(pinA[0]-t[0]) + abs(pinA[1]-t[1]) for t in terms)
        if comp.net_b in ('V+','GND'):
            s += distToRail(pinB, comp.net_b)
        else:
            terms = self.nets[comp.net_b].terms
            if terms:
                s += min(abs(pinB[0]-t[0]) + abs(pinB[1]-t[1]) for t in terms)

        # Prefer staying away from trough edges very slightly
        s += 0.05 * (abs(pinA[1]-self.bb.trough_cols[0]) + abs(pinB[1]-self.bb.trough_cols[1]))

        # Encourage clusters for parts that share the same two nets
        pairA = tuple(sorted((comp.net_a, comp.net_b)))
        cluster_bonus = 0.0
        for other in self.comps:
            if other is comp: 
                continue
            if other.pins:
                pairB = tuple(sorted((other.net_a, other.net_b)))
                if pairA == pairB:
                    # small bonus for being near other already-placed similar pair
                    pa = other.pins[0]; pb = other.pins[1]
                    d = min(abs(pinA[0]-pa[0]) + abs(pinA[1]-pa[1]),
                            abs(pinB[0]-pb[0]) + abs(pinB[1]-pb[1]))
                    cluster_bonus += 0.01 * d
        s += cluster_bonus
        return s

    def shortsExist(self):
        # Only consider nets that actually have terminals
        names = [k for k,v in self.nets.items() if v.terms]
        for i in range(len(names)):
            for j in range(i+1, len(names)):
                ni, nj = names[i], names[j]
                for a in self.nets[ni].terms:
                    ra = self.bb.uf.find(a)
                    for b in self.nets[nj].terms:
                        if ra == self.bb.uf.find(b):
                            self.dbg.p(f"short {ni}<->{nj} via nodes containing {a} and {b}")
                            return True
        return False

    def solution(self):
        sol = {'components':{}, 'wires':[], 'ok': True}
        for c in self.comps:
            sol['components'][c.name] = {'anchor': c.anchor, 'body': c.body, 'pins': c.pins, 'nets': (c.net_a, c.net_b)}
        for net in self.nets.values():
            for seg in net.seg_paths: sol['wires'].append({'net': net.name, 'holes': seg})
        used = defaultdict(int)
        for h,(t,_) in self.bb.occ.items():
            if t != 'empty': used[h]+=1
        if any(c>1 for c in used.values()): sol['ok']=False
        return sol

def renderBreadboard(sol, bb, filename=None, show=True, title="Breadboard P&R"):
    rows = bb.rows
    core_cols = bb.total_cols
    trough_cols = bb.trough_cols

    # collect all real holes to set bounds
    all_real = (bb.holes | bb.rails_v | bb.rails_g)
    min_col = min(c for r,c in all_real)
    max_col = max(c for r,c in all_real)

    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_title(title)

    # draw holes (board + rails)
    for (r,c) in all_real:
        ax.add_patch(Circle((c, r), 0.08, fill=False, linewidth=0.5))

    # draw trough as dashed columns
    for c in trough_cols:
        ax.add_patch(Rectangle((c-0.5, -0.5), 1, rows, fill=False, linewidth=1.0, linestyle="--"))

    # draw 2-column side gaps (no holes)
    for c in bb.left_gap_cols:
        ax.add_patch(Rectangle((c-0.5, -0.5), 1, rows, fill=False, linewidth=1.0, linestyle="--"))
    for c in bb.right_gap_cols:
        ax.add_patch(Rectangle((c-0.5, -0.5), 1, rows, fill=False, linewidth=1.0, linestyle="--"))

    # label rail columns at the top
    def label_col(col, text): ax.text(col, -0.8, text, va="center", ha="center", fontsize=8)
    label_col(bb.left_rail_cols[0],  "V+");  label_col(bb.left_rail_cols[1],  "GND")
    label_col(bb.right_rail_cols[0], "V+");  label_col(bb.right_rail_cols[1], "GND")

    # lightly outline rail columns
    for col in [*bb.left_rail_cols, *bb.right_rail_cols]:
        ax.add_patch(Rectangle((col-0.5, -0.5), 1, rows, fill=False, linewidth=0.8))

    # components
    for name, info in sol.get("components", {}).items():
        for (r, c) in info.get("body", []):
            ax.add_patch(Rectangle((c-0.4, r-0.4), 0.8, 0.8, alpha=0.35))
        for (r, c) in info.get("pins", []):
            ax.add_patch(Circle((c, r), 0.15, fill=False, linewidth=1.2))
        body = info.get("body", [])
        if body:
            mid = len(body) // 2
            r_lab, c_lab = body[mid]
            ax.text(c_lab, r_lab, name, fontsize=8, ha="center", va="center")

    # wires: straight line between endpoints, and fill every real hole on that path by virtue of geometry
    for w in sol.get("wires", []):
        holes = w.get("holes", [])
        if len(holes) < 2:
            continue
        (r1, c1), (r2, c2) = holes[0], holes[-1]
        ax.plot([c1, c2], [r1, r2], linewidth=2.0)
        ax.add_patch(Circle((c1, r1), 0.12))
        ax.add_patch(Circle((c2, r2), 0.12))

    ax.set_xlim(min_col-0.5, max_col+0.5)
    ax.set_ylim(rows-0.5, -1.2)
    ax.set_aspect('equal', 'box')
    ax.set_xticks(range(min_col, max_col+1))
    ax.set_yticks(range(0, rows))
    ax.grid(True, which='both', linewidth=0.2, alpha=0.4)
    plt.tight_layout()
    if filename: fig.savefig(filename, dpi=200)
    if show: plt.show()
    return fig, ax
