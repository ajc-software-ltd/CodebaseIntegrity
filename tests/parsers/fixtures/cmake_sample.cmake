# CMake extraction fixture.
function(my_add_library name)
  add_library(${name} STATIC ${ARGN})
endfunction()

macro(my_init)
  message(STATUS "init")
endmacro()
