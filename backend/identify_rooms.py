"""
identify_rooms.py
───────────────────────────────────────────────────────────────────────────────
Identify rectangular-ish “rooms” in an architectural SVG.

The algorithm is a direct, literal Python translation of the notebook-style
prototype you supplied (labelled “Code(1)”).  It

1.  parses the incoming SVG,
2.  keeps only *thick* polylines/lines (≈ walls),
3.  flattens them into individual segments,
4.  casts paired normal rays to group parallel wall-faces into *stripe pairs*,
5.  joins every stripe pair with mid-point connectors,
6.  aligns and merges those connectors into a skeletal line-network, and finally
7.  polygonises that network to obtain closed faces, returning each face’s
    axis-aligned bounding-box.

The front-end already expects a JSON list in the form  
`[{"bbox": [x, y, w, h]}, …]`; this function produces exactly that.

Dependencies
────────────
* **numpy**
* **shapely ≥ 1.8**  (for polygonising the final skeleton)

Install them once (inside your backend’s venv) with

    pip install numpy shapely

If Shapely is missing the function still loads, but returns an empty list.

You are welcome to remove the many inline `print()` statements or the optional
debug plots once everything works to your liking.
"""

from __future__ import annotations

import math
import random
import xml.etree.ElementTree as ET
from collections import defaultdict
from math import atan2, degrees, sqrt
from typing import Dict, List, Sequence, Tuple

import numpy as np

# ─────────────────────────────── helper maths ────────────────────────────────
EPS = 1.0e-9


def cross_2d(a: np.ndarray, b: np.ndarray) -> float:
    """2-D cross product (scalar)."""
    return a[0] * b[1] - a[1] * b[0]


def unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n else v


# ─────────────────────────── SVG → thick polylines ───────────────────────────
def _extract_polylines(svg_text: str, stroke_thresh: float = 1.5) -> List[List[Tuple[float, float]]]:
    """
    Return a list of **poly-lines** (lists of (x,y)) whose stroke-width is
    ≥ stroke_thresh.  Only <polyline>, <polygon>, and <line> elements are
    handled – that is sufficient for flattened PDF-to-SVG floor-plans.
    """
    # SVG may or may not carry a namespace; ignore it
    def _strip_ns(tag: str) -> str:
        return tag.split("}", 1)[-1]

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return []

    polylines = []

    for el in root.iter():
        tag = _strip_ns(el.tag)
        sw_txt = el.attrib.get("stroke-width") or el.attrib.get("style", "")
        if "stroke-width" in sw_txt:  # inlined CSS
            try:
                sw_txt = (
                    sw_txt.split("stroke-width", 1)[1]
                    .split(":", 1)[1]
                    .split(";", 1)[0]
                )
            except IndexError:
                sw_txt = "1"
        stroke_w = float(sw_txt or 1.0)

        if stroke_w < stroke_thresh:
            continue  # too thin → ignore (probably annotation or furniture)

        if tag in ("polyline", "polygon"):
            raw_pts = (el.attrib.get("points") or "").replace(",", " ").split()
            if len(raw_pts) < 4:
                continue
            pts = list(map(float, raw_pts))
            polylines.append(list(zip(pts[0::2], pts[1::2])))

        elif tag == "line":
            try:
                x1, y1 = float(el.attrib["x1"]), float(el.attrib["y1"])
                x2, y2 = float(el.attrib["x2"]), float(el.attrib["y2"])
            except (KeyError, ValueError):
                continue
            polylines.append([(x1, y1), (x2, y2)])

        # <path> omitted – they are rare in Poppler SVGs and harder to flatten.
        # Bring in `svgpathtools` if you need true Bézier support.

    return polylines


# ──────────────────────────── core identification ───────────────────────────
def identify(svg_text: str) -> List[Dict[str, Sequence[float]]]:
    """Main entry point used by *server.py*."""
    thick_polylines = _extract_polylines(svg_text)
    if not thick_polylines:
        return []

    # 5 ─ Flatten thick polylines into segments ──────────────────────────────
    segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = [
        (p1, p2) for poly in thick_polylines for p1, p2 in zip(poly[:-1], poly[1:])
    ]

    # Pre-compute per-segment data
    orientations, midpoints, lengths = [], [], []
    for (x1, y1), (x2, y2) in segments:
        dx, dy = x2 - x1, y2 - y1
        orientations.append(degrees(atan2(dy, dx)) % 180)
        midpoints.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0))
        lengths.append(sqrt(dx * dx + dy * dy))

    orientations = np.asarray(orientations)
    midpoints = np.asarray(midpoints)
    lengths = np.asarray(lengths)

    # 6 ─ One random point per segment ───────────────────────────────────────
    random.seed(42)
    rand_points = []
    for (x1, y1), (x2, y2) in segments:
        t = random.random()
        rand_points.append((x1 + t * (x2 - x1), y1 + t * (y2 - y1)))

    # 8 ─ Cast normals until they hit another segment ────────────────────────
    def intersect_ray_segment(P: np.ndarray, d: np.ndarray, Q1: np.ndarray, Q2: np.ndarray):
        r = Q2 - Q1
        denom = cross_2d(d, r)
        if abs(denom) < EPS:
            return None
        t = cross_2d(Q1 - P, r) / denom
        u = cross_2d(Q1 - P, d) / denom
        if t >= 0 and 0 <= u <= 1:
            return t, P + t * d
        return None

    pair_points, connectors, pairs_dict = [], [], {}
    for idx, ((x1, y1), (x2, y2)) in enumerate(segments):
        P0 = np.array(rand_points[idx])
        v = np.array([x2 - x1, y2 - y1])
        v_norm = np.linalg.norm(v) or 1.0
        n1, n2 = np.array([-v[1], v[0]]) / v_norm, np.array([v[1], -v[0]]) / v_norm

        best_t, best_pt = math.inf, None
        for d in (n1, n2):
            for jdx, (Q1, Q2) in enumerate(segments):
                if jdx == idx:
                    continue
                hit = intersect_ray_segment(P0, d, np.array(Q1), np.array(Q2))
                if hit:
                    t, P_hit = hit
                    if t < best_t:
                        best_t, best_pt = t, P_hit

        if best_pt is not None:
            pair_points.append(best_pt)
            connectors.append((P0, best_pt))
            pairs_dict[idx] = best_pt

    # 9 & 11 ─ Confirm same-distance mate on original segment & second normal
    kept_P0, kept_P1, kept_P2 = [], [], []
    connectors_on = []
    for idx, P1 in pairs_dict.items():
        (x1, y1), (x2, y2) = segments[idx]
        P0 = np.array(rand_points[idx])
        P1 = np.array(P1)
        d = np.linalg.norm(P1 - P0)

        v = np.array([x2 - x1, y2 - y1])
        L = np.linalg.norm(v)
        if L == 0:
            continue
        v_hat = v / L

        t0 = np.dot(P0 - np.array([x1, y1]), v_hat) / L
        dt = d / L

        for sign in (-1, 1):
            t2 = t0 + sign * dt
            if 0 <= t2 <= 1:
                P2 = np.array([x1, y1]) + t2 * v
                kept_P0.append(P0)
                kept_P1.append(P1)
                kept_P2.append(P2)
                connectors_on.append((P0, P2))
                break  # keep first feasible

    # 11 → 13 ─ Build first generation of stripe pairs
    MAX_GAP_RATIO = 2.0

    def point_on_segment(P, Q1, Q2, tol=1e-6):
        if abs(cross_2d(Q2 - Q1, P - Q1)) > tol:
            return False
        dot1 = np.dot(P - Q1, Q2 - Q1)
        dot2 = np.dot(P - Q2, Q1 - Q2)
        return dot1 >= -tol and dot2 >= -tol

    stripe_pairs, viz_data = set(), []
    for idxA, P1 in pairs_dict.items():
        P0 = np.array(rand_points[idxA])
        P1 = np.array(P1)

        idxB = None
        for jdx, (Q1, Q2) in enumerate(segments):
            if jdx == idxA:
                continue
            if point_on_segment(P1, np.array(Q1), np.array(Q2)):
                idxB = jdx
                break
        if idxB is None:
            continue

        (x1, y1), (x2, y2) = segments[idxA]
        v = np.array([x2 - x1, y2 - y1])
        L = np.linalg.norm(v)
        if L == 0:
            continue
        v_hat = v / L
        t0 = np.dot(P0 - np.array([x1, y1]), v_hat) / L
        d = np.linalg.norm(P1 - P0)
        dt = d / L

        candidates = []
        for sign in (-1, 1):
            t2 = t0 + sign * dt
            if 0 <= t2 <= 1:
                P2 = np.array([x1, y1]) + t2 * v
                candidates.append(P2)

        dir_vec = P1 - P0
        n_len = np.linalg.norm(dir_vec)
        if n_len < EPS:
            continue
        d_hat = dir_vec / n_len

        (B1, B2) = segments[idxB]
        B1, B2 = np.array(B1), np.array(B2)

        for P2 in candidates:
            hit = intersect_ray_segment(P2, d_hat, B1, B2)
            if hit:
                t_hit, P3 = hit
                if t_hit > MAX_GAP_RATIO * d:
                    continue
                stripe_pairs.add(frozenset({idxA, idxB}))
                viz_data.append((P0, P1, P2))
                break

    # 13 → 18 ─ Iteratively absorb all remaining segments (identical to prototype)
    EPS_PT = 1e-6
    ANG_TOL = 5.0

    def same_pt(P, Q, tol=EPS_PT):
        return abs(P[0] - Q[0]) <= tol and abs(P[1] - Q[1]) <= tol

    def is_parallel(i, j, tol=ANG_TOL):
        d_ang = abs(orientations[i] - orientations[j])
        d_ang = d_ang if d_ang <= 90 else 180 - d_ang
        return d_ang <= tol

    endpts = [segments[i] for i in range(len(segments))]
    pt2segs = defaultdict(list)
    for idx, (P, Q) in enumerate(endpts):
        pt2segs[(round(P[0], 6), round(P[1], 6))].append(idx)
        pt2segs[(round(Q[0], 6), round(Q[1], 6))].append(idx)

    def reds_adjacent_to(seg_idx, lonely):
        res = set()
        for P in endpts[seg_idx]:
            res |= {
                j for j in pt2segs[(round(P[0], 6), round(P[1], 6))] if j in lonely
            }
        return res

    iter_no = 0
    while True:
        iter_no += 1
        paired = {i for pr in stripe_pairs for i in pr}
        ungrouped = set(range(len(segments))) - paired

        connector = set()
        for u in ungrouped:
            U1, U2 = endpts[u]
            for pair in stripe_pairs:
                A, B = tuple(pair)
                A1, A2 = endpts[A]
                B1, B2 = endpts[B]
                if (
                    (same_pt(U1, A1) or same_pt(U1, A2))
                    and (same_pt(U2, B1) or same_pt(U2, B2))
                ) or (
                    (same_pt(U2, A1) or same_pt(U2, A2))
                    and (same_pt(U1, B1) or same_pt(U1, B2))
                ):
                    connector.add(u)
                    break

        lonely = ungrouped - connector
        if not lonely:
            break

        new_pairs, used = set(), set()
        for A, B in (tuple(pr) for pr in stripe_pairs):
            cand_A = [r for r in reds_adjacent_to(A, lonely) if r not in used]
            cand_B = [r for r in reds_adjacent_to(B, lonely) if r not in used]
            for r1 in cand_A:
                for r2 in cand_B:
                    if is_parallel(r1, r2):
                        new_pairs.add(frozenset({r1, r2}))
                        used.update({r1, r2})
                        break
                if r1 in used:
                    break
        if new_pairs:
            stripe_pairs |= new_pairs
            continue
        break  # stuck

    # 19 → 21 → 22 ─ Build mid-point skeletons and merge overlaps ------------
    def dist(P, Q):
        return math.hypot(P[0] - Q[0], P[1] - Q[1])

    connector_lines, midpoint_lines = [], []
    for idxA, idxB in (tuple(pr) for pr in stripe_pairs):
        A1, A2 = endpts[idxA]
        B1, B2 = endpts[idxB]
        L1 = dist(A1, B1) + dist(A2, B2)
        L2 = dist(A1, B2) + dist(A2, B1)
        conns = [(A1, B1), (A2, B2)] if L1 <= L2 else [(A1, B2), (A2, B1)]
        connector_lines.extend(conns)
        mids = [((P[0] + Q[0]) / 2, (P[1] + Q[1]) / 2) for P, Q in conns]
        midpoint_lines.append(tuple(mids))

    # align onto best-fit axes  (sections 20-20·5, abbreviated)
    ANG_TOL_ALIGN = 3.0
    SHIFT_TOL_RATIO = 0.02
    med_link_len = np.median([dist(*l) for l in midpoint_lines])
    POINT_JOIN_TOL = 0.005 * med_link_len

    violet_xy = [np.array(l) for l in midpoint_lines]
    violet_dir = [unit(p2 - p1) for p1, p2 in violet_xy]
    violet_len = [np.linalg.norm(p2 - p1) for p1, p2 in violet_xy]
    violet_mid = [(p1 + p2) / 2 for p1, p2 in violet_xy]
    violet_ang = [
        (math.degrees(math.atan2(*(b - a)[::-1])) % 180) for a, b in violet_xy
    ]

    parent = list(range(len(violet_xy)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        a, b = find(i), find(j)
        if a != b:
            parent[b] = a

    def perp_dist(P, A, v_hat):
        return abs((P - A)[0] * v_hat[1] - (P - A)[1] * v_hat[0])

    for i in range(len(violet_xy)):
        for j in range(i + 1, len(violet_xy)):
            dang = abs(violet_ang[i] - violet_ang[j])
            dang = dang if dang <= 90 else 180 - dang
            if dang > ANG_TOL_ALIGN:
                continue
            gap = perp_dist(violet_mid[i], violet_xy[j][0], violet_dir[j])
            if gap <= SHIFT_TOL_RATIO * max(violet_len[i], violet_len[j]):
                union(i, j)

    clusters = defaultdict(list)
    for idx in range(len(violet_xy)):
        clusters[find(idx)].append(idx)

    cluster_axis = {}
    for root, members in clusters.items():
        if len(members) == 1:
            p1, p2 = violet_xy[members[0]]
            axis_v = unit(p2 - p1)
            if axis_v[0] < 0:
                axis_v = -axis_v
            cluster_axis[root] = (p1, axis_v)
        else:
            P = np.vstack([violet_xy[m] for m in members])
            ctr = P.mean(axis=0)
            axis_v = unit(np.linalg.svd(P - ctr)[2][0])
            if axis_v[0] < 0:
                axis_v = -axis_v
            cluster_axis[root] = (ctr, axis_v)

    aligned_links = []
    for idx, (P, Q) in enumerate(violet_xy):
        anchor, v_hat = cluster_axis[find(idx)]
        P_proj = anchor + np.dot(P - anchor, v_hat) * v_hat
        Q_proj = anchor + np.dot(Q - anchor, v_hat) * v_hat
        if np.dot(Q_proj - P_proj, v_hat) < 0:
            P_proj, Q_proj = Q_proj, P_proj
        aligned_links.append((tuple(P_proj), tuple(Q_proj)))

    def weld(seglist, tol=POINT_JOIN_TOL):
        uniques = []

        def canon(pt):
            for c in uniques:
                if math.hypot(*(pt - c)) <= tol:
                    return c
            uniques.append(pt)
            return pt

        out = []
        for A, B in seglist:
            a = canon(np.array(A))
            b = canon(np.array(B))
            out.append((tuple(a), tuple(b)))
        return out

    aligned_links = weld(aligned_links)

    # 20·6 – merge overlapping/touching on same axis
    unified_links = []
    OVERLAP_TOL = POINT_JOIN_TOL
    for root, members in clusters.items():
        anchor, v_hat = cluster_axis[root]
        intervals = []
        for idx in members:
            P, Q = aligned_links[idx]
            s1 = np.dot(np.array(P) - anchor, v_hat)
            s2 = np.dot(np.array(Q) - anchor, v_hat)
            if s1 > s2:
                s1, s2 = s2, s1
            intervals.append((s1, s2))
        intervals.sort(key=lambda iv: iv[0])
        merged = []
        cur_a, cur_b = intervals[0]
        for a, b in intervals[1:]:
            if a <= cur_b + OVERLAP_TOL:
                cur_b = max(cur_b, b)
            else:
                merged.append((cur_a, cur_b))
                cur_a, cur_b = a, b
        merged.append((cur_a, cur_b))
        for s0, s1 in merged:
            P = anchor + s0 * v_hat
            Q = anchor + s1 * v_hat
            unified_links.append((tuple(P), tuple(Q)))

    unified_links = weld(unified_links)

    # ───────────────────────────── polygonise rooms ─────────────────────────
    try:
        from shapely.geometry import LineString
        from shapely.ops import polygonize
    except (ImportError, OSError):
        # Shapely not present (or GEOS missing) – return nothing
        return []

    line_strings = [LineString([P, Q]) for P, Q in unified_links if P != Q]
    polys = list(polygonize(line_strings))
    rooms = []
    for poly in polys:
        if not poly.is_valid or poly.area < 1e-3:
            continue
        minx, miny, maxx, maxy = poly.bounds
        rooms.append({"bbox": [minx, miny, maxx - minx, maxy - miny]})

    return rooms
