"""
Mathematical utilities for bezier curves and trajectory calculations
"""
import numpy as np
import math


class MathUtils:
    """Mathematical utilities for physics and animation"""
    
    @staticmethod
    def quadratic_bezier_through_point(P0, Pmid, P2, tm=0.5):
        """
        Returns a function B(t) for a quadratic Bézier that passes through Pmid at t=tm.
        
        Args:
            P0: Start point (2D or 3D array-like)
            Pmid: Point to pass through (2D or 3D array-like)
            P2: End point (2D or 3D array-like)
            tm: Time parameter for Pmid (between 0 and 1)
            
        Returns:
            Tuple of (B function, control point P1)
        """
        P0 = np.asarray(P0, dtype=float)
        Pmid = np.asarray(Pmid, dtype=float)
        P2 = np.asarray(P2, dtype=float)

        if not (0 < tm < 1):
            raise ValueError("tm must be strictly between 0 and 1")

        u = 1 - tm
        denom = 2 * u * tm
        if abs(denom) < 1e-12:
            raise ValueError("tm too close to 0 or 1")

        P1 = (Pmid - (u*u)*P0 - (tm*tm)*P2) / denom

        def B(t):
            t = np.asarray(t, dtype=float)
            u = 1 - t
            return (u*u)[:, None]*P0 + (2*u*t)[:, None]*P1 + (t*t)[:, None]*P2

        return B, P1

    @staticmethod
    def simpson_integral(f, a=0.0, b=1.0, n=1000):
        """
        Simpson's rule for numerical integration; n must be even.
        
        Args:
            f: Function to integrate
            a: Start of integration range
            b: End of integration range
            n: Number of segments (will be made even if odd)
            
        Returns:
            Approximation of the integral
        """
        if n % 2 == 1:
            n += 1
        x = np.linspace(a, b, n + 1)
        y = f(x)
        h = (b - a) / n
        return (h/3) * (y[0] + y[-1] + 4*y[1:-1:2].sum() + 2*y[2:-1:2].sum())

    @staticmethod
    def quadratic_length(P0, P1, P2, n=2000):
        """
        Calculate arc length of a quadratic Bézier curve.
        
        Args:
            P0: Start point
            P1: Control point
            P2: End point
            n: Number of segments for integration
            
        Returns:
            Arc length of the curve
        """
        P0 = np.asarray(P0, float)
        P1 = np.asarray(P1, float)
        P2 = np.asarray(P2, float)

        def speed(t):
            t = np.asarray(t, float)
            d = 2*(1-t)[:,None]*(P1-P0) + 2*t[:,None]*(P2-P1)
            return np.linalg.norm(d, axis=1)

        return float(MathUtils.simpson_integral(speed, 0.0, 1.0, n=n))

    @staticmethod
    def calculate_jump_trajectory(start, peak, end, speed, fps=60):
        """
        Calculate jump trajectory points for animation.
        
        Args:
            start: Starting position (x, y)
            peak: Peak of jump (x, y)
            end: Ending position (x, y)
            speed: Jump speed
            fps: Frames per second
            
        Returns:
            Tuple of (trajectory_points, duration_steps)
        """
        P0 = start
        Pmid = peak
        P2 = end
        
        B, P1 = MathUtils.quadratic_bezier_through_point(P0, Pmid, P2, tm=0.5)
        L2 = MathUtils.quadratic_length(P0, P1, P2, n=2000)
        
        T = 0.75 * (L2 / (speed * 1800)) ** 0.4
        Steps = math.floor(T * fps)
        dt = T / Steps
        ts = np.linspace(0, 1, Steps)
        points = B(ts)
        
        return points, Steps, dt
