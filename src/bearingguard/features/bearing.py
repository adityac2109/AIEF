"""Bearing kinematics: characteristic defect frequencies from geometry.

Standard rolling-element bearing kinematics (e.g. Randall & Antoni, "Rolling
element bearing diagnostics - A tutorial", Mechanical Systems and Signal
Processing 25 (2011) 485-520):

    FTF  = fr/2 * (1 - d/D cos a)               cage (fundamental train)
    BPFO = n fr/2 * (1 - d/D cos a)             outer-race defect
    BPFI = n fr/2 * (1 + d/D cos a)             inner-race defect
    BSF  = D/(2d) fr * (1 - (d/D cos a)^2)      rolling-element spin

with shaft frequency fr, n rolling elements per row, element diameter d,
pitch diameter D and contact angle a. Real bearings slip a little, so observed
frequencies deviate by ~1-2% from these values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BearingGeometry:
    n_elements: int
    element_diameter: float  # same length unit as pitch_diameter
    pitch_diameter: float
    contact_angle_deg: float

    def defect_frequencies(self, shaft_hz: float) -> dict[str, float]:
        r = self.element_diameter / self.pitch_diameter * math.cos(math.radians(self.contact_angle_deg))
        return {
            "shaft": shaft_hz,
            "ftf": shaft_hz / 2 * (1 - r),
            "bpfo": self.n_elements * shaft_hz / 2 * (1 - r),
            "bpfi": self.n_elements * shaft_hz / 2 * (1 + r),
            "bsf": self.pitch_diameter / (2 * self.element_diameter) * shaft_hz * (1 - r**2),
        }


# Rexnord ZA-2115 double-row bearing used in the IMS rig. Geometry as compiled
# in https://github.com/hustcxl/Rotating-machine-fault-data-set/blob/master/doc/IMS.md
# (16 rollers per row, d = 0.331 in, D = 2.815 in, contact angle 15.17 deg),
# which lists BPFO 236 Hz, BPFI 297 Hz, BSF 139 Hz, FTF 15 Hz at 2000 RPM.
ZA_2115 = BearingGeometry(n_elements=16, element_diameter=0.331,
                          pitch_diameter=2.815, contact_angle_deg=15.17)
