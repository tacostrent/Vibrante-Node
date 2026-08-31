def calculate_components(length, angle_deg):
    import math

    angle_rad = math.radians(angle_deg)
    horizontal = length * math.cos(angle_rad)
    vertical = length * math.sin(angle_rad)

    return horizontal, vertical