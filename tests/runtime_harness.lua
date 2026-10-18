-- API doubles deliberately use only Lua 5.1 and the DCS mission sandbox APIs.
local source = assert(arg[1], "Pass the runtime.lua path")
local cases = {}

local function newWorld(configuration)
    IRON_ANVIL = configuration
    local data = {groups = {}, statics = {}, flags = {}, messages = {}, activated = {}, menus = {}, now = 0}
    function data.unit(name, player, point)
        local unit = {name = name, life = 100, player = player, flying = false, point = point or {x=0, y=0, z=0}}
        function unit:isExist() return self.life > 0 end
        function unit:getLife() return self.life end
        function unit:getName() return self.name end
        function unit:getPlayerName() return self.player end
        function unit:inAir() return self.flying end
        function unit:getPoint() return self.point end
        function unit:getGroup() return self.owner end
        return unit
    end
    function data.group(name, count, player)
        local group = {name = name, all = {}, tasks = {}, commands = {}}
        function group:isExist() return true end
        function group:getName() return self.name end
        function group:getUnits() return self.all end
        function group:getController() return self end
        function group:setTask(task) self.tasks[#self.tasks + 1] = task end
        function group:setCommand(command) self.commands[#self.commands + 1] = command end
        function group:setOnOff(value) self.on = value end
        for index = 1, count do
            local unit = data.unit(name .. index, player)
            unit.owner = group
            group.all[#group.all + 1] = unit
        end
        data.groups[name] = group
        return group
    end
    coalition = {side = {BLUE = 2}}
    Group = {
        getByName = function(name) return data.groups[name] end,
        activate = function(group) data.activated[group.name] = (data.activated[group.name] or 0) + 1 end,
    }
    StaticObject = {getByName = function(name) return data.statics[name] end}
    trigger = {action = {
        outTextForCoalition = function(_, text) data.messages[#data.messages + 1] = text end,
        setUserFlag = function(name, value) data.flags[name] = value end,
        markToCoalition = function(_, _, point) data.mark = point end,
        removeMark = function() data.removedMark = true end,
    }}
    env = {info = function() end}
    missionCommands = {
        addSubMenuForCoalition = function() return {} end,
        addCommandForCoalition = function(_, name, _, action) data.menus[name] = action end,
    }
    land = {
        getHeight = function() return 0 end,
        getClosestPointOnRoads = function(_, x, z) return x + 10, z + 10 end,
        findPathOnRoads = function(_, x, z, dx, dz) return {{x=x, y=z}, {x=dx, y=dz}} end,
    }
    coord = {
        LOtoLL = function() return 42, 43 end,
        LLtoMGRS = function() return {UTMZone="38T", MGRSDigraph="MN", Easting=1, Northing=2} end,
    }
    world = {
        event = {S_EVENT_TAKEOFF=3, S_EVENT_LAND=4, S_EVENT_CRASH=5, S_EVENT_EJECTION=6,
                 S_EVENT_DEAD=8, S_EVENT_PILOT_DEAD=9, S_EVENT_BIRTH=15},
        addEventHandler = function(handler) data.handler = handler end,
    }
    timer = {getTime = function() return data.now end, scheduleFunction = function(fn) data.tick = fn end}
    function data.start() assert(loadfile(source))() end
    function data.advance(count)
        for _ = 1, (count or 1) do
            data.now = data.now + 5
            assert(data.tick(nil, data.now) == data.now + 5)
        end
    end
    function data.takeoff(unit)
        unit.flying = true
        data.handler:onEvent({id=3, initiator=unit})
    end
    function data.land(unit, name, side)
        unit.flying = false
        local place
        if name then place = {getName=function() return name end, getCoalition=function() return side end} end
        data.handler:onEvent({id=4, initiator=unit, place=place})
    end
    function data.lose(unit)
        unit.life = 0
        data.handler:onEvent({id=5, initiator=unit})
    end
    return data
end

local function base(kind)
    return {
        mission_type=kind, player_group="players", base_name="Home", home={x=0, z=0},
        target={x=5000, z=5000}, target_groups={"target"}, cap_groups={"enemycap"}, enemy_cap=true,
    }
end

function cases.ground_objective_and_friendly_recovery()
    local data = newWorld(base("facility"))
    local player = data.group("players", 1, "Pilot").all[1]
    local targets = data.group("target", 2)
    data.group("enemycap", 2)
    data.start()
    data.advance()
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE, "grounded clients cannot complete objectives")
    data.takeoff(player)
    targets.all[1].life = 0
    data.advance()
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE, "every target must be destroyed")
    -- DCS can remove a destroyed group from its lookup table entirely.
    data.groups.target = nil
    data.advance()
    assert(data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE == 1, "destroyed ground objective completes")
    data.land(player, "Other", 2)
    assert(not data.flags.IRON_ANVIL_MISSION_COMPLETE, "wrong base must be rejected")
    data.land(player, "Home", 1)
    assert(not data.flags.IRON_ANVIL_MISSION_COMPLETE, "hostile base must be rejected")
    data.land(player, "Home", 2)
    assert(data.flags.IRON_ANVIL_MISSION_COMPLETE == 1, "friendly home recovery must complete")
    assert(data.flags.IRON_ANVIL_RESULT == 1, "success result flag must be 1")
    local announcements = #data.messages
    data.land(player, "Home", 2)
    assert(#data.messages == announcements, "completion must be idempotent")
end

function cases.cap_activation_and_defeat()
    local data = newWorld(base("cap"))
    local player = data.group("players", 1, "Pilot").all[1]
    local cap = data.group("enemycap", 2)
    data.start()
    assert(not data.activated.enemycap, "CAP must not launch before clients")
    data.takeoff(player)
    data.advance()
    assert(data.activated.enemycap == 1, "CAP launches once")
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE, "living enemy CAP blocks completion")
    cap.all[1].life = 0
    data.advance()
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE, "all enemy aircraft must be defeated")
    cap.all[2].life = 0
    data.advance()
    assert(data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE == 1, "defeated CAP completes objective")
    data.land(player, "Home", 2)
    assert(data.flags.IRON_ANVIL_MISSION_COMPLETE == 1)
end

function cases.cap_disabled_station_time()
    local config = base("cap")
    config.enemy_cap, config.station_seconds, config.station_radius = false, 15, 1000
    local data = newWorld(config)
    local player = data.group("players", 1, "Pilot").all[1]
    data.start()
    data.takeoff(player)
    data.advance(5)
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE, "time outside station cannot count")
    player.point = {x=5000, y=1000, z=5000}
    data.advance()
    player.flying = false
    data.advance(5)
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE, "grounded time cannot count")
    player.flying = true
    data.advance(2)
    assert(data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE == 1, "time on station completes CAP without enemies")
    assert(not data.activated.enemycap, "disabled CAP cannot activate")
end

function cases.convoy_hold_and_road_routing()
    local config = base("convoy")
    config.convoy_group, config.convoy_destination = "target", {x=15000, z=15000}
    local data = newWorld(config)
    local player = data.group("players", 1, "Pilot").all[1]
    local convoy = data.group("target", 2)
    data.group("enemycap", 2)
    data.start()
    assert(convoy.commands[1].params.value == true, "convoy must start held")
    data.advance(10)
    assert(#convoy.commands == 1, "convoy cannot depart without clients")
    data.takeoff(player)
    assert(convoy.commands[2].params.value == false, "first client releases convoy")
    local points = convoy.tasks[1].params.route.points
    assert(#points == 4 and points[2].action == "On Road", "convoy follows road path")
    assert(points[2].x == 10 and points[2].y == 10, "DCS z must become route y")
    assert(points[4].x == 15000 and points[4].y == 15000)
    data.advance(4)
    assert(#convoy.tasks == 1, "convoy route must not reset each tick")
end

function cases.convoy_road_fallbacks()
    for _, mode in ipairs({"missing_path", "missing_roads"}) do
        local config = base("convoy")
        config.enemy_cap = false
        config.convoy_group, config.convoy_destination = "target", {x=10000, z=10000}
        local data = newWorld(config)
        local player = data.group("players", 1, "Pilot").all[1]
        local convoy = data.group("target", 1)
        if mode == "missing_path" then land.findPathOnRoads = function() error("unavailable") end else land = nil end
        data.start()
        data.takeoff(player)
        local points = convoy.tasks[1].params.route.points
        if mode == "missing_path" then
            assert(#points == 4 and points[2].action == "On Road", "road endpoints permit DCS routing fallback")
        else
            assert(#points == 2 and points[2].action == "Off Road", "missing roads permit direct fallback")
        end
    end
end

function cases.f10_current_target_position()
    local config = base("convoy")
    config.convoy_group = "target"
    local data = newWorld(config)
    local convoy = data.group("target", 1)
    data.start()
    assert(data.menus["Mission status"] and data.menus["Target position / mark"])
    convoy.all[1].point = {x=777, y=15, z=888}
    data.menus["Target position / mark"]()
    assert(data.mark.x == 777 and data.mark.z == 888, "marker must track moving convoy")
    assert(string.find(data.messages[#data.messages], "38T MN 00001 00002", 1, true), "position must include MGRS")
    assert(data.removedMark, "old objective marker must be replaced")
    data.menus["Mission status"]()
    assert(string.find(data.messages[#data.messages], "1 targets remaining", 1, true))
    local player = data.group("players", 1, "Pilot").all[1]
    player.point = {x=0, y=1000, z=0}
    data.menus["Target bearing / range"]()
    assert(string.find(data.messages[#data.messages], "range", 1, true))
    data.menus["Vector home"]()
    assert(string.find(data.messages[#data.messages], "Home bearing", 1, true))
end

function cases.air_start_and_human_client_filter()
    local config = base("facility")
    local data = newWorld(config)
    local ai = data.group("players", 1).all[1]
    local otherPlayer = data.group("other", 1, "Other").all[1]
    data.group("enemycap", 1)
    data.group("target", 1)
    data.start()
    data.takeoff(ai)
    data.takeoff(otherPlayer)
    data.advance()
    assert(not data.activated.enemycap, "AI or unrelated players cannot start mission")
    -- Air starts do not always emit takeoff events: polling must detect them.
    ai.player, ai.flying = "Pilot", true
    data.advance()
    assert(data.activated.enemycap == 1, "airborne client must start controller without takeoff event")
    data.groups.target = nil
    data.advance()
    ai.point = {x=100000, y=0, z=100000}
    data.land(ai)
    assert(not data.flags.IRON_ANVIL_MISSION_COMPLETE, "place-less landing away from home cannot count")
    ai.point = {x=100, y=0, z=100}
    data.land(ai)
    assert(data.flags.IRON_ANVIL_MISSION_COMPLETE == 1, "place-less home landing permits recovery")
end

function cases.static_objectives_and_empty_configuration()
    local config = base("facility")
    config.target_groups, config.target_statics, config.enemy_cap = {}, {"bunker"}, false
    local data = newWorld(config)
    local player = data.group("players", 1, "Pilot").all[1]
    data.statics.bunker = data.unit("bunker")
    data.start()
    data.takeoff(player)
    data.advance()
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE, "living static blocks objective")
    data.statics.bunker.life = 0
    data.advance()
    assert(data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE == 1)
    data = newWorld({})
    data.start()
    data.advance(5)
    data.menus["Mission status"]()
    data.menus["Target position / mark"]()
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE, "empty configuration cannot falsely complete")
end

local function twoClientWorld()
    local config = base("facility")
    config.enemy_cap = false
    local data = newWorld(config)
    local players = data.group("players", 2, "Pilot")
    data.group("target", 1)
    data.start()
    return data, players.all[1], players.all[2]
end

local function clearObjective(data)
    data.groups.target = nil
    data.advance()
    assert(data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE == 1)
end

function cases.all_surviving_clients_must_recover()
    local data, first, second = twoClientWorld()
    data.takeoff(first)
    data.takeoff(second)
    clearObjective(data)
    data.land(first, "Home", 2)
    assert(not data.flags.IRON_ANVIL_MISSION_COMPLETE, "first landing cannot win while second survivor is airborne")
    assert(not data.flags.IRON_ANVIL_RESULT, "no result while a survivor remains airborne")
    data.land(second, "Home", 2)
    assert(data.flags.IRON_ANVIL_RESULT == 1, "all survivors home must win")
    assert(data.flags.IRON_ANVIL_MISSION_COMPLETE == 1)
end

function cases.joined_idle_client_must_fly_and_return()
    local data, first, second = twoClientWorld()
    data.takeoff(first)
    clearObjective(data)
    data.land(first, "Home", 2)
    assert(not data.flags.IRON_ANVIL_RESULT, "joined client parked since start must prevent win")
    data.advance(3)
    assert(not data.flags.IRON_ANVIL_RESULT, "parked clients cannot count as recovered")
    data.takeoff(second)
    data.land(second, "Home", 2)
    assert(data.flags.IRON_ANVIL_RESULT == 1, "idle client must fly and then recover")
end

function cases.loss_excludes_dead_client_from_recovery()
    local data, first, second = twoClientWorld()
    data.takeoff(first)
    data.takeoff(second)
    clearObjective(data)
    data.land(first, "Home", 2)
    assert(not data.flags.IRON_ANVIL_RESULT)
    data.lose(second)
    assert(data.flags.IRON_ANVIL_RESULT == 1, "loss of last airborne client permits surviving recovery win")
    assert(data.flags.IRON_ANVIL_MISSION_COMPLETE == 1)
end

function cases.all_clients_lost_fails_mission()
    local data, first, second = twoClientWorld()
    data.takeoff(first)
    data.takeoff(second)
    data.lose(first)
    assert(not data.flags.IRON_ANVIL_RESULT, "one surviving client prevents total loss")
    -- Tick-based polling must detect a lost client when DCS omits death events.
    second.life = 0
    data.advance()
    assert(data.flags.IRON_ANVIL_RESULT == 2, "total client loss must set failure result 2")
    assert(not data.flags.IRON_ANVIL_MISSION_COMPLETE, "failure cannot set successful completion flag")
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE)
    data.menus["Mission status"]()
    assert(string.find(data.messages[#data.messages], "Mission failed", 1, true))
end

function cases.birth_registers_late_joined_client()
    local config = base("facility")
    config.enemy_cap, config.player_groups = false, {"players", "late"}
    local data = newWorld(config)
    local first = data.group("players", 1, "Pilot").all[1]
    data.group("target", 1)
    data.start()
    data.takeoff(first)
    clearObjective(data)
    local late = data.group("late", 1, "Late Pilot").all[1]
    data.handler:onEvent({id=15, initiator=late})
    data.land(first, "Home", 2)
    assert(not data.flags.IRON_ANVIL_RESULT, "late joined parked client must join recovery roster")
    data.takeoff(late)
    data.land(late, "Home", 2)
    assert(data.flags.IRON_ANVIL_RESULT == 1)
end

local selected = arg[2]
if selected then
    assert(cases[selected], "Unknown runtime case: " .. selected)()
    print("PASS: " .. selected)
else
    for name, check in pairs(cases) do check(); print("PASS: " .. name) end
end
