#!/usr/bin/env python3
"""Deterministic TEST_ONLY stadium-loop motion for the Mission 3 vehicle."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class Pose2:
    x: float
    y: float
    yaw: float
    curvature: float


class StadiumPath:
    """Clockwise stadium: top +X, right turn, bottom -X, left turn."""

    def __init__(self, straight_half_length_m: float, turn_radius_m: float,
                 direction: str = "clockwise"):
        if straight_half_length_m <= 0.0 or turn_radius_m <= 0.0:
            raise ValueError("stadium dimensions must be positive")
        self.half = float(straight_half_length_m)
        self.radius = float(turn_radius_m)
        self.straight_length = 2.0 * self.half
        self.turn_length = math.pi * self.radius
        self.length = 2.0 * (self.straight_length + self.turn_length)
        if direction not in ("clockwise", "counterclockwise"):
            raise ValueError("direction must be clockwise or counterclockwise")
        self.direction = direction

    def pose(self, arc_m: float) -> Pose2:
        s = float(arc_m) % self.length
        if s < self.straight_length:
            pose = Pose2(-self.half + s, self.radius, 0.0, 0.0)
            return pose if self.direction == "clockwise" else Pose2(pose.x,-pose.y,-pose.yaw,-pose.curvature)
        s -= self.straight_length
        if s < self.turn_length:
            theta = math.pi / 2.0 - s / self.radius
            pose = Pose2(self.half + self.radius * math.cos(theta),
                         self.radius * math.sin(theta),
                         theta - math.pi / 2.0, -1.0 / self.radius)
            return pose if self.direction == "clockwise" else Pose2(pose.x,-pose.y,-pose.yaw,-pose.curvature)
        s -= self.turn_length
        if s < self.straight_length:
            pose = Pose2(self.half - s, -self.radius, -math.pi, 0.0)
            return pose if self.direction == "clockwise" else Pose2(pose.x,-pose.y,-pose.yaw,-pose.curvature)
        s -= self.straight_length
        theta = -math.pi / 2.0 - s / self.radius
        pose = Pose2(-self.half + self.radius * math.cos(theta),
                     self.radius * math.sin(theta),
                     theta - math.pi / 2.0, -1.0 / self.radius)
        return pose if self.direction == "clockwise" else Pose2(pose.x,-pose.y,-pose.yaw,-pose.curvature)

    def samples(self, count: int) -> Iterable[Pose2]:
        for i in range(count):
            yield self.pose(self.length * i / count)


