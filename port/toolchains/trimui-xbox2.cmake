include("${CMAKE_CURRENT_LIST_DIR}/trimui.cmake")
# LLVM archives retain the symbol index for ThinLTO's bitcode objects.
set(CMAKE_AR "${PORT_ROOT}/toolchains/zig-ar")
set(CMAKE_RANLIB "${PORT_ROOT}/toolchains/zig-ranlib")
foreach(lang C CXX)
  set(CMAKE_${lang}_COMPILER_AR "${CMAKE_AR}" CACHE FILEPATH "LLVM archiver" FORCE)
  set(CMAKE_${lang}_COMPILER_RANLIB "${CMAKE_RANLIB}" CACHE FILEPATH "LLVM ranlib" FORCE)
endforeach()
