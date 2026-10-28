"""Parameterized shared towers, a double-supported arch and SNOT lamps."""

from brickagent import Assembly, UP, spin
from legoworld.build import expose_port, require_contact, get_port


def tower(courses=4):
    model = Assembly("watchtower")
    floor = model.add("3031", color="dark bluish gray")
    expose_port(model, "bottom", floor.hole[0])
    last = []
    for x in (-30, -10, 10, 30):
        for z in (-30, -10, 10, 30):
            if abs(x) != 30 and abs(z) != 30:
                continue
            support = floor.stud.near((x, 0, z))
            for _ in range(courses):
                brick = model.attach("3005", to=support, by=("hole", 0), color="tan")
                support = brick.stud[0]
            last.append(brick)
    cap = model.attach("3031", to=last[0].stud[0], by=("hole", 0), color="dark bluish gray")
    # Choose by position so geometry is independent of the catalog's index ordering.
    roof = model.attach("3941", to=cap.stud.near((-10, cap.pose.t[1], -10)), by=("hole", 0), color="tan")
    roof = model.attach("3942c", to=roof.stud[0], by=("hole", 0), color="dark red")
    tip = model.attach("6141", to=roof.open[0], by=("tube", 0), color="yellow")
    model.attach("4589", to=tip.stud[0], by=("tube", 0), color="dark red")
    holder = model.attach("87087", to=cap.stud.near((-30, cap.pose.t[1], -30)), by=("hole", 0), color="dark bluish gray")
    model.attach("6141", to=holder.open[0], by=("tube", 0), color="yellow")
    return model


def wall():
    model = Assembly("curtain_wall")
    brick = model.add("3010", color="tan")
    expose_port(model, "bottom", brick.hole[0])
    for _ in range(2):
        brick = model.attach("3010", to=brick.stud[0], by=("hole", 0), color="tan")
    cap = model.attach("3710", to=brick.stud[0], by=("hole", 0), color="dark bluish gray")
    for x in (-30, 10):
        model.attach("3005", to=cap.stud.near((x, cap.pose.t[1], 0)), by=("hole", 0), color="tan")
    return model


def gate():
    from brickagent import move
    model = Assembly("arched_gate")
    left = model.add("3005", pose=move(-30, 0, 0), color="tan")
    right = model.add("3005", pose=move(30, 0, 0), color="tan")
    expose_port(model, "bottom", left.hole[0])
    arch = model.attach("3659", to=left.stud[0], by=("hole", 0), color="tan")
    require_contact(model, arch.hole[-1], right.stud[0])
    cap = model.attach("3710", to=arch.stud[0], by=("hole", 0), color="dark bluish gray")
    for c in (cap.stud[0], cap.stud[-1]):
        model.attach("3005", to=c, by=("hole", 0), color="tan")
    return model


def build(courses=4):
    if not 1 <= courses <= 8:
        raise ValueError("courses must be 1..8")
    from brickagent import move
    model = Assembly("v3_modular_castle")
    plates = [model.add("3031", pose=move(x, 0, z), color="sand green")
              for x in (-120, -40, 40, 120) for z in (-120, -40, 40, 120)]
    studs = [c for plate in plates for c in plate.stud]

    def place(component, x, z, yaw=0):
        port = get_port(component, "bottom")
        rotation = spin(UP, yaw)
        offset = rotation.dir(port.at)
        point = (x + offset[0], 0, z + offset[2])
        target = min(studs, key=lambda c: sum((a-b)**2 for a, b in zip(c.at, point)))
        return model.attach(component, to=target, by=port, orient=rotation)

    unit = tower(courses)
    for x, z in ((-80, -80), (80, -80), (-80, 80), (80, 80)):
        place(unit, x, z)
    unit = wall()
    place(unit, 0, 90)
    place(unit, -90, 0, 90)
    place(unit, 90, 0, 90)
    place(gate(), 0, -90)
    return model
