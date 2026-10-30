cmake_minimum_required(VERSION 3.16)
project(sieans_qt LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

if(NOT DEFINED CMAKE_PREFIX_PATH OR CMAKE_PREFIX_PATH STREQUAL "")
  if(DEFINED ENV{CMAKE_PREFIX_PATH} AND NOT "$ENV{CMAKE_PREFIX_PATH}" STREQUAL "")
    # honor env
  elseif(EXISTS "$ENV{HOME}/Qt/6.7.3/gcc_64")
    list(APPEND CMAKE_PREFIX_PATH "$ENV{HOME}/Qt/6.7.3/gcc_64")
  elseif(EXISTS "$ENV{HOME}/Qt/6.8.0/gcc_64")
    list(APPEND CMAKE_PREFIX_PATH "$ENV{HOME}/Qt/6.8.0/gcc_64")
  endif()
endif()

find_package(Qt6 REQUIRED COMPONENTS Widgets Gui Core)

set(SIEANS_NATIVE_PYTHON OFF CACHE BOOL "Skip pybind for Qt app" FORCE)
if(NOT TARGET sieans_algo)
  add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../native
                   ${CMAKE_BINARY_DIR}/native
                   EXCLUDE_FROM_ALL)
endif()

add_executable(sieans_qt
  src/main.cpp
  src/MainWindow.cpp
  src/MainWindow.hpp
  src/ImageView.cpp
  src/ImageView.hpp
  src/Theme.hpp
  src/SieansDocument.cpp
  src/SieansDocument.hpp
  src/FlowCanvas.cpp
  src/FlowCanvas.hpp
  src/GenTLWorker.cpp
  src/GenTLWorker.hpp
  src/OperatorLibrary.cpp
  src/OperatorLibrary.hpp
  src/PropertyPanel.cpp
  src/PropertyPanel.hpp
)

target_include_directories(sieans_qt PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/src
)

target_link_libraries(sieans_qt PRIVATE
  Qt6::Widgets
  Qt6::Gui
  Qt6::Core
  sieans_algo
)

add_custom_command(TARGET sieans_qt POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E make_directory $<TARGET_FILE_DIR:sieans_qt>/resources
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
          ${CMAKE_CURRENT_SOURCE_DIR}/resources/sample-qr.png
          $<TARGET_FILE_DIR:sieans_qt>/resources/sample-qr.png
  COMMENT "Copy sample-qr.png beside sieans_qt")

install(TARGETS sieans_qt RUNTIME DESTINATION bin)
