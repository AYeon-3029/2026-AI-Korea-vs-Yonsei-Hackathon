"""Bounded tactical rollout; no imports from the offline game engine.

Own W follow their already assigned goals. Opponent policies are scenarios,
not probabilities. Only the candidate building changes ownership; other
fronts and future TELE are deliberately outside this local model.
"""


def combat(w, f, owner, target):
    """Mutate two teams' cell counts; return owner and W/F casualties."""
    losses = [[0, 0], [0, 0]]
    for cell in w[0].keys() | w[1].keys():
        killed = min(w[0].get(cell, 0), w[1].get(cell, 0))
        for side in (0, 1):
            w[side][cell] = w[side].get(cell, 0) - killed
            losses[side][0] += killed
        for side in (0, 1):
            victim = 1 - side
            if w[side][cell] > 0 and f[victim].get(cell, 0):
                losses[victim][1] += f[victim].pop(cell)
                if cell == target and owner == victim:
                    owner = -1
    return owner, losses


def capture(owner, flags, resource, costs):
    """One capture stage, including contention and affordability."""
    if bool(flags[0]) == bool(flags[1]):
        return owner
    side = 0 if flags[0] else 1
    if owner != side and resource[side] >= costs[side]:
        resource[side] -= costs[side]
        return side if owner == -1 else -1
    return owner


def rollout(geo, target, actor, first, groups, my_f, en_w, en_f,
            resource, income, costs, cap_costs, spawns, owner, btype,
            worth, horizon, policy, wait=False, economy=None):
    """Return explicit outcomes of one response scenario.

    groups: (first-turn destination, assigned W goal, count). Dead soldiers
    are removed from these groups before the next movement. The actor's
    first step comes from the real safe()/path selector.
    """
    def step(cell, goal, enemy=False):
        if cell == goal:
            return cell
        options = [v for _, v in geo.nbrs[cell] if geo.dist[v][goal] < geo.dist[cell][goal]]
        return min(options, key=lambda v: -geo.nkey(v) if enemy else geo.nkey(v), default=cell)

    def moved(table, goal, enemy=False):
        out = {}
        for cell, n in table.items():
            if n:
                dest = step(cell, goal, enemy)
                out[dest] = out.get(dest, 0) + n
        return out

    initial_owner = owner
    resource, income, costs, cap_costs = map(list, (resource, income, costs, cap_costs))
    spawns = [list(s) for s in spawns]
    eng = list(economy["eng"]) if economy else None
    lib = list(economy["lib"]) if economy else None
    depot = list(economy["depot"]) if economy else [True, True]
    groups = list(groups)
    # ponytail: local continuation freezes other F and other buildings;
    # full-board policy rollout is needed before claiming global prediction.
    f = [dict(my_f), dict(en_f)]
    f[0][actor] -= 1
    actor_cell = actor
    ew = dict(en_w)
    casualties = [[0, 0], [0, 0]]
    gain = 0.0
    held = 0
    first_capture = None
    for turn in range(horizon):
        # Allocate half of future income to this front, with one shared
        # budget per side. Our first-turn production is already in groups.
        for side in (0, 1):
            if (turn == 0 and side == 0) or (side == 1 and policy == "hold"):
                continue
            choices = [s for s in spawns[side] if geo.dist[s][target] <= horizon - turn]
            if not choices:
                continue
            source = min(choices, key=lambda s: (geo.dist[s][target],
                         geo.nkey(s) if side == 0 else -geo.nkey(s)))
            n = max(0, min(resource[side] - cap_costs[side], income[side] // 2)) // costs[side]
            resource[side] -= n * costs[side]
            if n:
                if side == 0:
                    groups.append((source, target, n))
                else:
                    ew[source] = ew.get(source, 0) + n
        # Opponent acts on the pre-movement actor position (simultaneous turns).
        enemy_goal = actor_cell if policy == "hunt" and actor_cell is not None else target
        if policy != "hold":
            ew = moved(ew, enemy_goal, True)
            f[1] = moved(f[1], target, True)
        if turn:
            groups = [(step(cell, goal), goal, n) for cell, goal, n in groups]
        w0 = {}
        for cell, _, n in groups:
            w0[cell] = w0.get(cell, 0) + n
        if actor_cell is not None:
            dest = actor if wait == "hold" or (turn == 0 and wait) else first if turn == 0 else step(actor_cell, target)
            actor_cell = dest
            f[0][dest] = f[0].get(dest, 0) + 1
        w = [w0, ew]
        before = owner
        owner, loss = combat(w, f, owner, target)
        for side in (0, 1):
            for kind in (0, 1):
                casualties[side][kind] += loss[side][kind]
        if actor_cell is not None:
            if f[0].get(actor_cell, 0):
                f[0][actor_cell] -= 1
            else:
                actor_cell = None
        survivors = dict(w[0])
        kept = []
        for cell, goal, n in groups:
            n = min(n, survivors.get(cell, 0))
            survivors[cell] = survivors.get(cell, 0) - n
            if n:
                kept.append((cell, goal, n))
        groups, ew = kept, {c: n for c, n in w[1].items() if n}
        # Combat neutralization changes HALL income before capture.
        def update_effect(old, new):
            if old == new:
                return
            if btype == "HALL":
                for side in (0, 1):
                    income[side] += 2 * ((new == side) - (old == side))
            for side in (0, 1):
                change = (new == side) - (old == side)
                if btype == "ENG" and eng is not None:
                    eng[side] += change
                    costs[side] = max(2, 3 - eng[side])
                if btype == "LIBRARY" and lib is not None:
                    lib[side] += change
                    cap_costs[side] = max(1, 2 - bool(lib[side]))
                if btype == "HOSPITAL":
                    if old == side and target in spawns[side]:
                        spawns[side].remove(target)
                    if new == side and target not in spawns[side]:
                        spawns[side].append(target)
        update_effect(before, owner)
        resource = [min(40, r + inc) for r, inc in zip(resource, income)]
        before = owner
        owner = capture(owner, [f[0].get(target, 0) + (actor_cell == target),
                                f[1].get(target, 0)], resource, cap_costs)
        update_effect(before, owner)
        if btype == "DEPOT" and owner >= 0 and not depot[owner]:
            depot[owner] = True
            resource[owner] = min(40, resource[owner] + 15)
        held += owner == 0
        if owner == 0 and first_capture is None:
            first_capture = turn + 1
        # Temporary ownership and denial both earn value; no binary hold filter.
        gain += worth * ((owner == 0) - (owner == 1) + (initial_owner == 1))
    return {"gain": gain / horizon, "held": held, "capture_turn": first_capture,
            "owner": owner, "losses": casualties, "actor_alive": actor_cell is not None}
