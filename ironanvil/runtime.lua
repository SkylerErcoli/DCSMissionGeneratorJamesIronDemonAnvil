-- Iron Anvil mission controller. Runs inside the DCS mission sandbox (Lua 5.1).
-- The generator inserts IRON_ANVIL before loading this script with DoScriptFile.
-- Required configuration: mission_type, player_group, base_name, home{x,z}.
-- Ground objectives: target_groups and, optionally, target_statics (name arrays).
-- Optional: target{x,z}, enemy_cap, cap_groups, convoy_group,
-- convoy_destination{x,z}, station_seconds, station_radius, convoy_speed.
do
    local config = IRON_ANVIL or {}
    local blue = coalition and coalition.side and coalition.side.BLUE or 2
    local state = {
        airborne = false,
        objective = false,
        complete = false,
        result = 0,
        roster = {},
        capStarted = false,
        capActivated = {},
        capSeenAlive = {},
        capAnnounced = false,
        convoyStarted = false,
        stationTime = 0,
        lastTime = nil,
        warned = {},
    }
    local function log(message)
        if env and env.info then
            env.info("[Iron Anvil] " .. tostring(message))
        end
    end
    local function warnOnce(key, message)
        if not state.warned[key] then
            state.warned[key] = true
            log(message)
        end
    end
    local function method(object, name, ...)
        if not object or type(object[name]) ~= "function" then return nil end
        local ok, value = pcall(object[name], object, ...)
        if ok then return value end
        return nil
    end
    local function group(name)
        if not name or not Group or not Group.getByName then return nil end
        local ok, value = pcall(Group.getByName, name)
        if ok then return value end
        return nil
    end
    local function units(namedGroup)
        local found = group(namedGroup)
        if not found or method(found, "isExist") == false then return {} end
        return method(found, "getUnits") or {}
    end
    local function alive(unit)
        if not unit or method(unit, "isExist") == false then return false end
        local life = method(unit, "getLife")
        return life == nil or life > 1
    end
    local function liveCount(names)
        local count = 0
        for _, name in ipairs(names or {}) do
            for _, unit in ipairs(units(name)) do
                if alive(unit) then count = count + 1 end
            end
        end
        return count
    end
    local function staticCount()
        local count = 0
        for _, name in ipairs(config.target_statics or {}) do
            if StaticObject and StaticObject.getByName then
                local ok, object = pcall(StaticObject.getByName, name)
                if ok and alive(object) then count = count + 1 end
            end
        end
        return count
    end
    local function announce(message, seconds)
        if trigger and trigger.action then
            if trigger.action.outTextForCoalition then
                trigger.action.outTextForCoalition(blue, "IRON ANVIL: " .. message, seconds or 15)
            elseif trigger.action.outText then
                trigger.action.outText("IRON ANVIL: " .. message, seconds or 15)
            end
        end
        log(message)
    end
    local function flag(name, value)
        if trigger and trigger.action and trigger.action.setUserFlag then
            trigger.action.setUserFlag(name, value or 1)
        end
    end
    local function playerUnits()
        local result = {}
        local names = config.player_groups or {config.player_group}
        for _, name in ipairs(names) do
            for _, unit in ipairs(units(name)) do
                if alive(unit) and method(unit, "getPlayerName") then
                    result[#result + 1] = unit
                end
            end
        end
        return result
    end
    local function isPlayer(unit)
        if not unit or not method(unit, "getPlayerName") then return false end
        local owner = method(unit, "getGroup")
        local name = method(owner, "getName")
        for _, expected in ipairs(config.player_groups or {config.player_group}) do
            if name == expected then return true end
        end
        return false
    end
    local function playerKey(unit)
        return method(unit, "getName") or tostring(unit)
    end
    local function registerPlayer(unit)
        if not isPlayer(unit) then return nil end
        local key = playerKey(unit)
        local record = state.roster[key]
        local id = method(unit, "getID")
        if not record or (record.dead and alive(unit)
            and (method(record.unit, "isExist") == false or (id and record.id and id ~= record.id))) then
            record = {unit = unit, id = id, tookOff = false, recovered = false, dead = false, lastInAir = false}
            state.roster[key] = record
        end
        record.unit = unit
        return record
    end
    local function registerJoinedPlayers()
        for _, unit in ipairs(playerUnits()) do registerPlayer(unit) end
    end
    local function horizontalDistance(point, target)
        if not point or not target or not target.x or not target.z then return math.huge end
        return math.sqrt((point.x - target.x)^2 + (point.z - target.z)^2)
    end
    local function targetPoint()
        if config.convoy_group then
            for _, unit in ipairs(units(config.convoy_group)) do
                if alive(unit) then
                    local point = method(unit, "getPoint")
                    if point then return point end
                end
            end
        end
        if config.target and config.target.x and config.target.z then
            local height = 0
            if land and land.getHeight then
                local ok, value = pcall(land.getHeight, {x = config.target.x, y = config.target.z})
                if ok then height = value end
            end
            return {x = config.target.x, y = height, z = config.target.z}
        end
        return nil
    end
    local function coordinates(point)
        if coord and coord.LOtoLL then
            local ok, latitude, longitude = pcall(coord.LOtoLL, point)
            if ok and latitude and longitude then
                local text = string.format("%.5f, %.5f", latitude, longitude)
                if coord.LLtoMGRS then
                    local converted, grid = pcall(coord.LLtoMGRS, latitude, longitude)
                    if converted and grid then
                        text = text .. string.format(" | %s %s %05d %05d",
                            grid.UTMZone or "", grid.MGRSDigraph or "",
                            math.floor(grid.Easting or 0), math.floor(grid.Northing or 0))
                    end
                end
                return text
            end
        end
        return string.format("DCS x %.0f, z %.0f", point.x, point.z)
    end
    local function vectorTo(destination, label)
        if not destination then announce("No " .. label .. " position is available."); return end
        local clients = playerUnits()
        local reference = clients[1]
        for _, unit in ipairs(clients) do
            if method(unit, "inAir") then reference = unit; break end
        end
        local origin = method(reference, "getPoint")
        if not origin then announce("Join a client slot to request a vector."); return end
        local north, east = destination.x - origin.x, destination.z - origin.z
        local bearing = math.deg(math.atan2(east, north)) % 360
        announce(string.format("From %s: %s bearing %03d, range %.1f NM.",
            method(reference, "getPlayerName") or "lead client", label,
            math.floor(bearing + 0.5) % 360, horizontalDistance(origin, destination) / 1852), 20)
    end
    local function reportPosition()
        local point = targetPoint()
        if point then
            announce("Target position: " .. coordinates(point), 25)
            if trigger and trigger.action and trigger.action.markToCoalition then
                if trigger.action.removeMark then pcall(trigger.action.removeMark, 918700) end
                pcall(trigger.action.markToCoalition, 918700, "Iron Anvil objective", point, blue, true)
                for index, site in ipairs(config.facility_sites or {}) do
                    local height = 0
                    if land and land.getHeight then
                        local ok, value = pcall(land.getHeight, {x = site.x, y = site.z})
                        if ok then height = value end
                    end
                    local mark = 918710 + index
                    if trigger.action.removeMark then pcall(trigger.action.removeMark, mark) end
                    pcall(trigger.action.markToCoalition, mark, site.name or ("Facility site " .. index),
                          {x = site.x, y = height, z = site.z}, blue, true)
                end
            end
        else
            announce("No target position is available.")
        end
    end
    local function status()
        if state.complete then
            if state.result == 2 then
                announce("Mission failed. All participating client aircraft were lost.")
            else
                announce("Mission complete. All objectives achieved and every surviving client recovered.")
            end
        elseif state.objective then
            local remaining = 0
            for _, record in pairs(state.roster) do
                if not record.dead and not record.recovered then remaining = remaining + 1 end
            end
            announce("Objective complete. " .. remaining .. " surviving clients must fly and recover at " ..
                tostring(config.base_name or "your friendly airbase") .. ".")
        elseif config.mission_type == "cap" then
            if config.enemy_cap then
                announce("CAP: " .. liveCount(config.cap_groups) .. " enemy aircraft remaining. Enemy flights launch when a client is airborne.")
            else
                local remaining = math.max(0, math.ceil((tonumber(config.station_seconds) or 300) - state.stationTime))
                announce("CAP: remain within " .. math.floor((tonumber(config.station_radius) or 25000) / 1000) ..
                    " km of the objective, airborne, for " .. remaining .. " more seconds.")
            end
        else
            announce("Ground objective: " .. (liveCount(config.target_groups) + staticCount()) ..
                " targets remaining. Recover at " .. tostring(config.base_name or "your friendly airbase") .. ".")
        end
    end
    local function startCAP()
        if state.capStarted or not config.enemy_cap then return end
        local allActivated = #(config.cap_groups or {}) > 0
        local anyActivated = false
        for _, name in ipairs(config.cap_groups or {}) do
            if not state.capActivated[name] then
                local flight = group(name)
                -- activateGroup is a trigger action in the DCS sandbox. A
                -- Group.activate method is not part of the documented API.
                if flight and trigger and trigger.action and trigger.action.activateGroup then
                    local ok, err = pcall(trigger.action.activateGroup, flight)
                    if ok and err ~= false then
                        state.capActivated[name] = true
                    else
                        warnOnce("cap_" .. name, "Could not activate CAP group " .. name .. ": " .. tostring(err) .. "; will retry.")
                    end
                else
                    warnOnce("cap_" .. name, "CAP group or activation API temporarily unavailable: " .. tostring(name) .. "; will retry.")
                end
            end
            if state.capActivated[name] then anyActivated = true else allActivated = false end
        end
        state.capStarted = allActivated
        if anyActivated and not state.capAnnounced then
            state.capAnnounced = true
            announce("Enemy CAP is active. Maintain a lookout for hostile fighters.")
        end
    end

    local function capDefeated()
        if not state.capStarted then return false end
        local allObserved = true
        for _, name in ipairs(config.cap_groups or {}) do
            if liveCount({name}) > 0 then state.capSeenAlive[name] = true end
            if not state.capSeenAlive[name] then allObserved = false end
        end
        -- Activation can take a simulation frame. Missing/unspawned groups
        -- must never count as destroyed fighters and complete CAP instantly.
        return allObserved and liveCount(config.cap_groups) == 0
    end
    local function routePoint(x, z, onRoad)
        return {
            x = x, y = z, type = "Turning Point", action = onRoad and "On Road" or "Off Road",
            speed = tonumber(config.convoy_speed) or 10, speed_locked = true,
            task = {id = "ComboTask", params = {tasks = {}}},
        }
    end
    local function nearestRoad(point)
        if land and land.getClosestPointOnRoads then
            local ok, x, z = pcall(land.getClosestPointOnRoads, "roads", point.x, point.z)
            if ok and type(x) == "number" and type(z) == "number" then return {x = x, z = z} end
        end
        return nil
    end
    local function startConvoy()
        if state.convoyStarted or not config.convoy_group then return end
        state.convoyStarted = true
        local convoy = group(config.convoy_group)
        local controller = method(convoy, "getController")
        if not controller then
            warnOnce("convoy_missing", "Convoy controller unavailable; retaining its mission-editor route.")
            return
        end
        method(controller, "setOnOff", true)
        method(controller, "setCommand", {id = "StopRoute", params = {value = false}})
        local first
        for _, unit in ipairs(units(config.convoy_group)) do
            if alive(unit) then first = method(unit, "getPoint"); break end
        end
        local destination = config.convoy_destination
        if first and destination and destination.x and destination.z then
            local roadStart = nearestRoad(first)
            local roadEnd = nearestRoad(destination)
            local points = {routePoint(first.x, first.z, false)}
            local path
            if roadStart and roadEnd and land and land.findPathOnRoads then
                local ok, found = pcall(land.findPathOnRoads, "roads", roadStart.x, roadStart.z, roadEnd.x, roadEnd.z)
                if ok and type(found) == "table" and #found > 1 then path = found end
            end
            if path then
                for _, point in ipairs(path) do
                    if point.x and point.y then points[#points + 1] = routePoint(point.x, point.y, true) end
                end
            elseif roadStart and roadEnd then
                -- DCS computes its own road route between these two road waypoints.
                points[#points + 1] = routePoint(roadStart.x, roadStart.z, true)
                points[#points + 1] = routePoint(roadEnd.x, roadEnd.z, true)
            else
                warnOnce("convoy_roads", "No road route found; using a direct off-road convoy route.")
            end
            points[#points + 1] = routePoint(destination.x, destination.z, false)
            method(controller, "setTask", {id = "Mission", params = {route = {points = points}}})
        end
        announce("Enemy convoy is moving. Request its current position from the F10 menu.")
    end
    local function objectiveComplete()
        if state.objective then return end
        state.objective = true
        flag("IRON_ANVIL_OBJECTIVE_COMPLETE")
        announce("Objective complete. RTB to " .. tostring(config.base_name or "your friendly airbase") .. " and land to complete the mission.", 25)
    end
    local function friendlyHome(unit, place)
        local placeName = method(place, "getName")
        local side = method(place, "getCoalition")
        if placeName and config.base_name then
            return placeName == config.base_name and (side == nil or side == blue)
        end
        -- Helicopter/FARP land events can omit event.place; use home proximity
        -- and the actual airbase coalition when the sandbox exposes it.
        if not place and Airbase and Airbase.getByName and config.base_name then
            local ok, airbase = pcall(Airbase.getByName, config.base_name)
            if ok and airbase then side = method(airbase, "getCoalition") end
        end
        return horizontalDistance(method(unit, "getPoint"), config.home) <= (tonumber(config.home_radius) or 4000)
            and (side == nil or side == blue)
    end
    local function checkResult()
        if state.complete or not state.airborne then return end
        local joined, surviving, recovered = 0, 0, 0
        for _, record in pairs(state.roster) do
            joined = joined + 1
            if not record.dead and not alive(record.unit) then record.dead = true end
            if not record.dead then
                surviving = surviving + 1
                if record.tookOff and record.recovered then recovered = recovered + 1 end
            end
        end
        if joined > 0 and surviving == 0 then
            state.complete, state.result = true, 2
            flag("IRON_ANVIL_RESULT", 2)
            announce("Mission failed. All participating client aircraft were lost.", 30)
        elseif state.objective and surviving > 0 and recovered == surviving then
            state.complete, state.result = true, 1
            flag("IRON_ANVIL_MISSION_COMPLETE")
            flag("IRON_ANVIL_RESULT", 1)
            announce("Mission complete. Every surviving client recovered at " .. tostring(config.base_name or "home base") .. ".", 30)
        end
    end
    local function recover(unit, place)
        local record = registerPlayer(unit)
        if record and not record.dead and record.tookOff then
            record.lastInAir = false
            record.recovered = friendlyHome(unit, place)
            registerJoinedPlayers()
            checkResult()
        end
    end
    local handler = {}
    function handler:onEvent(event)
        if not event or not world or not world.event then return end
        if event.id == world.event.S_EVENT_BIRTH then
            registerPlayer(event.initiator)
        elseif event.id == world.event.S_EVENT_TAKEOFF and isPlayer(event.initiator) then
            registerJoinedPlayers()
            local record = registerPlayer(event.initiator)
            record.tookOff, record.lastInAir, record.recovered = true, true, false
            state.airborne = true
            startCAP()
            startConvoy()
        elseif event.id == world.event.S_EVENT_LAND then
            recover(event.initiator, event.place)
        elseif event.id == world.event.S_EVENT_DEAD or event.id == world.event.S_EVENT_CRASH
            or event.id == world.event.S_EVENT_EJECTION or event.id == world.event.S_EVENT_PILOT_DEAD then
            local record = event.initiator and state.roster[playerKey(event.initiator)]
            if record then
                record.dead, record.recovered = true, false
                registerJoinedPlayers()
                checkResult()
            end
        end
    end
    if world and world.addEventHandler then world.addEventHandler(handler) end

    local function tick(_, now)
        local ok, err = pcall(function()
            local delta = state.lastTime and math.max(0, math.min(now - state.lastTime, 10)) or 0
            state.lastTime = now
            if state.complete then return end
            local flying = false
            local onStation = false
            for _, unit in ipairs(playerUnits()) do
                local record = registerPlayer(unit)
                if method(unit, "inAir") then
                    record.tookOff, record.lastInAir, record.recovered = true, true, false
                    flying = true
                    local point = method(unit, "getPoint")
                    if horizontalDistance(point, config.target or config.home) <= (tonumber(config.station_radius) or 25000) then
                        onStation = true
                    end
                elseif record.lastInAir and not record.dead then
                    record.lastInAir = false
                    record.recovered = record.tookOff and friendlyHome(unit, nil)
                end
            end
            checkResult()
            if state.complete then return end
            if flying then
                state.airborne = true
                startCAP()
                startConvoy()
            end
            if state.airborne and not state.objective then
                if config.mission_type == "cap" then
                    if config.enemy_cap then
                        if capDefeated() then
                            objectiveComplete()
                        end
                    elseif onStation then
                        state.stationTime = state.stationTime + delta
                        if state.stationTime >= (tonumber(config.station_seconds) or 300) then objectiveComplete() end
                    end
                elseif (#(config.target_groups or {}) + #(config.target_statics or {})) > 0
                    and liveCount(config.target_groups) + staticCount() == 0 then
                    objectiveComplete()
                end
            end
            checkResult()
        end)
        if not ok then warnOnce(tostring(err), "Controller error: " .. tostring(err)) end
        return now + 5
    end

    -- Prevent a convoy from departing before clients get airborne, including
    -- multiplayer missions where clients occupy their slots well after start.
    if config.convoy_group then
        local controller = method(group(config.convoy_group), "getController")
        method(controller, "setCommand", {id = "StopRoute", params = {value = true}})
    end
    if missionCommands and missionCommands.addSubMenuForCoalition and missionCommands.addCommandForCoalition then
        local menu = missionCommands.addSubMenuForCoalition(blue, "Iron Anvil")
        missionCommands.addCommandForCoalition(blue, "Mission status", menu, status)
        missionCommands.addCommandForCoalition(blue, "Target position / mark", menu, reportPosition)
        missionCommands.addCommandForCoalition(blue, "Target bearing / range", menu, function() vectorTo(targetPoint(), "target") end)
        missionCommands.addCommandForCoalition(blue, "Vector home", menu, function() vectorTo(config.home, tostring(config.base_name or "home base")) end)
    end
    if timer and timer.scheduleFunction and timer.getTime then
        timer.scheduleFunction(tick, nil, timer.getTime() + 5)
    end
    registerJoinedPlayers()
    announce("Mission controller ready. Use F10 > Iron Anvil for status and target coordinates.", 20)
end
