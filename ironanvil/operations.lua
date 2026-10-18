-- Cooperative objective and response state machine; native DCS Lua 5.1 only.
-- Loaded before runtime.lua. No filesystem, sockets, hooks or external frameworks.
IRON_ANVIL_CREATE_OPERATION = function(config, service)
    local op = {objectives = {}, alarm = false, bonus = 0, main = false,
                response = config.response and 'held' or 'disabled', attempts = 0, extra = 0}
    local response = config.response
    local responseSeen = false
    local responseCodes = {held=0, scheduled=1, dispatched=2, cancelled=3, destroyed=4, unavailable=5}
    local function invoke(object, name, ...)
        if not object or type(object[name]) ~= 'function' then return false end
        local ok, result = pcall(object[name], object, ...)
        return ok and result ~= false
    end
    local function readStatic(name)
        if not StaticObject or not StaticObject.getByName then return nil, nil end
        local ok, object = pcall(StaticObject.getByName, name)
        if not ok or not object then return nil, nil end
        local life
        if type(object.getLife) == 'function' then
            local good, value = pcall(object.getLife, object)
            if good and type(value) == 'number' then life = value end
        end
        return object, life
    end
    local function setResponse(value)
        op.response = value
        service.flag('IRON_ANVIL_RESPONSE_STATUS', responseCodes[value] or 0)
    end
    local function holdResponse()
        if not response then return end
        local group = service.group(response.group)
        if not group then return end
        local ok, controller = pcall(function() return group:getController() end)
        if ok and controller then
            invoke(controller, 'setCommand', {id='StopRoute', params={value=true}})
            invoke(controller, 'setOnOff', false)
        end
    end
    for _, definition in ipairs(config.objectives or {}) do
        local objective = {definition=definition, complete=false, destroyed=0, targets={}}
        for _, name in ipairs(definition.statics or {}) do
            local object, life = readStatic(name)
            objective.targets[#objective.targets+1] = {name=name, seen=object ~= nil, initial=life}
        end
        op.objectives[#op.objectives+1] = objective
    end
    holdResponse()
    if response then setResponse('held') end

    local function bonusEffect(definition)
        op.bonus = op.bonus + (definition.points or 100)
        service.flag('IRON_ANVIL_BONUS_' .. string.upper(definition.id), 1)
        if not response then
            service.announce('Bonus achieved: ' .. definition.title .. '. Ground response is disabled.')
        elseif op.response == 'held' or op.response == 'scheduled' then
            if definition.effect == 'cancel' then
                setResponse('cancelled')
                holdResponse()
                service.announce('Bonus achieved: fuel support disabled. The ground response has been cancelled.')
            elseif definition.effect == 'delay' then
                op.extra = op.extra + (response.bonus_delay or 360)
                if op.deadline then op.deadline = op.deadline + (response.bonus_delay or 360) end
                service.announce('Bonus achieved: communications disabled. Ground response delayed by ' ..
                    math.floor((response.bonus_delay or 360) / 60) .. ' minutes.')
            end
        else
            service.announce('Bonus achieved: ' .. definition.title .. '. Response is already ' .. op.response .. '; it will not disappear.')
        end
    end
    local function road(point)
        if land and land.getClosestPointOnRoads then
            local ok, x, z = pcall(land.getClosestPointOnRoads, 'roads', point.x, point.z)
            if ok and type(x)=='number' and type(z)=='number' then return {x=x, z=z} end
        end
    end
    local function waypoint(x, z, onRoad)
        return {x=x, y=z, type='Turning Point', action=onRoad and 'On Road' or 'Off Road',
                speed=8, speed_locked=true, task={id='ComboTask', params={tasks={}}}}
    end
    local function dispatch()
        local group = service.group(response.group)
        if not group then return false end
        local ok, controller = pcall(function() return group:getController() end)
        if not ok or not controller then return false end
        local first
        for _, unit in ipairs(service.units(response.group)) do
            if service.alive(unit) then
                local good, point = pcall(function() return unit:getPoint() end)
                if good and point then first=point; break end
            end
        end
        if not first then return false end
        local destination = response.destination
        if not destination then return false end
        local points = {waypoint(first.x, first.z, false)}
        local startRoad, endRoad = road(first), road(destination)
        local path
        if startRoad and endRoad and land and land.findPathOnRoads then
            local good, value = pcall(land.findPathOnRoads, 'roads', startRoad.x, startRoad.z, endRoad.x, endRoad.z)
            if good and type(value)=='table' and #value>1 then path=value end
        end
        if path then
            for _, point in ipairs(path) do
                if point.x and point.y then points[#points+1]=waypoint(point.x, point.y, true) end
            end
        elseif startRoad and endRoad then
            points[#points+1]=waypoint(startRoad.x, startRoad.z, true)
            points[#points+1]=waypoint(endRoad.x, endRoad.z, true)
        else
            service.warn('operation_roads', 'No road route for ground response; using the editor-compatible off-road route.')
        end
        points[#points+1]=waypoint(destination.x, destination.z, false)
        if not invoke(controller, 'setTask', {id='Mission', params={route={points=points}}}) then return false end
        if not invoke(controller, 'setCommand', {id='StopRoute', params={value=false}}) then return false end
        if not invoke(controller, 'setOnOff', true) then return false end
        return true
    end

    function op.tick(now)
        local damaged, required, allRequired = false, 0, true
        for _, objective in ipairs(op.objectives) do
            if not objective.complete then
                local destroyed = 0
                for _, target in ipairs(objective.targets) do
                    local object, life = readStatic(target.name)
                    if object then
                        if not target.seen then target.seen=true; target.initial=life end
                        if life and life<=1 then destroyed=destroyed+1; damaged=true
                        elseif life and target.initial and life<target.initial then damaged=true end
                    elseif target.seen then
                        destroyed=destroyed+1; damaged=true
                    end
                end
                objective.destroyed=destroyed
                if destroyed >= objective.definition.threshold then
                    objective.complete=true
                    service.flag('IRON_ANVIL_GOAL_' .. string.upper(objective.definition.id), 1)
                    if objective.definition.required then
                        service.announce('Required objective disabled: ' .. objective.definition.title .. '.')
                    else
                        bonusEffect(objective.definition)
                    end
                end
            end
            if objective.definition.required then
                required=required+1
                if not objective.complete then allRequired=false end
            end
        end
        if response and (op.response=='held' or op.response=='scheduled') then
            local living=0
            for _, unit in ipairs(service.units(response.group)) do
                if service.alive(unit) then living=living+1; responseSeen=true end
            end
            if responseSeen and living==0 then
                setResponse('destroyed')
                service.announce('The staged ground response has been destroyed. No replacement force will be dispatched.')
            end
        end
        if damaged and not op.alarm then
            op.alarm=true
            service.flag('IRON_ANVIL_ALARM', 1)
            if response and op.response=='held' then
                op.deadline=now+(response.delay or 180)+op.extra
                setResponse('scheduled')
                service.announce('Alarm raised. A ground response is preparing at the briefed staging area. Optional objectives can disrupt it.')
            end
        end
        if op.response=='held' or op.response=='scheduled' or op.response=='cancelled' then holdResponse() end
        if op.response=='scheduled' and now >= op.deadline and (not op.nextAttempt or now>=op.nextAttempt) then
            op.attempts=op.attempts+1
            if dispatch() then
                setResponse('dispatched')
                service.announce('Ground response dispatched from its staging area. It must travel to the main objective; intercept or withdraw as a group.')
            elseif op.attempts >= (response.max_attempts or 3) then
                setResponse('unavailable')
                holdResponse()
                service.announce('Ground response is unavailable. Continue the operation; this does not block your objectives.')
                service.warn('operation_response', 'Ground response dispatch failed after bounded retries.')
            else
                holdResponse()
                op.nextAttempt=now+(response.retry_interval or 15)
            end
        elseif op.response=='dispatched' then
            local living=0
            for _, unit in ipairs(service.units(response.group)) do
                if service.alive(unit) then living=living+1 end
            end
            if living==0 then setResponse('destroyed'); service.announce('Enemy ground response destroyed. No further waves.') end
        end
        if required>0 and allRequired and not op.main then
            op.main=true
            service.complete()
        end
    end

    function op.status()
        local lines={config.title or 'Cooperative operation'}
        for _, objective in ipairs(op.objectives) do
            local definition=objective.definition
            lines[#lines+1]=(definition.required and 'REQUIRED: ' or 'BONUS: ') .. definition.title .. ' — ' ..
                (objective.complete and 'DISABLED' or (objective.destroyed .. '/' .. definition.threshold .. ' disabled'))
        end
        local suffix=''
        if op.response=='scheduled' and op.deadline and timer and timer.getTime then
            suffix=' (dispatch in ' .. math.max(0, math.ceil(op.deadline-timer.getTime())) .. ' seconds)'
        end
        lines[#lines+1]='Ground response: ' .. op.response .. suffix
        lines[#lines+1]='Shared objective points: ' .. ((op.main and 300 or 0)+op.bonus) .. '. Replay seed: ' .. tostring(config.seed)
        service.announce(table.concat(lines, '\n'), 25)
    end

    function op.debrief(roster, result)
        if op.debriefed then return end
        op.debriefed=true
        local recovered,lost=0,0
        for _, record in pairs(roster) do
            if record.dead then lost=lost+1 elseif record.recovered then recovered=recovered+1 end
        end
        local score=(op.main and 300 or 0)+op.bonus+recovered*25
        service.flag('IRON_ANVIL_SCORE', score)
        service.announce((config.title or 'Operation') .. ' — DEBRIEF\n' ..
            'Main objective: ' .. (op.main and 'disabled' or 'incomplete') ..
            ' | Bonus points: ' .. op.bonus .. '\n' ..
            'Recovered: ' .. recovered .. ' | Lost: ' .. lost .. ' | Shared score: ' .. score .. '\n' ..
            'Ground response: ' .. op.response .. ' | Replay seed: ' .. tostring(config.seed) .. '\n' ..
            (result==1 and 'Operation complete. Thank you for bringing the team home.' or 'Flight lost. Completed objectives still appear in this debrief.'), 45)
    end
    return op
end
