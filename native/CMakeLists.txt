cmake_minimum_required(VERSION 3.16)
project(sieans_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(SIEANS_NATIVE_GENTL "Build Hikrobot MvCameraControl GenTL capture" ON)
option(SIEANS_NATIVE_PYTHON "Build pybind11 Python module" ON)

# ---- zxing-cpp (vendored) -------------------------------------------------
set(BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(BUILD_BLACKBOX_TESTS OFF CACHE BOOL "" FORCE)
set(BUILD_UNIT_TESTS OFF CACHE BOOL "" FORCE)
set(BUILD_PYTHON_MODULE OFF CACHE BOOL "" FORCE)
set(BUILD_WRITERS OFF CACHE BOOL "" FORCE)
set(BUILD_READERS ON CACHE BOOL "" FORCE)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
add_subdirectory(third_party/zxing-cpp EXCLUDE_FROM_ALL)

add_library(sieans_algo STATIC
  src/barcode.cpp
  src/gentl_capture.cpp
)
target_include_directories(sieans_algo
  PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include
  PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/third_party/zxing-cpp/core/src
)
target_link_libraries(sieans_algo PUBLIC ZXing::ZXing)

set(SIEANS_GENTL_BUILT 0)
if(SIEANS_NATIVE_GENTL)
  set(_MVS_ROOT "/opt/MVS")
  if(DEFINED ENV{MVCAM_COMMON_RUNENV})
    get_filename_component(_cand "$ENV{MVCAM_COMMON_RUNENV}/.." ABSOLUTE)
    if(EXISTS "${_cand}/include/MvCameraControl.h")
      set(_MVS_ROOT "${_cand}")
    endif()
  endif()
  if(EXISTS "${_MVS_ROOT}/include/MvCameraControl.h")
    message(STATUS "SIEANS GenTL: enabling MvCameraControl at ${_MVS_ROOT}")
    target_compile_definitions(sieans_algo PUBLIC SIEANS_HAS_MVCAM=1)
    target_include_directories(sieans_algo PUBLIC "${_MVS_ROOT}/include")
    find_library(MVCAM_LIB MvCameraControl
      HINTS "${_MVS_ROOT}/lib/64" "${_MVS_ROOT}/lib"
      NO_DEFAULT_PATH)
    if(MVCAM_LIB)
      target_link_libraries(sieans_algo PUBLIC ${MVCAM_LIB} dl)
      set(SIEANS_GENTL_BUILT 1)
    else()
      message(WARNING "MvCameraControl library not found; GenTL stubs only")
      target_compile_definitions(sieans_algo PUBLIC SIEANS_HAS_MVCAM=0)
    endif()
  else()
    message(STATUS "SIEANS GenTL: /opt/MVS not found — stub GenTL API only")
  endif()
endif()

# ---- pybind11 module ------------------------------------------------------
if(SIEANS_NATIVE_PYTHON)
  find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
  find_package(pybind11 CONFIG QUIET)
  find_path(PYBIND11_INCLUDE_DIR pybind11/pybind11.h
    HINTS /usr/include /usr/local/include)
  if(pybind11_FOUND)
    pybind11_add_module(sieans_native MODULE python/module.cpp)
  else()
    if(NOT PYBIND11_INCLUDE_DIR)
      message(FATAL_ERROR "pybind11 not found (apt install pybind11-dev)")
    endif()
    message(STATUS "Using pybind11 headers at ${PYBIND11_INCLUDE_DIR}")
    Python3_add_library(sieans_native MODULE WITH_SOABI python/module.cpp)
    target_include_directories(sieans_native PRIVATE ${PYBIND11_INCLUDE_DIR})
  endif()
  target_link_libraries(sieans_native PRIVATE sieans_algo)
  # Drop into repo .pydeps so existing launch PYTHONPATH finds it.
  set(_PYDEPS_OUT "${CMAKE_CURRENT_SOURCE_DIR}/../.pydeps")
  file(MAKE_DIRECTORY "${_PYDEPS_OUT}")
  set_target_properties(sieans_native PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${_PYDEPS_OUT}"
    RUNTIME_OUTPUT_DIRECTORY "${_PYDEPS_OUT}"
  )
  add_custom_command(TARGET sieans_native POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory "${CMAKE_BINARY_DIR}/python"
    COMMAND ${CMAKE_COMMAND} -E copy $<TARGET_FILE:sieans_native>
            "${CMAKE_BINARY_DIR}/python/"
    COMMENT "Copy sieans_native into build/python")
endif()

message(STATUS "sieans_native: GenTL built=${SIEANS_GENTL_BUILT}")
