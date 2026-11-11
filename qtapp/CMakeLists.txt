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

find_package(Qt6 REQUIRED COMPONENTS Widgets Gui Core Network)

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
  src/GeomOverlay.hpp
  src/GeomOverlay.cpp
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
  src/CommHub.cpp
  src/CommHub.hpp
  src/CommPanel.cpp
  src/CommPanel.hpp
  src/VarWatchPanel.cpp
  src/VarWatchPanel.hpp
  src/HostStrip.cpp
  src/HostStrip.hpp
  src/ExprEval.hpp
  src/ExprEval.cpp
  src/UvcCapture.hpp
  src/UvcCapture.cpp
  src/OperatorRail.hpp
  src/OperatorRail.cpp
  src/PropertyFloat.hpp
  src/PropertyFloat.cpp
  src/FlowTabBar.hpp
  src/FlowTabBar.cpp
  src/FilmstripBar.hpp
  src/FilmstripBar.cpp
  src/CompareStrip.hpp
  src/CompareStrip.cpp
  src/SoftFrame.hpp
  src/SoftFrame.cpp
  src/HostStatePanel.hpp
  src/HostStatePanel.cpp
  src/TemplateMatch.hpp
  src/TemplateMatch.cpp
  src/LocateMatchPanel.hpp
  src/LocateMatchPanel.cpp
  src/CaliperMeasure.hpp
  src/CaliperMeasure.cpp
  src/DefectDetect.hpp
  src/DefectDetect.cpp
  src/FixturePose.hpp
  src/FixturePose.cpp
  src/GeometryFind.hpp
  src/GeometryFind.cpp
  src/MeasureDim.hpp
  src/MeasureDim.cpp
  src/SerialExchange.hpp
  src/SerialExchange.cpp
  src/ProtocolNet.hpp
  src/ProtocolNet.cpp
  src/ModbusClient.hpp
  src/ModbusClient.cpp
  src/S7Client.hpp
  src/S7Client.cpp
  src/OpcUaClient.hpp
  src/OpcUaClient.cpp
  src/MqttClient.hpp
  src/MqttClient.cpp
  src/YoloInfer.hpp
  src/YoloInfer.cpp
  src/YoloOnnx.hpp
  src/YoloOnnx.cpp
  src/WorkbenchPaths.hpp
  src/WorkbenchPaths.cpp
  src/CloudOps.hpp
  src/CloudOps.cpp
  src/SocketExchange.hpp
  src/SocketExchange.cpp
  src/FlowExtras.hpp
  src/FlowExtras.cpp
  src/PythonExt.hpp
  src/PythonExt.cpp
  src/ConditionEval.hpp
  src/ConditionEval.cpp
  src/SubflowExec.hpp
  src/SubflowExec.cpp
  src/SubflowDialog.hpp
  src/SubflowDialog.cpp
  src/FlowMinimap.hpp
  src/FlowMinimap.cpp
  src/FlowIoDialog.hpp
  src/FlowIoDialog.cpp
)

target_include_directories(sieans_qt PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/src
)

target_link_libraries(sieans_qt PRIVATE
  Qt6::Widgets
  Qt6::Gui
  Qt6::Core
  Qt6::Network
  sieans_algo
)

# Optional ONNX Runtime headers (real YOLO path). The library is loaded with
# dlopen at runtime so a machine without ORT can still run the software fallback.
target_link_libraries(sieans_qt PRIVATE ${CMAKE_DL_LIBS})
set(_sieans_ort "")
if(DEFINED ENV{SIEANS_ONNXRUNTIME_DIR} AND EXISTS "$ENV{SIEANS_ONNXRUNTIME_DIR}/include/onnxruntime_c_api.h")
  set(_sieans_ort "$ENV{SIEANS_ONNXRUNTIME_DIR}")
elseif(EXISTS "$ENV{HOME}/.local/opt/onnxruntime/include/onnxruntime_c_api.h")
  set(_sieans_ort "$ENV{HOME}/.local/opt/onnxruntime")
endif()
if(_sieans_ort)
  message(STATUS "SIEANS ONNX Runtime headers: ${_sieans_ort}")
  target_compile_definitions(sieans_qt PRIVATE SIEANS_HAS_ONNXRUNTIME=1)
  target_include_directories(sieans_qt PRIVATE "${_sieans_ort}/include")
else()
  message(STATUS "SIEANS ONNX Runtime headers not found — YOLO uses software fallback only")
endif()

add_custom_command(TARGET sieans_qt POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E make_directory $<TARGET_FILE_DIR:sieans_qt>/resources
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
          ${CMAKE_CURRENT_SOURCE_DIR}/resources/sample-qr.png
          $<TARGET_FILE_DIR:sieans_qt>/resources/sample-qr.png
  COMMENT "Copy sample-qr.png beside sieans_qt")

install(TARGETS sieans_qt RUNTIME DESTINATION bin)
