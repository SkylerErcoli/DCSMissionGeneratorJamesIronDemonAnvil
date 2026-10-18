-- API doubles deliberately use only Lua 5.1 and the DCS mission sandbox APIs.
local source = assert(arg[1], "Pass the runtime.lua path")
local cases = {}

local function newWorld(configuration)
    IRON_ANVIL = configuration
    Airbase = nil
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
    }
    StaticObject = {getByName = function(name) return data.statics[name] end}
    trigger = {action = {
        activateGroup = function(group) data.activated[group.name] = (data.activated[group.name] or 0) + 1 end,
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
    function data.start()
        assert(loadfile(source:gsub('runtime.lua$', 'operations.lua')))()
        assert(loadfile(source))()
    end
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
        mission_type=kind, player_group="players", base_name="Home", home={x=0, z=0}, allow_withdrawal=true,
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

function cases.cap_activation_retries_documented_api()
    local data = newWorld(base("cap"))
    local player = data.group("players", 1, "Pilot").all[1]
    data.group("enemycap", 2)
    local activate = trigger.action.activateGroup
    local attempts = 0
    trigger.action.activateGroup = function(flight)
        attempts = attempts + 1
        if attempts == 1 then error("simulation group not ready") end
        activate(flight)
    end
    data.start()
    assert(Group.activate == nil, "the mock must not invent a Group.activate API")
    data.takeoff(player)
    assert(not data.activated.enemycap, "a failed API call must not claim activation")
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE)
    data.advance()
    assert(data.activated.enemycap == 1, "the next airborne tick retries activation")
    data.advance()
    assert(data.activated.enemycap == 1, "an active flight must not be activated twice")
end

function cases.cap_waits_for_actual_spawn()
    local data = newWorld(base("cap"))
    local player = data.group("players", 1, "Pilot").all[1]
    local pending = data.group("enemycap", 0)
    data.start()
    data.takeoff(player)
    data.advance(2)
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE, "unspawned CAP is not a defeated CAP")
    local enemy = data.unit("enemy1", nil)
    enemy.owner = pending
    pending.all[1] = enemy
    data.advance()
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE)
    enemy.life = 0
    data.advance()
    assert(data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE == 1, "observed and subsequently destroyed CAP completes")
end


local function operationWorld(effect, responseEnabled)
    local config=base('facility')
    config.enemy_cap=false
    config.operation={title='Test Operation', seed=42, objectives={
        {id='primary', title='Fuel depot', required=true, statics={'tank1','tank2','tank3'}, threshold=2, points=300},
        {id='bonus', title='Communications', required=false, statics={'relay'}, threshold=1, points=100, effect=effect or 'delay'},
    }}
    if responseEnabled~=false then config.operation.response={group='response', destination={x=5000,z=5000}, staging={x=9000,z=10000},
        delay=30, bonus_delay=60, max_attempts=3, retry_interval=5} end
    local data=newWorld(config)
    local players=data.group('players',2,'Pilot')
    local response=data.group('response',2)
    for _,name in ipairs({'tank1','tank2','tank3','relay','scenery'}) do data.statics[name]=data.unit(name) end
    data.start()
    data.takeoff(players.all[1]);data.takeoff(players.all[2])
    return data,players,response
end

function cases.operation_functional_threshold_and_shared_recovery()
    local data,players=operationWorld('delay',false)
    data.statics.tank1.life=0;data.advance()
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE)
    data.statics.tank2.life=0;data.advance()
    assert(data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE==1)
    assert(data.statics.tank3.life==100 and data.statics.scenery.life==100 and data.statics.relay.life==100)
    data.land(players.all[1],'Home',2)
    assert(not data.flags.IRON_ANVIL_MISSION_COMPLETE,'every surviving teammate must return')
    data.land(players.all[2],'Home',2)
    assert(data.flags.IRON_ANVIL_RESULT==1 and data.flags.IRON_ANVIL_SCORE==350)
    local count=#data.messages
    data.land(players.all[2],'Home',2)
    assert(#data.messages==count,'debrief is sent once')
end

function cases.operation_bonus_delays_once_and_dispatches()
    local data,_,response=operationWorld('delay')
    assert(response.on==false,'response held at startup')
    data.statics.tank1.life=50;data.advance() -- alarm at t=5, deadline 35
    assert(data.flags.IRON_ANVIL_ALARM==1 and data.flags.IRON_ANVIL_RESPONSE_STATUS==1)
    data.statics.relay.life=0;data.advance() -- deadline 95
    assert(data.flags.IRON_ANVIL_BONUS_BONUS==1)
    data.advance(16) -- t=90
    assert(response.on==false,'bonus delays dispatch once by 60 seconds')
    data.advance() -- t=95
    assert(response.on==true and data.flags.IRON_ANVIL_RESPONSE_STATUS==2)
    assert(#response.tasks==1 and response.tasks[1].params.route.points[2].action=='On Road')
    data.advance(20)
    assert(#response.tasks==1,'no endless waves or repeated dispatch')
end

function cases.operation_bonus_cancels_before_dispatch()
    local data,_,response=operationWorld('cancel')
    data.statics.relay.life=0;data.advance(100)
    assert(data.flags.IRON_ANVIL_RESPONSE_STATUS==3 and response.on==false and #response.tasks==0)
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE,'bonus never substitutes for main objective')
end

function cases.operation_late_bonus_does_not_remove_response()
    local data,_,response=operationWorld('cancel')
    data.statics.tank1.life=75;data.advance(8)
    assert(response.on==true)
    data.statics.relay.life=0;data.advance(10)
    assert(data.flags.IRON_ANVIL_BONUS_BONUS==1 and data.flags.IRON_ANVIL_RESPONSE_STATUS==2)
    assert(response.on==true and #response.all==2,'already dispatched force remains')
end

function cases.operation_unseen_targets_are_not_destroyed()
    local config=base('facility');config.enemy_cap=false
    config.operation={title='Missing target test',seed=1,objectives={
        {id='primary',title='Required',required=true,statics={'missing'},threshold=1}}}
    local data=newWorld(config);local pilot=data.group('players',1,'Pilot').all[1]
    data.start();data.takeoff(pilot);data.advance(10)
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE,'unobserved targets cannot count as destroyed')
    data.statics.missing=data.unit('missing');data.advance()
    data.statics.missing=nil;data.advance()
    assert(data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE==1,'previously observed removed object counts')
end

function cases.operation_response_retries_are_bounded()
    local data,players,response=operationWorld('delay')
    response.setTask=function() error('routing temporarily unavailable') end
    data.statics.tank1.life=0;data.statics.tank2.life=0;data.advance(12)
    assert(data.flags.IRON_ANVIL_RESPONSE_STATUS==5 and response.on==false)
    assert(data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE==1,'failed response never blocks main goal')
    data.land(players.all[1],'Home',2);data.land(players.all[2],'Home',2)
    assert(data.flags.IRON_ANVIL_RESULT==1)
end

function cases.operation_staged_force_can_be_interdicted()
    local data,_,response=operationWorld('delay')
    data.advance();response.all[1].life=0;response.all[2].life=0;data.advance()
    assert(data.flags.IRON_ANVIL_RESPONSE_STATUS==4)
    data.statics.tank1.life=20;data.advance(100)
    assert(#response.tasks==0,'destroyed staged force never respawns')
end

function cases.operation_failure_keeps_partial_debrief()
    local data,players=operationWorld('delay',false)
    data.statics.relay.life=0;data.advance()
    data.lose(players.all[1]);data.lose(players.all[2])
    assert(data.flags.IRON_ANVIL_RESULT==2 and data.flags.IRON_ANVIL_SCORE==100)
    data.menus['Operation status']()
    assert(data.messages[#data.messages]:find('Replay seed: 42'))
end

function cases.operation_bonus_after_main_before_recovery()
    local data,players=operationWorld('delay',false)
    data.statics.tank1.life=0;data.statics.tank2.life=0;data.advance()
    data.statics.relay.life=0;data.advance()
    data.land(players.all[1],'Home',2);data.land(players.all[2],'Home',2)
    assert(data.flags.IRON_ANVIL_RESULT==1 and data.flags.IRON_ANVIL_SCORE==450)
end

function cases.operation_staging_mark_is_available_to_the_team()
    local data=operationWorld('delay')
    data.menus['Response staging / mark']()
    assert(data.mark.x==9000 and data.mark.z==10000)
    assert(data.messages[#data.messages]:find('Response staging area:'))
    local quiet=operationWorld('delay',false)
    quiet.menus['Response staging / mark']()
    assert(quiet.messages[#quiet.messages]:find('disabled'))
end


local function convoyOperationWorld()
    local config=base('facility');config.enemy_cap=false
    config.convoy_group='cargo';config.convoy_destination={x=5000,z=5000}
    config.operation={title='Rolling Thunder',seed=13,objectives={
        {id='primary',title='Supply convoy',required=true,statics={},units={'cargo1','cargo2','cargo3'},group='cargo',threshold=2,points=300},
        {id='bonus',title='Fuel support',required=false,statics={'fuel'},threshold=1,points=100,effect='cancel'},
    },convoy={group='cargo',destination={x=5000,z=5000},delivery_radius=350,interdiction_points=150,delivery_response_delay=15},
    response={group='response',destination={x=5000,z=5000},delay=60,max_attempts=3,retry_interval=5}}
    local data=newWorld(config);local players=data.group('players',2,'Pilot')
    local cargo=data.group('cargo',4);data.group('response',2)
    data.statics.fuel=data.unit('fuel');data.start()
    data.takeoff(players.all[1]);data.takeoff(players.all[2])
    return data,players,cargo
end

function cases.convoy_operation_counts_supply_trucks_not_escorts()
    local data,players,cargo=convoyOperationWorld()
    cargo.all[4].life=0;data.advance()
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE)
    cargo.all[1].life=0;cargo.all[2].life=0;data.advance()
    assert(data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE==1 and data.flags.IRON_ANVIL_INTERDICTION_BONUS==1)
    assert(cargo.all[3].life==100,'third supply truck need not be hunted')
    data.land(players.all[1],'Home',2);data.land(players.all[2],'Home',2)
    assert(data.flags.IRON_ANVIL_SCORE==500,'main plus early interdiction plus both recoveries')
end

function cases.convoy_delivery_accelerates_only_one_response()
    local data,_,cargo=convoyOperationWorld()
    cargo.all[1].point={x=5000,y=0,z=5000};cargo.all[2].point={x=5000,y=0,z=5000}
    data.advance()
    assert(data.flags.IRON_ANVIL_CONVOY_DELIVERED==1 and not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE)
    data.advance(3)
    assert(data.flags.IRON_ANVIL_RESPONSE_STATUS==2 and #data.groups.response.tasks==1)
    data.advance(20)
    assert(#data.groups.response.tasks==1,'delivery cannot create infinite response waves')
    cargo.all[1].life=0;cargo.all[2].life=0;data.advance()
    assert(data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE==1 and not data.flags.IRON_ANVIL_INTERDICTION_BONUS)
end

function cases.convoy_delivery_respects_cancelled_response()
    local data,_,cargo=convoyOperationWorld()
    data.statics.fuel.life=0;data.advance()
    cargo.all[1].point={x=5000,y=0,z=5000};cargo.all[2].point={x=5000,y=0,z=5000}
    data.advance(30)
    assert(data.flags.IRON_ANVIL_CONVOY_DELIVERED==1)
    assert(data.flags.IRON_ANVIL_RESPONSE_STATUS==3 and #data.groups.response.tasks==0)
end

function cases.convoy_operation_f10_tracks_moving_cargo()
    local data,_,cargo=convoyOperationWorld()
    cargo.all[1].point={x=10000,y=0,z=12000};data.menus['Target position / mark']()
    assert(data.mark.x==10000 and data.mark.z==12000)
    assert(#cargo.tasks==1 and cargo.tasks[1].params.route.points[2].action=='On Road')
    data.advance()
    assert(not data.flags.IRON_ANVIL_CONVOY_DELIVERED,'one lead vehicle passing a location is not delivery')
end


function cases.withdrawal_needs_confirmation_and_all_survivors()
    local data,players=operationWorld('delay',false)
    data.statics.tank1.life=0;data.advance()
    data.menus['Confirm withdrawal']()
    assert(not data.flags.IRON_ANVIL_WITHDRAWAL_CONFIRMED)
    data.menus['Propose withdrawal']();data.menus['Confirm withdrawal']()
    assert(data.flags.IRON_ANVIL_WITHDRAWAL_CONFIRMED==1 and not data.flags.IRON_ANVIL_RESULT)
    data.land(players.all[1],'Home',2)
    assert(not data.flags.IRON_ANVIL_RESULT,'an airborne teammate blocks final withdrawal')
    data.land(players.all[2],'Home',2)
    assert(data.flags.IRON_ANVIL_RESULT==3 and data.flags.IRON_ANVIL_SCORE==200)
    assert(not data.flags.IRON_ANVIL_OBJECTIVE_COMPLETE and not data.flags.IRON_ANVIL_MISSION_COMPLETE)
    data.menus['Mission status']()
    assert(data.messages[#data.messages]:find('partial result'))
end

function cases.withdrawal_proposal_expiry_cancel_and_disabled_option()
    local data=operationWorld('delay',false)
    data.menus['Propose withdrawal']();data.advance(7);data.menus['Confirm withdrawal']()
    assert(not data.flags.IRON_ANVIL_WITHDRAWAL_CONFIRMED,'expired proposal must not apply')
    data.menus['Propose withdrawal']();data.menus['Cancel withdrawal']();data.menus['Confirm withdrawal']()
    assert(not data.flags.IRON_ANVIL_WITHDRAWAL_CONFIRMED,'cancelled proposal must not apply')
    local config=base('facility');config.allow_withdrawal=false
    local quiet=newWorld(config);quiet.group('players',1,'Pilot');quiet.start()
    assert(not quiet.menus['Propose withdrawal'] and not quiet.menus['Confirm withdrawal'])
end

function cases.withdrawal_keeps_parked_teammates_safe_without_awarding_flight_points()
    local config=base('facility');config.enemy_cap=false
    config.operation={title='Partial',seed=9,objectives={
        {id='primary',title='Fuel',required=true,statics={'one','two'},threshold=2,points=300}}}
    local data=newWorld(config);local players=data.group('players',2,'Pilot')
    data.statics.one=data.unit('one');data.statics.two=data.unit('two');data.start()
    data.takeoff(players.all[1]);data.statics.one.life=0;data.advance()
    data.menus['Propose withdrawal']();data.menus['Confirm withdrawal']()
    data.land(players.all[1],'Home',2)
    assert(data.flags.IRON_ANVIL_RESULT==3 and data.flags.IRON_ANVIL_SCORE==175)
    assert(data.messages[#data.messages]:find('Safely parked: 1'))
end

function cases.withdrawal_can_upgrade_to_full_success_and_loss_still_fails()
    local data,players=operationWorld('delay',false)
    data.menus['Propose withdrawal']();data.menus['Confirm withdrawal']()
    data.statics.tank1.life=0;data.statics.tank2.life=0;data.advance()
    data.land(players.all[1],'Home',2);data.land(players.all[2],'Home',2)
    assert(data.flags.IRON_ANVIL_RESULT==1,'finishing main goal during return earns full success')
    local loss,pilots=operationWorld('delay',false)
    loss.menus['Propose withdrawal']();loss.menus['Confirm withdrawal']()
    loss.lose(pilots.all[1]);loss.lose(pilots.all[2])
    assert(loss.flags.IRON_ANVIL_RESULT==2,'withdrawal cannot turn aircraft losses into safe recovery')
end

local function alternateWorld()
    local config=base('facility');config.enemy_cap=false
    config.recovery_bases={{name='Home',x=0,z=0},{name='Alternate',x=9000,z=0}}
    config.recovery_label='Home or Alternate'
    local data=newWorld(config);local players=data.group('players',2,'Pilot')
    local target=data.group('target',1);data.start()
    data.takeoff(players.all[1]);data.takeoff(players.all[2]);target.all[1].life=0;data.advance()
    return data,players
end

function cases.approved_alternate_allows_split_team_recovery()
    local data,players=alternateWorld()
    data.menus['Vector alternate']()
    assert(data.messages[#data.messages]:find('Alternate'))
    data.land(players.all[1],'Home',2);data.land(players.all[2],'Alternate',2)
    assert(data.flags.IRON_ANVIL_RESULT==1)
end

function cases.alternate_rejects_hostile_and_unlisted_airfields()
    local data,players=alternateWorld()
    data.land(players.all[1],'Home',2);data.land(players.all[2],'Alternate',1)
    assert(not data.flags.IRON_ANVIL_RESULT,'captured alternate must be rejected')
    data.land(players.all[2],'Unlisted friendly field',2)
    assert(not data.flags.IRON_ANVIL_RESULT,'only briefed recovery fields count')
    data.land(players.all[2],'Alternate',2)
    assert(data.flags.IRON_ANVIL_RESULT==1)
end

function cases.alternate_helipad_event_without_place_checks_coalition()
    local data,players=alternateWorld()
    data.land(players.all[1],'Home',2)
    players.all[2].point={x=9000,y=0,z=0}
    Airbase={getByName=function(name) return {getCoalition=function() return name=='Alternate' and 1 or 2 end} end}
    data.land(players.all[2],nil,nil)
    assert(not data.flags.IRON_ANVIL_RESULT)
    Airbase={getByName=function() return {getCoalition=function() return 2 end} end}
    data.land(players.all[2],nil,nil)
    assert(data.flags.IRON_ANVIL_RESULT==1)
end

local selected = arg[2]
if selected then
    assert(cases[selected], "Unknown runtime case: " .. selected)()
    print("PASS: " .. selected)
else
    for name, check in pairs(cases) do check(); print("PASS: " .. name) end
end
