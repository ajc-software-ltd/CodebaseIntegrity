-- Lua extraction fixture.
local M = {}

function M.start(mode)
end

function M:stop()
end

local function helper(x)
    local function inner(y)
        return y
    end
    return inner(x)
end

function global_setup()
end

return M
