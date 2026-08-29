"""
Mathematical utilities for bezier curves and trajectory calculations
"""

import math
import numpy as np

from PyQt6.QtCore import QPointF


class MathUtils:
    """Mathematical utilities for physics and animation"""

    @staticmethod
    def quadratic_bezier_through_point(P0, Pmid, P2, tm=0.5):
        """Returns a function B(t) for a quadratic Bézier that passes through Pmid at t=tm."""
        P0 =   np.asarray(P0, dtype=float)
        Pmid = np.asarray(Pmid, dtype=float)
        P2 =   np.asarray(P2, dtype=float)

        if not (0 < tm < 1):
            raise ValueError("tm must be strictly between 0 and 1")

        u = 1 - tm
        denom = 2 * u * tm
        if abs(denom) < 1e-12:
            raise ValueError("tm too close to 0 or 1")

        P1 = (Pmid - (u * u) * P0 - (tm * tm) * P2) / denom

        def B(t):
            t = np.asarray(t, dtype=float)
            u = 1 - t
            return (u * u)[:, None] * P0 + (2 * u * t)[:, None] * P1 + (t * t)[:, None] * P2
        return B, P1

    @staticmethod
    def _simpson_integral(f, a=0.0, b=1.0, n=1000):
        """Simpson's rule for numerical integration, n must be even."""
        if n % 2 == 1:
            n += 1
        x = np.linspace(a, b, n + 1)
        y = f(x)
        h = (b - a) / n
        return (h / 3) * (y[0] + y[-1] + 4 * y[1:-1:2].sum() + 2 * y[2:-1:2].sum())

    @staticmethod
    def quadratic_length(P0, P1, P2, n=2000):
        """Calculate arc length of a quadratic Bezier curve."""
        P0 = np.asarray(P0, float)
        P1 = np.asarray(P1, float)
        P2 = np.asarray(P2, float)

        def speed(t):
            t = np.asarray(t, float)
            d = 2 * (1 - t)[:, None] * (P1 - P0) + 2 * t[:, None] * (P2 - P1)
            return np.linalg.norm(d, axis=1)

        return float(MathUtils._simpson_integral(speed, 0.0, 1.0, n=n))

    @staticmethod
    def calculate_jump_trajectory(start_x, start_y, peak_x, peak_y, end_x, end_y, speed):
        """Calculate jump trajectory points for animation while keeping a constant speed."""
        P0      = (start_x, start_y)
        Pmid    = (peak_x, peak_y)
        P2      = (end_x, end_y)
        B, P1   = MathUtils.quadratic_bezier_through_point(P0, Pmid, P2, tm=0.5)
        L2      = MathUtils.quadratic_length(P0, P1, P2, n=2000)

        T       = 1 * (L2 / (speed * 1800)) ** 0.4
        Steps   = math.floor(T * 30)
        dt      = T / Steps
        ts = np.linspace(0, 1, Steps)
        points  = B(ts)

        return points, Steps, dt

    @staticmethod
    def calculate_orbit_path_cords(distance_traveled_px, start_x, start_y, end_x, end_y, radius, angle_deg, approach_side):
        """Calculates the x, y position along a path(for a certain % along the path) that starts at point a and orbits point b at a radius to hit it from a certain angle.
        Requires a percentage through the path, start and end points, orbit radius, and final arrival angle."""

        cx, cy = end_x, end_y
        sx, sy = start_x, start_y
        r = radius

        exit_angle = math.radians(angle_deg)
        final_entry_x = cx + r * math.cos(exit_angle)
        final_entry_y = cy + r * math.sin(exit_angle)

        h = math.hypot(cx - sx, cy - sy)
        gamma = math.atan2(cy - sy, cx - sx)

        is_in_view = math.cos(exit_angle - gamma) < 0 or h <= r

        if is_in_view:
            entry_x = final_entry_x
            entry_y = final_entry_y
            entry_angle = exit_angle
            l1 = math.hypot(entry_x - sx, entry_y - sy)
            l2 = 0.0
            l3 = r
            arc_diff = 0.0
        else:
            alpha = math.asin(r / h) if h > r else 0.0

            def shortest_arc_diff(a_start, a_end):
                diff = (a_end - a_start + math.pi) % (2 * math.pi) - math.pi
                return diff

            entry_angle_cw  = gamma + math.pi / 2 + alpha
            entry_angle_ccw = gamma - math.pi / 2 - alpha
            diff_cw  = shortest_arc_diff(entry_angle_cw, exit_angle)
            diff_ccw = shortest_arc_diff(entry_angle_ccw, exit_angle)
            if approach_side is None:
                approach_side = abs(diff_cw) <= abs(diff_ccw)

            if approach_side:
                entry_angle = entry_angle_cw
                arc_diff = diff_cw
            else:
                entry_angle = entry_angle_ccw
                arc_diff = diff_ccw

            entry_x = cx + r * math.cos(entry_angle)
            entry_y = cy + r * math.sin(entry_angle)

            l1 = math.sqrt(max(0.0, h * h - r * r))
            l2 = abs(arc_diff) * r
            l3 = r

        total = l1 + l2 + l3
        d = min(total, distance_traveled_px)
        overflow = distance_traveled_px > total

        # Seg 1: start to entry point
        if d <= l1:
            t = d / l1 if l1 > 0 else 1.0
            x = sx + (entry_x - sx) * t
            y = sy + (entry_y - sy) * t
            return x, y, overflow, approach_side, distance_traveled_px / total

        # Seg 2: orbit arc
        if d <= l1 + l2 and l2 > 0:
            orbit_d = d - l1
            t = orbit_d / l2

            # arc_diff already shortest and signed
            current_angle = entry_angle + arc_diff * t
            x = cx + r * math.cos(current_angle)
            y = cy + r * math.sin(current_angle)
            return x, y, overflow, approach_side, distance_traveled_px / total

        # Seg 3: straight to target
        final_d = d - l1 - l2
        t = final_d / l3 if l3 > 0 else 1.0
        x = final_entry_x + (cx - final_entry_x) * t
        y = final_entry_y + (cy - final_entry_y) * t
        return x, y, overflow, approach_side, distance_traveled_px / total

    @staticmethod
    def evaluate_pure_bezier(p0, p1, p2, p3, samples=100):
        """Calculates all points along a cubic Bezier curve in one vectorized operation."""
        pct = np.linspace(0.0, 1.0, samples + 1)[:, None]  # Shape (N, 1)
        mt = 1.0 - pct
        mt2 = mt * mt
        pct2 = pct * pct

        # Fast matrix multiplication on pure numpy arrays
        return (mt2 * mt * p0 +
                3.0 * mt2 * pct * p1 +
                3.0 * mt * pct2 * p2 +
                pct2 * pct * p3)

    @staticmethod
    def compute_side_sweep_geometry_and_durations(a, b, c, speed_a, angle_deg, speed_b, radius):
        """Calculates structural path parameters and kinematic time intervals based on linear acceleration."""
        v_ba = a - b
        v_bc = c - b

        # qpointf dot product acceleration calculation helper
        len_ba = math.sqrt(QPointF.dotProduct(v_ba, v_ba))
        len_bc = math.sqrt(QPointF.dotProduct(v_bc, v_bc))

        u_ba = v_ba / len_ba if len_ba > 0 else QPointF(0, 0)
        u_bc = v_bc / len_bc if len_bc > 0 else QPointF(0, 0)

        max_r = min(len_ba * 0.9, len_bc * 0.9)
        r = min(radius, max_r)

        t_entry = b + u_ba * r
        t_exit = b + u_bc * r

        # Generate bezier control points for the shape
        v_entry = t_entry - a
        shape_weight = math.sqrt(QPointF.dotProduct(v_entry, v_entry)) * 0.4
        rad = math.radians(angle_deg)
        v_initial = QPointF(shape_weight * math.cos(rad), shape_weight * math.sin(rad))

        samples = 150

        p0 = np.array([a.x(), a.y()])
        p1 = np.array([a.x() + v_initial.x(), a.y() + v_initial.y()])
        p2 = np.array([t_entry.x() + u_ba.x() * shape_weight, t_entry.y() + u_ba.y() * shape_weight])
        p3 = np.array([t_entry.x(), t_entry.y()])

        # Generate all positions at once
        seg1_points = MathUtils.evaluate_pure_bezier(p0, p1, p2, p3, samples)

        # Compute distances between sequential coordinate points via matrix operations
        deltas = np.diff(seg1_points, axis=0)
        step_distances = np.sqrt(np.sum(np.square(deltas), axis=1))

        # Create your cumulative distance profile lookup table
        seg1_distances = np.zeros(samples + 1)
        seg1_distances[1:] = np.cumsum(step_distances)
        d1 = float(seg1_distances[-1])

        # Corner arc Length
        dot = QPointF.dotProduct(u_ba, u_bc)
        angle_diff = math.acos(max(-1.0, min(1.0, dot)))
        d2 = r * angle_diff

        # straight Exit Distance
        v_exit = c - t_exit
        d3 = math.sqrt(QPointF.dotProduct(v_exit, v_exit))

        # kinematics
        avg_speed_1 = (speed_a + speed_b) * 0.5
        duration_1 = d1 / max(1.0, avg_speed_1)

        # Linear acceleration rate through Segment 1
        accel_1 = (speed_b - speed_a) / duration_1 if duration_1 > 0 else 0.0

        duration_2 = d2 / max(1.0, speed_b)
        duration_3 = d3 / max(1.0, speed_b)

        np_distances = np.array(seg1_distances, dtype=float)
        np_pts = np.array(seg1_points, dtype=float)

        return {
            "seg1_d": np_distances, "seg1_pt": np_pts, "d1": d1, "d2": d2, "d3": d3,
            "duration_1": duration_1, "duration_2": duration_2, "duration_3": duration_3,
            "accel_1": accel_1, "speed_a": speed_a, "t_entry": t_entry, "t_exit": t_exit,
            "u_ba": u_ba, "u_bc": u_bc, "r": r, "c": c, "samples": samples
        }

    @staticmethod
    def get_side_sweep_path_position(t, geo):
        """Evaluates position using physical kinematic profiling."""
        d1_dur = geo["duration_1"]
        d2_dur = geo["duration_2"]
        total_d = d1_dur + d2_dur + geo["duration_3"]

        if t <= 0:
            return geo["seg1_pt"][0], total_d

        elif t <= d1_dur:
            # seg 1: constant Linear Acceleration
            target_dist = (geo["speed_a"] * t) + (0.5 * geo["accel_1"] * t * t)
            target_dist = max(0.0, min(geo["d1"], target_dist))

            # Perform seamless mathematical interpolation over the data arrays
            x_pos = np.interp(target_dist, geo["seg1_d"], geo["seg1_pt"][:, 0])
            y_pos = np.interp(target_dist, geo["seg1_d"], geo["seg1_pt"][:, 1])

            # Return a clean QPointF matching your original design structure
            return QPointF(x_pos, y_pos), total_d

        elif t <= (d1_dur + d2_dur):
            # seg 2: Constant speed corner turn
            local_t = t - d1_dur
            pct = local_t / d2_dur if d2_dur > 0 else 0.0

            # Define the 4 control points for the bezier arc
            q0 = geo["t_entry"]
            q1 = geo["t_entry"] - geo["u_ba"] * (geo["r"] * 0.552)
            q2 = geo["t_exit"] - geo["u_bc"] * (geo["r"] * 0.552)
            q3 = geo["t_exit"]

            # Explicit scalar cubic Bezier evaluation using the actual 'pct' timeline position
            mt = 1.0 - pct
            mt2 = mt * mt
            pct2 = pct * pct

            pos = (mt2 * mt * q0 +
                   3.0 * mt2 * pct * q1 +
                   3.0 * mt * pct2 * q2 +
                   pct2 * pct * q3)
            
            return pos, total_d
        elif t <= total_d:
            # seg 3: Const speed straight line
            local_t = t - d1_dur - d2_dur
            pct = local_t / geo["duration_3"] if geo["duration_3"] > 0 else 0.0
            return geo["t_exit"] + (geo["c"] - geo["t_exit"]) * pct, total_d

        else:
            return geo["c"], total_d
