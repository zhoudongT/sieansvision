#include "PropertyPanel.hpp"

#include "Theme.hpp"

#include <QCheckBox>
#include <QComboBox>
#include <QDoubleSpinBox>
#include <QFormLayout>
#include <QHeaderView>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLineEdit>
#include <QMetaType>
#include <QSpinBox>
#include <QTableWidget>
#include <QShortcut>
#include <QClipboard>
#include <QApplication>
#include <QGuiApplication>
#include <QKeySequence>
#include <QFrame>
#include <QPushButton>
#include <QHBoxLayout>
#include <QVBoxLayout>

namespace sieans_qt {
namespace {

QString stringify(const QVariant& v) {
  if (v.typeId() == QMetaType::QVariantMap || v.typeId() == QMetaType::QVariantList) {
    return QString::fromUtf8(
        QJsonDocument::fromVariant(v).toJson(QJsonDocument::Compact));
  }
  if (v.typeId() == QMetaType::Bool)
    return v.toBool() ? QStringLiteral("true") : QStringLiteral("false");
  return v.toString();
}

}  // namespace

QVector<PropertyPanel::Spec> PropertyPanel::specsFor(const QString& op) {
  auto S = [](const char* key, const char* label, int kind, const char* choices) {
    Spec spec;
    spec.key = QString::fromUtf8(key);
    spec.label = QString::fromUtf8(label);
    spec.kind = kind;
    spec.choices = QString::fromUtf8(choices);
    return spec;
  };
  constexpr int kLine = 0, kInt = 1, kReal = 2, kBool = 3, kChoice = 4;
  if (op == QLatin1String("source:local")) {
    return {S("cam.imageSource", "图像源", kChoice, "local|本地图像;camera|相机;sdk|SDK"),
            S("cam.pixelFormat", "像素格式", kChoice, "MONO8|MONO8;RGB24|RGB24"),
            S("cam.autoSwitch", "自动切换", kBool, "")};
  }
  if (op == QLatin1String("source:sdk")) {
    return {S("cam.imageSource", "图像源", kChoice, "local|本地图像;camera|相机;sdk|SDK"),
            S("cam.sdkNote", "SDK 说明", kLine, "")};
  }
  if (op == QLatin1String("source") || op == QLatin1String("source:camera")) {
    return {S("cam.imageSource", "图像源", kChoice, "local|本地图像;camera|相机;sdk|SDK"),
            S("cam.backendKind", "采集后端", kChoice, "gentl|GenTL;uvc|UVC;soft|Soft 仿真"),
            S("cam.deviceId", "设备", kLine, ""),
            S("cam.continuousLive", "连续预览", kBool, ""),
            S("cam.exposureTime", "曝光 µs", kReal, ""),
            S("cam.gainDb", "增益 dB", kReal, ""),
            S("cam.acquisitionFrameRate", "帧率", kReal, ""),
            S("cam.trigger", "触发", kChoice, "freerun|自由运行;software|软触发;line0|Line0")};
  }
  if (op == QLatin1String("camera_capture")) {
    return {S("backendKind", "采集后端", kChoice, "gentl|GenTL;uvc|UVC;soft|Soft 仿真"),
            S("deviceId", "设备", kLine, ""),
            S("continuousLive", "连续预览", kBool, ""),
            S("exposureTime", "曝光 µs", kReal, ""),
            S("gainDb", "增益 dB", kReal, ""),
            S("trigger", "触发", kChoice, "freerun|自由运行;software|软触发;line0|Line0")};
  }
  if (op == QLatin1String("locate")) {
    return {S("templateSource", "模板来源", kChoice,
              "file|文件路径;soft_plate|软场景标牌;capture|从当前图截取"),
            S("templatePath", "模板文件", kLine, ""),
            S("templateW", "截取宽", kInt, ""),
            S("templateH", "截取高", kInt, ""),
            S("minScore", "最低分数", kReal, ""),
            S("maxMatches", "最多目标", kInt, ""),
            S("overlapThreshold", "去重重叠", kReal, "0.3"),
            S("angleEnable", "搜索旋转", kBool, ""),
            S("angleStart", "起始角度", kReal, ""),
            S("angleEnd", "终止角度", kReal, ""),
            S("angleStep", "角度步长", kReal, "")};
  }
  if (op == QLatin1String("pose_correct")) {
    return {S("fixtureSource", "位姿来源", kChoice,
              "auto|自动上游定位;bind|绑定步骤;manual|手动基准"),
            S("bindStepId", "绑定步骤", kLine, "空=最近 locate"),
            S("autoBindLocate", "自动绑定 locate", kBool, ""),
            S("baseX", "基准 X", kReal, ""),
            S("baseY", "基准 Y", kReal, ""),
            S("baseAngle", "基准角度", kReal, ""),
            S("baseScale", "基准缩放", kReal, ""),
            S("followRoi", "下游 ROI 跟随", kBool, ""),
            S("resultVar", "结果前缀", kLine, "fixture"),
            S("axisLength", "轴长度", kReal, ""),
            S("showAxes", "显示坐标轴", kBool, ""),
            S("writeFlowVars", "写入流程变量", kBool, "")};
  }
  if (op == QLatin1String("preprocess")) {
    return {S("mode", "方法", kChoice, "gray|灰度;mono|灰度;invert|反色;threshold|阈值"),
            S("threshold", "阈值", kInt, "")};
  }
  if (op == QLatin1String("barcode") || op == QLatin1String("qr_decode")) {
    return {S("types", "码制", kLine, ""),
            S("maxCodes", "最多码数", kInt, ""),
            S("judgeEnable", "启用判定", kBool, ""),
            S("judgeMinCount", "最少码数", kInt, ""),
            S("showOverlay", "显示码框", kBool, "")};
  }
  if (op == QLatin1String("ocr")) {
    return {S("lang", "语言", kLine, "eng"),
            S("psm", "PSM", kInt, "6=块 7=行"),
            S("judgeEnable", "启用判定", kBool, ""),
            S("judgeMinCount", "最少行数", kInt, ""),
            S("minConfidence", "最低置信度", kInt, ""),
            S("showOverlay", "显示文本框", kBool, "")};
  }
  if (op == QLatin1String("defects")) {
    return {S("referenceSource", "参考来源", kChoice,
              "file|文件路径;soft_scene|软仿真场景;soft_scene_blemish|软场景+斑块"),
            S("referencePath", "参考图路径", kLine, "同尺寸良品图"),
            S("scaleReference", "尺寸不一致时缩放", kBool, ""),
            S("differenceThreshold", "灰度差异阈值", kInt, "1–255"),
            S("minArea", "最小区域面积", kInt, ""),
            S("maxCount", "最多缺陷数", kInt, ""),
            S("blur", "模糊核", kInt, "0=无，默认 3"),
            S("ignoreBottomPx", "忽略底部像素", kInt, "避开 soft HUD"),
            S("roiX", "ROI X", kInt, ""),
            S("roiY", "ROI Y", kInt, ""),
            S("roiW", "ROI 宽", kInt, ""),
            S("roiH", "ROI 高", kInt, ""),
            S("judgeEnable", "启用判定", kBool, ""),
            S("judgeMaxCount", "允许最大个数", kInt, "0=有缺陷即 NG"),
            S("judgeMaxRatio", "允许最大比例", kReal, ""),
            S("maxDefectRatio", "关闭判定时允许比例", kReal, ""),
            S("resultVar", "结果前缀", kLine, "defects → defectsCount"),
            S("writePassGate", "写入 passGate", kBool, ""),
            S("showOverlay", "显示缺陷框", kBool, ""),
            S("showLabels", "显示面积标签", kBool, ""),
            S("followFixture", "跟随定位位姿", kBool, "ROI 在夹具坐标系"),
            S("fixtureVar", "位姿变量前缀", kLine, "fixture")};
  }
  if (op == QLatin1String("yolo") || op == QLatin1String("yolo_segment")) {
    QVector<Spec> f = {
        S("model", "模型文件", kLine, "yolo11n.pt / yolo11n-seg.pt（models/，不自动下载）"),
        S("device", "推理设备", kChoice, "cpu|CPU;auto|自动;cuda:0|cuda:0"),
        S("confidence", "置信度阈值", kReal, "默认 0.25"),
        S("iou", "NMS IoU", kReal, "默认 0.45"),
        S("imageSize", "输入边长", kInt, "32 的倍数；检测 32–1920，分割 32–1280"),
        S("classes", "类别筛选", kLine, "空=全部；逗号分隔 id 或名称"),
        S("maxDetections", "最多检出", kInt, "分割 1–100，默认 50"),
        S("minArea", "最小面积", kInt, "默认 1"),
        S("resultVar", "结果前缀", kLine, "yolo → yoloCount / yoloSeg → yoloSegCount"),
        S("showOverlay", "显示叠加", kBool, ""),
        S("showLabels", "显示标签", kBool, ""),
        S("followFixture", "跟随定位位姿", kBool, "ROI 在夹具坐标系"),
        S("fixtureVar", "位姿变量前缀", kLine, "fixture"),
        S("roiX", "ROI X", kInt, ""),
        S("roiY", "ROI Y", kInt, ""),
        S("roiW", "ROI 宽", kInt, ""),
        S("roiH", "ROI 高", kInt, "")};
    if (op == QLatin1String("yolo_segment")) {
      f.append(S("contourTolerance", "轮廓简化容差", kReal, "默认 0.5，不改变面积"));
      f.append(S("overlayAlpha", "叠加透明度", kReal, "默认 0.35"));
      f.append(S("output", "输出模式", kChoice, "overlay|彩色叠加（下游仍用原图）;mask|二值掩膜"));
    }
    return f;
  }
  if (op == QLatin1String("geometry")) {
    return {S("feature", "特征类型", kChoice,
              "contours|轮廓;lines|直线;circles|圆;rects|矩形;edges|边缘"),
            S("target", "软场景目标", kChoice,
              "|手动ROI;soft_circle|软圆;soft_line|软直线;soft_follow|软跟随圆"),
            S("threshold", "轮廓二值阈值", kInt, "0–255"),
            S("minArea", "最小轮廓面积", kInt, ""),
            S("invert", "反色提取深色目标", kBool, ""),
            S("filterSize", "平滑半径", kInt, "1=不模糊"),
            S("maxCount", "最多特征数", kInt, "1–100"),
            S("cannyLow", "Canny 低阈值", kInt, ""),
            S("cannyHigh", "Canny 高阈值", kInt, ""),
            S("edgeThreshold", "边缘阈值", kInt, "覆盖 cannyLow"),
            S("votes", "霍夫投票阈值", kInt, ""),
            S("minLength", "最小直线长度", kInt, ""),
            S("maxGap", "最大间隙", kInt, ""),
            S("minDistance", "圆心最小间距", kInt, ""),
            S("minRadius", "最小半径", kInt, ""),
            S("maxRadius", "最大半径", kInt, ""),
            S("annulusInner", "扇环内径", kInt, "0=不限制"),
            S("annulusOuter", "扇环外径", kInt, "0=不限制"),
            S("angleNormalize", "角度归一化 0–180", kBool, ""),
            S("reverseFind", "互换直线端点", kBool, ""),
            S("roiX", "ROI X", kInt, ""),
            S("roiY", "ROI Y", kInt, ""),
            S("roiW", "ROI 宽", kInt, ""),
            S("roiH", "ROI 高", kInt, ""),
            S("judgeEnable", "启用判定", kBool, ""),
            S("judgeMin", "判定下限", kReal, "半径/长度/面积"),
            S("judgeMax", "判定上限", kReal, ""),
            S("resultVar", "结果前缀", kLine, "geom → geomCount"),
            S("writePassGate", "写入 passGate", kBool, ""),
            S("showOverlay", "显示特征", kBool, ""),
            S("showLabels", "显示标签", kBool, ""),
            S("followFixture", "跟随定位位姿", kBool, "ROI 在夹具坐标系"),
            S("fixtureVar", "位姿变量前缀", kLine, "fixture")};
  }
  if (op == QLatin1String("measure")) {
    return {S("feature", "测量对象", kChoice,
              "circles|圆直径/半径;lines|直线长度;points|两点距离;angle|夹角;contours|轮廓外接矩形;caliper|卡尺间距"),
            S("target", "软场景目标", kChoice,
              "|手动/ROI;soft_circle|软圆;soft_line|软直线;soft_points|软直线两端;soft_angle|软直线⊥垂直;soft_bars|软卡尺条"),
            S("pxPerMm", "像素/毫米", kReal, "0=仅像素；与标定二选一"),
            S("unit", "单位", kLine, "px 或 mm"),
            S("calDistance", "标定点实际距离", kReal, "配合 calX1..calY2"),
            S("calX1", "标定点1 X", kReal, ""),
            S("calY1", "标定点1 Y", kReal, ""),
            S("calX2", "标定点2 X", kReal, ""),
            S("calY2", "标定点2 Y", kReal, ""),
            S("x1", "点1 / 线1起点 X", kReal, ""),
            S("y1", "点1 / 线1起点 Y", kReal, ""),
            S("x2", "点2 / 线1终点 X", kReal, ""),
            S("y2", "点2 / 线1终点 Y", kReal, ""),
            S("x3", "线2起点 X", kReal, "夹角"),
            S("y3", "线2起点 Y", kReal, ""),
            S("x4", "线2终点 X", kReal, ""),
            S("y4", "线2终点 Y", kReal, ""),
            S("threshold", "轮廓阈值", kInt, ""),
            S("minArea", "最小面积", kInt, ""),
            S("invert", "深色目标", kBool, ""),
            S("minRadius", "最小半径", kInt, ""),
            S("maxRadius", "最大半径", kInt, ""),
            S("minLength", "最小直线长度", kInt, ""),
            S("votes", "霍夫投票", kInt, ""),
            S("roiX", "ROI X", kInt, ""),
            S("roiY", "ROI Y", kInt, ""),
            S("roiW", "ROI 宽", kInt, ""),
            S("roiH", "ROI 高", kInt, ""),
            S("judgeEnable", "启用判定", kBool, ""),
            S("judgeMin", "判定下限", kReal, "直径/长度/角度/间距"),
            S("judgeMax", "判定上限", kReal, ""),
            S("resultVar", "结果前缀", kLine, "measure → measureDiameter"),
            S("writePassGate", "写入 passGate", kBool, ""),
            S("showOverlay", "显示标注", kBool, ""),
            S("showLabels", "显示标签", kBool, ""),
            S("followFixture", "跟随定位位姿", kBool, ""),
            S("fixtureVar", "位姿变量前缀", kLine, "fixture")};
  }
  if (op == QLatin1String("caliper")) {
    return {S("direction", "方向", kChoice, "horizontal|水平;vertical|垂直"),
            S("target", "目标", kLine, "soft_bars|软靶 / 空=ROI"),
            S("roiX", "ROI X", kInt, ""),
            S("roiY", "ROI Y", kInt, ""),
            S("roiW", "ROI 宽", kInt, ""),
            S("roiH", "ROI 高", kInt, ""),
            S("threshold", "边缘阈值", kInt, ""),
            S("polarity", "极性", kChoice, "any|任意;dark_to_light|暗→亮;light_to_dark|亮→暗"),
            S("pxPerMm", "像素/毫米", kReal, "0=仅像素"),
            S("bandHalf", "扫描半宽", kInt, ""),
            S("judgeEnable", "启用判定", kBool, ""),
            S("judgeMinPx", "最小间距 px", kReal, ""),
            S("judgeMaxPx", "最大间距 px", kReal, ""),
            S("showOverlay", "显示卡尺", kBool, ""),
            S("followFixture", "跟随定位位姿", kBool, ""),
            S("fixtureVar", "位姿变量前缀", kLine, "fixture")};
  }
  if (op == QLatin1String("var_calc")) {
    return {S("scope", "作用域", kChoice, "flow|流程;global|全局")};
  }
  if (op == QLatin1String("format_data")) {
    return {S("template", "模板 {name}/${flow.x}/{{name}}", kLine, ""),
            S("args", "参数变量 CSV", kLine, ""),
            S("targetVar", "目标变量", kLine, ""),
            S("emptyDefault", "空结果默认", kLine, "空输出时的占位报文（如 BARCODE empty）")};
  }
  if (op == QLatin1String("result_gate")) {
    return {S("minCount", "最少码数", kInt, ""),
            S("sourceVar", "源变量", kLine, ""),
            S("passVar", "输出变量", kLine, "")};
  }
  if (op == QLatin1String("send_data")) {
    return {S("device", "设备 LocalLoop/TCP", kLine, ""),
            S("message", "报文 ${flow.x}", kLine, "")};
  }
  if (op == QLatin1String("receive_data")) {
    return {S("device", "设备 LocalLoop/TCP", kLine, ""),
            S("targetVar", "目标变量", kLine, ""),
            S("timeoutMs", "超时 ms", kInt, "")};
  }
  if (op == QLatin1String("save_image")) {
    return {S("dir", "目录", kLine, "")};
  }
  if (op == QLatin1String("condition")) {
    return {S("logic", "规则逻辑", kChoice, "and|全部满足 (AND);or|任一满足 (OR)"),
            S("comparison", "判断方式", kChoice,
              "eq|等于;ne|不等于;gt|大于;gte|大于等于;lt|小于;lte|小于等于;"
              "contains|包含;starts_with|开头是;ends_with|结尾是;regex|正则;"
              "empty|为空;not_empty|非空;is_true|为真;is_false|为假"),
            S("left", "左侧值 / 变量", kLine, "barcodeCount / ${flow.ocrOk} / 1"),
            S("right", "右侧值 / 变量", kLine, ""),
            S("writePassGate", "写入 passGate", kBool, "")};
  }
  if (op == QLatin1String("branch")) {
    return {S("defaultPathId", "默认路径", kLine, "default")};
  }
  if (op == QLatin1String("branch_merge")) {
    return {};
  }
  if (op == QLatin1String("serial_exchange")) {
    return {S("connection", "串口连接", kChoice, "simulator|回环模拟;device|真实端口 / PTY"),
            S("mode", "通信方式", kChoice, "exchange|请求应答;send|仅发送;receive|仅接收"),
            S("serialPort", "服务器串口路径", kLine, "/dev/ttyUSB0 或 SerialLoopback"),
            S("baudrate", "波特率", kInt, "300–4000000"),
            S("dataBits", "数据位", kChoice, "5|5;6|6;7|7;8|8"),
            S("parity", "校验位", kChoice, "N|无;E|偶;O|奇;M|标记;S|空号"),
            S("stopbits", "停止位", kChoice, "1|1;1.5|1.5;2|2"),
            S("flowControl", "流量控制", kChoice, "none|无;rtscts|RTS/CTS;xonxoff|XON/XOFF;dsrdtr|DSR/DTR"),
            S("rts", "打开时 RTS 状态", kBool, ""),
            S("dtr", "打开时 DTR 状态", kBool, ""),
            S("encoding", "发送内容格式", kChoice, "text|文本;structured|结构化 JSON;bytes|字节"),
            S("responseEncoding", "接收内容格式", kChoice, "text|文本;structured|结构化 JSON;bytes|字节"),
            S("value", "发送内容", kLine, "支持 ${flow.x} / {name}"),
            S("timeoutMs", "通信超时 (ms)", kInt, "100–10000"),
            S("maxBytes", "接收字节上限", kInt, ""),
            S("clearInput", "发送前丢弃已有接收数据", kBool, ""),
            S("txFraming", "发送分帧方式", kChoice,
              "raw|原始;lf|LF;crlf|CRLF;nul|NUL;length16be|长度16BE;length16le|长度16LE;length32be|长度32BE;length32le|长度32LE"),
            S("rxFraming", "接收完成条件", kChoice,
              "lf|LF;crlf|CRLF;nul|NUL;length16be|长度16BE;length16le|长度16LE;length32be|长度32BE;length32le|长度32LE;fixed|定长"),
            S("responseBytes", "应答字节数", kInt, "定长分帧时使用"),
            S("resultVar", "结果变量前缀", kLine, "serial")};
  }
  if (op == QLatin1String("modbus_read") || op == QLatin1String("modbus_write") ||
      op == QLatin1String("modbus_wait")) {
    QVector<Spec> specs;
    specs << S("transport", "连接方式", kChoice, "simulator|模拟器;tcp|Modbus TCP;rtu|Modbus RTU");
    specs << S("host", "设备 IP / 主机名", kLine, "127.0.0.1");
    specs << S("port", "TCP 端口", kInt, "回环软从站默认 1502");
    specs << S("serialPort", "串口路径", kLine, "/dev/ttyUSB0 或 ModbusRtuLoopback");
    specs << S("baudrate", "波特率", kInt, "");
    specs << S("parity", "校验位", kChoice, "N|无;E|偶;O|奇");
    specs << S("stopbits", "停止位", kChoice, "1|1;2|2");
    specs << S("deviceId", "设备站号", kInt, "0–255");
    specs << S("area", "数据区域", kChoice, "holding|保持寄存器;input|输入寄存器;coils|线圈;discrete|离散输入");
    specs << S("address", "起始地址（从 0 开始）", kInt, "不要把手册 40001 直接当 0");
    specs << S("dataType", "数据类型", kChoice,
              "uint16|uint16;int16|int16;uint32|uint32;int32|int32;float32|float32;float64|float64");
    specs << S("byteOrder", "字节序", kChoice, "big|大端;little|小端");
    specs << S("wordOrder", "字序", kChoice, "big|大端;little|小端");
    specs << S("timeoutMs", "超时 (ms)", kInt, "100–10000");
    if (op == QLatin1String("modbus_read"))
      specs << S("count", "读取值数量", kInt, "32/64 位占多个寄存器");
    if (op == QLatin1String("modbus_write"))
      specs << S("value", "写入值", kLine, "数值 / true false / 或绑定变量");
    if (op == QLatin1String("modbus_wait")) {
      specs << S("comparison", "信号条件", kChoice,
                "eq|等于;ne|不等于;gt|大于;gte|大于等于;lt|小于;lte|小于等于;is_true|开关为是;is_false|开关为否");
      specs << S("expectedValue", "比较值", kReal, "");
      specs << S("triggerMode", "触发方式", kChoice, "level|电平;rising|上升沿;falling|下降沿");
      specs << S("pollIntervalMs", "采样间隔 (ms)", kInt, "");
      specs << S("stableMs", "连续采样稳定时间 (ms)", kInt, "");
      specs << S("waitTimeoutMs", "等待超时 (ms)", kInt, "");
      specs << S("onTimeout", "超时处理", kChoice, "error|报错停止;continue|继续并置 triggered=false");
    }
    specs << S("resultVar", "结果变量前缀", kLine, "mbRead / mbWrite / mbWait");
    return specs;
  }
  if (op == QLatin1String("s7_read") || op == QLatin1String("s7_write")) {
    QVector<Spec> specs;
    specs << S("connection", "连接方式", kChoice, "simulator|模拟器;plc|真实 PLC / 软从站");
    specs << S("host", "设备 IP / 主机名", kLine, "127.0.0.1");
    specs << S("port", "TCP 端口", kInt, "软从站默认 1102（102 需特权）");
    specs << S("rack", "机架号", kInt, "0–7");
    specs << S("slot", "槽号", kInt, "0–31");
    specs << S("area", "数据区域", kChoice, "db|DB 数据块;mk|M 标志;pe|I 输入;pa|Q 输出");
    specs << S("dbNumber", "数据块编号", kInt, "仅 DB 区使用");
    specs << S("byteOffset", "字节偏移（从 0 开始）", kInt, "DB1.DBW10 填 10");
    specs << S("dataType", "数据类型", kChoice,
              "bool|BOOL;uint8|uint8;int8|int8;uint16|uint16;int16|int16;uint32|uint32;int32|int32;float32|float32;float64|float64");
    specs << S("bitOffset", "位偏移", kInt, "BOOL 使用 0–7");
    specs << S("timeoutMs", "事务超时 (ms)", kInt, "100–10000");
    if (op == QLatin1String("s7_read"))
      specs << S("count", "读取值数量", kInt, "单次最多 200 字节");
    if (op == QLatin1String("s7_write"))
      specs << S("value", "写入值", kLine, "数值 / true false / 或绑定变量");
    specs << S("resultVar", "结果变量前缀", kLine, "s7Read / s7Write");
    return specs;
  }
  if (op == QLatin1String("opcua_read") || op == QLatin1String("opcua_write") ||
      op == QLatin1String("opcua_browse") || op == QLatin1String("opcua_wait")) {
    QVector<Spec> specs;
    specs << S("connection", "连接目标", kChoice, "simulator|模拟器;server|真实服务器 / 软从站");
    specs << S("endpoint", "服务器端点", kLine, "opc.tcp://127.0.0.1:4840/sieans/");
    specs << S("security", "安全策略", kChoice, "None|None;Basic256Sha256|Basic256Sha256");
    specs << S("applicationUri", "客户端应用 URI", kLine, "urn:sieans:vision:client");
    specs << S("namespaceUri", "命名空间 URI（可选）", kLine, "urn:sieans:simulator");
    specs << S("nodeId", "节点地址", kLine, "ns=2;s=SIEANS.Count");
    specs << S("timeoutMs", "通信超时 (ms)", kInt, "100–10000");
    if (op == QLatin1String("opcua_read"))
      specs << S("requireGood", "仅接受良好数据质量", kChoice, "true|是;false|否");
    if (op == QLatin1String("opcua_write")) {
      specs << S("dataType", "节点值类型", kChoice,
                "Boolean|Boolean;SByte|SByte;Byte|Byte;Int16|Int16;UInt16|UInt16;"
                "Int32|Int32;UInt32|UInt32;Int64|Int64;UInt64|UInt64;"
                "Float|Float;Double|Double;String|String;DateTime|DateTime;"
                "Guid|Guid;ByteString|ByteString");
      specs << S("value", "写入值", kLine, "数值 / true false / 或绑定变量");
    }
    if (op == QLatin1String("opcua_browse"))
      specs << S("browseLimit", "单层浏览上限", kInt, "1–500");
    if (op == QLatin1String("opcua_wait")) {
      specs << S("comparison", "信号条件", kChoice,
                "eq|等于;ne|不等于;gt|大于;gte|大于等于;lt|小于;lte|小于等于;is_true|为真;is_false|为假");
      specs << S("expectedValue", "比较值", kLine, "有限数值");
      specs << S("triggerMode", "触发方式", kChoice, "level|条件成立;rising|上升沿;falling|下降沿");
      specs << S("publishingIntervalMs", "请求发布/采样间隔 (ms)", kInt, "20–10000");
      specs << S("waitTimeoutMs", "等待超时 (ms)", kInt, "100–600000");
      specs << S("onTimeout", "超时处理", kChoice, "error|报错;continue|继续");
    }
    specs << S("resultVar", "结果变量前缀", kLine, "opcRead / opcWrite / opcBrowse / opcWait");
    return specs;
  }
  if (op == QLatin1String("mqtt_publish") || op == QLatin1String("mqtt_receive")) {
    QVector<Spec> specs;
    specs << S("connection", "消息服务器", kChoice, "simulator|模拟器;broker|真实代理 / 软代理");
    specs << S("host", "服务器 IP / 主机名", kLine, "127.0.0.1");
    specs << S("port", "MQTT 端口", kInt, "软代理默认 1883");
    specs << S("security", "连接安全", kChoice, "plain|明文;tls|TLS");
    specs << S("clientId", "客户端标识（空白自动生成）", kLine, "");
    specs << S("topic", "消息主题", kLine, "sieans/inspection");
    specs << S("encoding", "消息内容格式", kChoice, "structured|结构化;text|文本;bytes|字节数组");
    specs << S("qos", "QoS 等级", kInt, "0–2");
    specs << S("timeoutMs", "操作总超时 (ms)", kInt, "100–60000");
    if (op == QLatin1String("mqtt_publish")) {
      specs << S("retain", "服务器保留最后一条消息", kChoice, "true|是;false|否");
      specs << S("value", "发布内容", kLine, "文本 / JSON / 或绑定变量");
    }
    if (op == QLatin1String("mqtt_receive"))
      specs << S("acceptRetained", "允许读取服务器保留消息", kChoice, "true|是;false|否");
    specs << S("resultVar", "结果变量前缀", kLine, "mqttPub / mqttRecv");
    return specs;
  }
  if (op == QLatin1String("subflow") || op == QLatin1String("loop")) {
    QVector<Spec> specs;
    specs << S("subflowId", "子流程", kChoice, "");
    specs << S("stateMode", "局部状态", kChoice, "reset|每次重置;preserve|保留上次");
    if (op == QLatin1String("loop")) {
      specs << S("mode", "循环模式", kChoice, "count|固定次数;until|直到条件");
      specs << S("iterations", "次数 / 上限", kInt, "1–100");
      specs << S("frameMode", "图像帧", kChoice, "previous|上一轮;original|原始帧");
      specs << S("stopField", "停止字段", kLine, "passed");
      specs << S("stopValue", "停止值", kBool, "");
    }
    return specs;
  }
  return {};
}

PropertyPanel::PropertyPanel(QWidget* parent) : QWidget(parent) {
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(6, 6, 6, 6);
  lay->setSpacing(4);
  title_ = new QLabel(QStringLiteral("属性"));
  title_->setObjectName(QStringLiteral("sectionTitle"));
  lay->addWidget(title_);
  meta_ = new QLabel(QStringLiteral("选中流程节点以编辑参数"));
  meta_->setObjectName(QStringLiteral("muted"));
  meta_->setWordWrap(true);
  lay->addWidget(meta_);
  filterEdit_ = new QLineEdit;
  filterEdit_->setObjectName(QStringLiteral("propFilter"));
  filterEdit_->setPlaceholderText(QStringLiteral("过滤参数 · Ctrl+F · Esc 清空"));
  filterEdit_->setClearButtonEnabled(true);
  filterEdit_->setToolTip(QStringLiteral("属性过滤 · 匹配键/标签 · Ctrl+F 聚焦 · Esc 清空"));
  lay->addWidget(filterEdit_);
  connect(filterEdit_, &QLineEdit::textChanged, this, [this](const QString&) { applyFilter(); });
  {
    auto* scF = new QShortcut(QKeySequence(QStringLiteral("Ctrl+F")), this);
    connect(scF, &QShortcut::activated, this, &PropertyPanel::focusFilter);
    auto* scEsc = new QShortcut(QKeySequence(Qt::Key_Escape), filterEdit_);
    connect(scEsc, &QShortcut::activated, this, [this]() {
      if (filterEdit_ && !filterEdit_->text().isEmpty()) filterEdit_->clear();
    });
  }
  {
    auto* scCopy = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+C")), this);
    connect(scCopy, &QShortcut::activated, this, &PropertyPanel::copyVisibleParams);
    auto* scPaste = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+V")), this);
    connect(scPaste, &QShortcut::activated, this, &PropertyPanel::pasteKeyValueParams);
    auto* scJ = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+J")), this);
    connect(scJ, &QShortcut::activated, this, &PropertyPanel::exportParamsJson);
    auto* scO = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+O")), this);
    connect(scO, &QShortcut::activated, this, &PropertyPanel::importParamsJson);
  }
  setStatusTip(QStringLiteral("属性面板 · Ctrl+F · Esc 清过滤 · Ctrl+Shift+C/V 键值 · Ctrl+Shift+J/O JSON · emptyDefault/{name}"));

  auto* scroll = new QScrollArea;
  scroll->setWidgetResizable(true);
  scroll->setFrameShape(QFrame::NoFrame);
  formHost_ = new QWidget;
  form_ = new QFormLayout(formHost_);
  form_->setContentsMargins(0, 0, 0, 0);
  form_->setSpacing(4);
  form_->setLabelAlignment(Qt::AlignLeft);
  scroll->setWidget(formHost_);
  lay->addWidget(scroll, 1);
}

void PropertyPanel::clear() {
  params_.clear();
  currentId_.clear();
  title_->setText(QStringLiteral("属性"));
  meta_->setText(QStringLiteral("选中流程节点以编辑参数"));
  while (form_->rowCount() > 0) form_->removeRow(0);
}

void PropertyPanel::emitEdit(const QString& key, const QString& value) {
  if (building_) return;
  params_.insert(key, value);
  emit paramEdited(currentId_, key, value);
}

void PropertyPanel::addExprTable(const QVariantList& rows) {
  auto* table = new QTableWidget(rows.size(), 3);
  table->setProperty("propKey", QStringLiteral("expressions"));
  table->setObjectName(QStringLiteral("exprTable"));
  table->setHorizontalHeaderLabels(
      {QStringLiteral("启用"), QStringLiteral("变量"), QStringLiteral("表达式")});
  table->horizontalHeader()->setStretchLastSection(true);
  table->horizontalHeader()->setSectionResizeMode(0, QHeaderView::ResizeToContents);
  table->horizontalHeader()->setSectionResizeMode(1, QHeaderView::ResizeToContents);
  table->verticalHeader()->setVisible(false);
  table->setMinimumHeight(140);
  for (int i = 0; i < rows.size(); ++i) {
    const QVariantMap row = rows[i].toMap();
    auto* en = new QTableWidgetItem;
    en->setFlags(Qt::ItemIsUserCheckable | Qt::ItemIsEnabled);
    const bool enabled =
        !row.contains(QStringLiteral("enabled")) || row.value(QStringLiteral("enabled")).toBool();
    en->setCheckState(enabled ? Qt::Checked : Qt::Unchecked);
    table->setItem(i, 0, en);
    auto* name = new QTableWidgetItem(row.value(QStringLiteral("name")).toString());
    table->setItem(i, 1, name);
    QString expr = row.value(QStringLiteral("expr")).toString();
    if (expr.isEmpty()) expr = row.value(QStringLiteral("expression")).toString();
    table->setItem(i, 2, new QTableWidgetItem(expr));
  }
  connect(table, &QTableWidget::itemChanged, this, [this, table](QTableWidgetItem*) {
    if (building_) return;
    QVariantList out;
    for (int r = 0; r < table->rowCount(); ++r) {
      QTableWidgetItem* en = table->item(r, 0);
      QTableWidgetItem* name = table->item(r, 1);
      QTableWidgetItem* expr = table->item(r, 2);
      if (!name || name->text().trimmed().isEmpty()) continue;
      QVariantMap row;
      row.insert(QStringLiteral("enabled"),
                 en && en->checkState() == Qt::Checked);
      row.insert(QStringLiteral("name"), name->text().trimmed());
      row.insert(QStringLiteral("expr"), expr ? expr->text() : QString());
      out.push_back(row);
    }
    emitEdit(QStringLiteral("expressions"),
             QString::fromUtf8(QJsonDocument::fromVariant(out).toJson(QJsonDocument::Compact)));
  });
  auto* exprLab = new QLabel(QStringLiteral("表达式"));
  exprLab->setProperty("propKey", QStringLiteral("expressions"));
  exprLab->setProperty("propLabel", QStringLiteral("表达式"));
  form_->addRow(exprLab, table);
}



static const char* kCmpChoices =
    "eq|等于;ne|不等于;gt|大于;gte|大于等于;lt|小于;lte|小于等于;"
    "contains|包含;starts_with|开头是;ends_with|结尾是;regex|正则;"
    "empty|为空;not_empty|非空;is_true|为真;is_false|为假";

void fillComparisonCombo(QComboBox* combo, const QString& cur) {
  const QStringList opts =
      QString::fromUtf8(kCmpChoices).split(QLatin1Char(';'), Qt::SkipEmptyParts);
  int pick = 0;
  for (int i = 0; i < opts.size(); ++i) {
    const QStringList pair = opts[i].split(QLatin1Char('|'));
    const QString val = pair.value(0);
    combo->addItem(pair.value(1, val), val);
    if (val == cur) pick = i;
  }
  combo->setCurrentIndex(pick);
}

void PropertyPanel::addRulesTable(const QVariantList& rows) {
  QVariantList use = rows;
  if (use.isEmpty()) {
    QVariantMap r;
    r.insert(QStringLiteral("left"), params_.value(QStringLiteral("left"), 0));
    r.insert(QStringLiteral("comparison"),
             params_.value(QStringLiteral("comparison"), QStringLiteral("eq")));
    r.insert(QStringLiteral("right"), params_.value(QStringLiteral("right"), 0));
    r.insert(QStringLiteral("enabled"), true);
    use.push_back(r);
  }
  auto* table = new QTableWidget(use.size(), 4);
  table->setObjectName(QStringLiteral("conditionRulesTable"));
  table->setProperty("propKey", QStringLiteral("rules"));
  table->setHorizontalHeaderLabels({QStringLiteral("启用"), QStringLiteral("左侧"),
                                    QStringLiteral("比较"), QStringLiteral("右侧")});
  table->horizontalHeader()->setStretchLastSection(true);
  table->horizontalHeader()->setSectionResizeMode(0, QHeaderView::ResizeToContents);
  table->verticalHeader()->setVisible(false);
  table->setMinimumHeight(140);
  auto emitRules = [this, table]() {
    if (building_) return;
    QVariantList out;
    for (int r = 0; r < table->rowCount(); ++r) {
      QTableWidgetItem* en = table->item(r, 0);
      QTableWidgetItem* left = table->item(r, 1);
      auto* cmp = qobject_cast<QComboBox*>(table->cellWidget(r, 2));
      QTableWidgetItem* right = table->item(r, 3);
      QVariantMap row;
      row.insert(QStringLiteral("enabled"), en && en->checkState() == Qt::Checked);
      row.insert(QStringLiteral("left"), left ? left->text() : QString());
      row.insert(QStringLiteral("comparison"),
                 cmp ? cmp->currentData().toString() : QStringLiteral("eq"));
      row.insert(QStringLiteral("right"), right ? right->text() : QString());
      out.push_back(row);
    }
    emitEdit(QStringLiteral("rules"),
             QString::fromUtf8(QJsonDocument::fromVariant(out).toJson(QJsonDocument::Compact)));
    if (!out.isEmpty()) {
      const QVariantMap r0 = out.first().toMap();
      emitEdit(QStringLiteral("left"), r0.value(QStringLiteral("left")).toString());
      emitEdit(QStringLiteral("comparison"), r0.value(QStringLiteral("comparison")).toString());
      emitEdit(QStringLiteral("right"), r0.value(QStringLiteral("right")).toString());
    }
  };
  for (int i = 0; i < use.size(); ++i) {
    const QVariantMap row = use[i].toMap();
    auto* en = new QTableWidgetItem;
    en->setFlags(Qt::ItemIsUserCheckable | Qt::ItemIsEnabled);
    const bool enabled =
        !row.contains(QStringLiteral("enabled")) || row.value(QStringLiteral("enabled")).toBool();
    en->setCheckState(enabled ? Qt::Checked : Qt::Unchecked);
    table->setItem(i, 0, en);
    table->setItem(i, 1, new QTableWidgetItem(row.value(QStringLiteral("left")).toString()));
    auto* cmp = new QComboBox;
    fillComparisonCombo(
        cmp, row.value(QStringLiteral("comparison"), QStringLiteral("eq")).toString());
    table->setCellWidget(i, 2, cmp);
    connect(cmp, QOverload<int>::of(&QComboBox::currentIndexChanged), this,
            [emitRules](int) { emitRules(); });
    table->setItem(i, 3, new QTableWidgetItem(row.value(QStringLiteral("right")).toString()));
  }
  connect(table, &QTableWidget::itemChanged, this, [emitRules](QTableWidgetItem*) { emitRules(); });

  auto* box = new QWidget;
  auto* v = new QVBoxLayout(box);
  v->setContentsMargins(0, 0, 0, 0);
  v->setSpacing(4);
  v->addWidget(table);
  auto* btns = new QHBoxLayout;
  auto* add = new QPushButton(QStringLiteral("添加规则"));
  auto* del = new QPushButton(QStringLiteral("删除选中"));
  btns->addWidget(add);
  btns->addWidget(del);
  btns->addStretch();
  v->addLayout(btns);
  connect(add, &QPushButton::clicked, this, [this, table, emitRules]() {
    const int r = table->rowCount();
    table->insertRow(r);
    auto* en = new QTableWidgetItem;
    en->setFlags(Qt::ItemIsUserCheckable | Qt::ItemIsEnabled);
    en->setCheckState(Qt::Checked);
    table->setItem(r, 0, en);
    table->setItem(r, 1, new QTableWidgetItem);
    auto* cmp = new QComboBox;
    fillComparisonCombo(cmp, QStringLiteral("eq"));
    table->setCellWidget(r, 2, cmp);
    connect(cmp, QOverload<int>::of(&QComboBox::currentIndexChanged), this,
            [emitRules](int) { emitRules(); });
    table->setItem(r, 3, new QTableWidgetItem);
    emitRules();
  });
  connect(del, &QPushButton::clicked, this, [table, emitRules]() {
    const int r = table->currentRow();
    if (r >= 0) table->removeRow(r);
    emitRules();
  });
  auto* lab = new QLabel(QStringLiteral("条件规则"));
  lab->setProperty("propKey", QStringLiteral("rules"));
  lab->setProperty("propLabel", QStringLiteral("条件规则"));
  form_->addRow(lab, box);
}

void PropertyPanel::addPathsTable(const QVariantList& rows) {
  QVariantList use = rows;
  if (use.isEmpty()) {
    use.push_back(QVariantMap{{QStringLiteral("id"), QStringLiteral("path1")},
                              {QStringLiteral("name"), QStringLiteral("分支1")},
                              {QStringLiteral("left"), QString()},
                              {QStringLiteral("comparison"), QStringLiteral("eq")},
                              {QStringLiteral("right"), QString()},
                              {QStringLiteral("enabled"), true}});
    use.push_back(QVariantMap{{QStringLiteral("id"), QStringLiteral("path2")},
                              {QStringLiteral("name"), QStringLiteral("分支2")},
                              {QStringLiteral("left"), QString()},
                              {QStringLiteral("comparison"), QStringLiteral("eq")},
                              {QStringLiteral("right"), QString()},
                              {QStringLiteral("enabled"), true}});
    use.push_back(QVariantMap{{QStringLiteral("id"), QStringLiteral("default")},
                              {QStringLiteral("name"), QStringLiteral("默认")},
                              {QStringLiteral("left"), QString()},
                              {QStringLiteral("comparison"), QStringLiteral("is_true")},
                              {QStringLiteral("right"), QString()},
                              {QStringLiteral("enabled"), true}});
  }
  auto* table = new QTableWidget(use.size(), 5);
  table->setObjectName(QStringLiteral("branchPathsTable"));
  table->setProperty("propKey", QStringLiteral("paths"));
  table->setHorizontalHeaderLabels({QStringLiteral("启用"), QStringLiteral("名称"),
                                    QStringLiteral("左侧"), QStringLiteral("比较"),
                                    QStringLiteral("右侧")});
  table->horizontalHeader()->setStretchLastSection(true);
  table->horizontalHeader()->setSectionResizeMode(0, QHeaderView::ResizeToContents);
  table->verticalHeader()->setVisible(false);
  table->setMinimumHeight(160);
  auto emitPaths = [this, table]() {
    if (building_) return;
    QVariantList out;
    for (int r = 0; r < table->rowCount(); ++r) {
      QTableWidgetItem* en = table->item(r, 0);
      QTableWidgetItem* name = table->item(r, 1);
      QTableWidgetItem* left = table->item(r, 2);
      auto* cmp = qobject_cast<QComboBox*>(table->cellWidget(r, 3));
      QTableWidgetItem* right = table->item(r, 4);
      QVariantMap row;
      const QString nm = name ? name->text().trimmed() : QString();
      const QString storedId = name ? name->data(Qt::UserRole).toString() : QString();
      row.insert(QStringLiteral("enabled"), en && en->checkState() == Qt::Checked);
      row.insert(QStringLiteral("name"), nm);
      row.insert(QStringLiteral("id"),
                 storedId.isEmpty()
                     ? (nm.isEmpty() ? QStringLiteral("path%1").arg(r + 1) : nm)
                     : storedId);
      row.insert(QStringLiteral("left"), left ? left->text() : QString());
      row.insert(QStringLiteral("comparison"),
                 cmp ? cmp->currentData().toString() : QStringLiteral("eq"));
      row.insert(QStringLiteral("right"), right ? right->text() : QString());
      out.push_back(row);
    }
    emitEdit(QStringLiteral("paths"),
             QString::fromUtf8(QJsonDocument::fromVariant(out).toJson(QJsonDocument::Compact)));
  };
  for (int i = 0; i < use.size(); ++i) {
    const QVariantMap row = use[i].toMap();
    auto* en = new QTableWidgetItem;
    en->setFlags(Qt::ItemIsUserCheckable | Qt::ItemIsEnabled);
    const bool enabled =
        !row.contains(QStringLiteral("enabled")) || row.value(QStringLiteral("enabled")).toBool();
    en->setCheckState(enabled ? Qt::Checked : Qt::Unchecked);
    table->setItem(i, 0, en);
    auto* name = new QTableWidgetItem(row.value(QStringLiteral("name")).toString());
    name->setData(Qt::UserRole, row.value(QStringLiteral("id")).toString());
    table->setItem(i, 1, name);
    table->setItem(i, 2, new QTableWidgetItem(row.value(QStringLiteral("left")).toString()));
    auto* cmp = new QComboBox;
    fillComparisonCombo(
        cmp, row.value(QStringLiteral("comparison"), QStringLiteral("eq")).toString());
    table->setCellWidget(i, 3, cmp);
    connect(cmp, QOverload<int>::of(&QComboBox::currentIndexChanged), this,
            [emitPaths](int) { emitPaths(); });
    table->setItem(i, 4, new QTableWidgetItem(row.value(QStringLiteral("right")).toString()));
  }
  connect(table, &QTableWidget::itemChanged, this, [emitPaths](QTableWidgetItem*) { emitPaths(); });
  auto* box = new QWidget;
  auto* v = new QVBoxLayout(box);
  v->setContentsMargins(0, 0, 0, 0);
  v->setSpacing(4);
  v->addWidget(table);
  auto* btns = new QHBoxLayout;
  auto* add = new QPushButton(QStringLiteral("添加路径"));
  auto* del = new QPushButton(QStringLiteral("删除选中"));
  btns->addWidget(add);
  btns->addWidget(del);
  btns->addStretch();
  v->addLayout(btns);
  connect(add, &QPushButton::clicked, this, [this, table, emitPaths]() {
    const int r = table->rowCount();
    table->insertRow(r);
    auto* en = new QTableWidgetItem;
    en->setFlags(Qt::ItemIsUserCheckable | Qt::ItemIsEnabled);
    en->setCheckState(Qt::Checked);
    table->setItem(r, 0, en);
    auto* name = new QTableWidgetItem(QStringLiteral("分支%1").arg(r + 1));
    name->setData(Qt::UserRole, QStringLiteral("path%1").arg(r + 1));
    table->setItem(r, 1, name);
    table->setItem(r, 2, new QTableWidgetItem);
    auto* cmp = new QComboBox;
    fillComparisonCombo(cmp, QStringLiteral("eq"));
    table->setCellWidget(r, 3, cmp);
    connect(cmp, QOverload<int>::of(&QComboBox::currentIndexChanged), this,
            [emitPaths](int) { emitPaths(); });
    table->setItem(r, 4, new QTableWidgetItem);
    emitPaths();
  });
  connect(del, &QPushButton::clicked, this, [table, emitPaths]() {
    const int r = table->currentRow();
    if (r >= 0) table->removeRow(r);
    emitPaths();
  });
  auto* lab = new QLabel(QStringLiteral("分支路径"));
  lab->setProperty("propKey", QStringLiteral("paths"));
  lab->setProperty("propLabel", QStringLiteral("分支路径"));
  form_->addRow(lab, box);
}

void PropertyPanel::addSpecRow(const Spec& spec, const QVariantMap& params) {
  const QString key = spec.key;
  const QString label = spec.label;
  const QVariant value = params.value(key);
  auto* lab = new QLabel(label);
  lab->setProperty("propKey", key);
  lab->setProperty("propLabel", label);
  const auto tipFor = [](const QString& k) -> QString {
    if (k == QLatin1String("emptyDefault"))
      return QStringLiteral("模板展开为空时写入的默认值（如 BARCODE empty）");
    if (k == QLatin1String("template"))
      return QStringLiteral("支持 {name} / ${flow.x} / {{name}}");
    if (k == QLatin1String("message"))
      return QStringLiteral("发送报文 · 支持 ${flow.x}/{name}/{{name}}");
    if (k == QLatin1String("sourceVar"))
      return QStringLiteral("result_gate 读取的源变量");
    if (k == QLatin1String("passVar"))
      return QStringLiteral("判定通过时写入的变量名（默认 passGate）");
    if (k == QLatin1String("deviceId") || k == QLatin1String("cam.deviceId"))
      return QStringLiteral("soft:0 / GenTL ID / /dev/videoN");
    if (k == QLatin1String("binding"))
      return QStringLiteral("通信绑定 · flow.formatted / LocalBus 设备名");
    if (k == QLatin1String("expressions") || k == QLatin1String("expression"))
      return QStringLiteral("expr · in/startswith/…/isempty/notempty · 见底部提示");
    if (k == QLatin1String("left") || k == QLatin1String("right"))
      return QStringLiteral("常量、引号文本，或变量 barcodeCount / ${flow.ocrOk}");
    if (k == QLatin1String("logic"))
      return QStringLiteral("多规则合成：AND 全部满足 / OR 任一满足");
    if (k == QLatin1String("writePassGate"))
      return QStringLiteral("判断结果写入 passGate，供 Host OK/NG 使用");
    if (k == QLatin1String("defaultPathId"))
      return QStringLiteral("未命中任何路径时走此路径 id");
    return {};
  };
  const QString tip = tipFor(key);
  if (!tip.isEmpty()) lab->setToolTip(tip);
  switch (spec.kind) {
    case 3: {
      auto* box = new QCheckBox(QStringLiteral("启用"));
      const QString s = stringify(value);
      box->setChecked(value.toBool() || s == QLatin1String("true") || s == QLatin1String("1"));
      connect(box, &QCheckBox::toggled, this, [this, key](bool on) {
        emitEdit(key, on ? QStringLiteral("true") : QStringLiteral("false"));
      });
      form_->addRow(lab, box);
      break;
    }
    case 1: {
      auto* spin = new QSpinBox;
      spin->setRange(-1000000, 10000000);
      spin->setValue(value.toInt());
      connect(spin, QOverload<int>::of(&QSpinBox::valueChanged), this,
              [this, key](int v) { emitEdit(key, QString::number(v)); });
      form_->addRow(lab, spin);
      break;
    }
    case 2: {
      auto* spin = new QDoubleSpinBox;
      const bool unit = key.contains(QStringLiteral("Score"), Qt::CaseInsensitive);
      const bool gain = key.contains(QStringLiteral("gain"), Qt::CaseInsensitive);
      const bool exposure = key.contains(QStringLiteral("exposure"), Qt::CaseInsensitive) ||
                            key.contains(QStringLiteral("Exposure"));
      if (unit) spin->setRange(0, 1);
      else if (gain) spin->setRange(0, 48);
      else if (exposure) spin->setRange(100, 10000000);
      else spin->setRange(0, 10000000);
      spin->setDecimals(gain || unit ? 2 : (exposure ? 0 : 2));
      spin->setSingleStep(unit ? 0.05 : (gain ? 0.5 : (exposure ? 100 : 1)));
      spin->setKeyboardTracking(false);
      spin->setValue(value.toDouble());
      connect(spin, QOverload<double>::of(&QDoubleSpinBox::valueChanged), this,
              [this, key](double v) { emitEdit(key, QString::number(v, 'g', 8)); });
      form_->addRow(lab, spin);
      break;
    }
    case 4: {
      auto* combo = new QComboBox;
      const QString cur = value.toString();
      int pick = 0;
      QStringList opts = spec.choices.split(QLatin1Char(';'), Qt::SkipEmptyParts);
      if (key == QLatin1String("subflowId")) {
        opts.clear();
        opts << QStringLiteral("|请选择子流程");
        for (const QString& pairTxt : subflowChoices_) opts << pairTxt;
      }
      for (int i = 0; i < opts.size(); ++i) {
        const QStringList pair = opts[i].split(QLatin1Char('|'));
        const QString val = pair.value(0);
        combo->addItem(pair.value(1, val), val);
        if (val == cur) pick = i;
      }
      if (key == QLatin1String("subflowId") && pick == 0 && !cur.isEmpty()) {
        combo->addItem(cur, cur);
        pick = combo->count() - 1;
      }
      combo->setCurrentIndex(pick);
      connect(combo, QOverload<int>::of(&QComboBox::currentIndexChanged), this,
              [this, key, combo](int) { emitEdit(key, combo->currentData().toString()); });
      form_->addRow(lab, combo);
      break;
    }
    case 0:
    default: {
      auto* edit = new QLineEdit(stringify(value));
      edit->setProperty("propKey", key);
      if (!tip.isEmpty()) edit->setToolTip(tip);
      connect(edit, &QLineEdit::editingFinished, this, [this, key, edit]() {
        emitEdit(key, edit->text());
      });
      form_->addRow(lab, edit);
      break;
    }
  }
}

void PropertyPanel::setSubflowChoices(const QStringList& idNamePairs) {
  subflowChoices_ = idNamePairs;
}

void PropertyPanel::addArgumentsTable(const QVariant& raw) {
  QVariantList rows;
  if (raw.typeId() == QMetaType::QVariantList) {
    rows = raw.toList();
  } else {
    const QVariantMap map = raw.toMap();
    for (auto it = map.begin(); it != map.end(); ++it) {
      QVariantMap row;
      row.insert(QStringLiteral("name"), it.key());
      row.insert(QStringLiteral("value"), it.value());
      rows.push_back(row);
    }
  }
  if (rows.isEmpty()) {
    QVariantMap row;
    row.insert(QStringLiteral("name"), QString());
    row.insert(QStringLiteral("value"), QString());
    rows.push_back(row);
  }
  auto* table = new QTableWidget(rows.size(), 2);
  table->setObjectName(QStringLiteral("subflowArgsTable"));
  table->setProperty("propKey", QStringLiteral("arguments"));
  table->setHorizontalHeaderLabels({QStringLiteral("参数名"), QStringLiteral("值 / 父变量")});
  table->horizontalHeader()->setStretchLastSection(true);
  table->verticalHeader()->setVisible(false);
  table->setMinimumHeight(110);
  auto emitArgs = [this, table]() {
    if (building_) return;
    QVariantMap out;
    for (int r = 0; r < table->rowCount(); ++r) {
      QTableWidgetItem* name = table->item(r, 0);
      QTableWidgetItem* val = table->item(r, 1);
      if (!name || name->text().trimmed().isEmpty()) continue;
      out.insert(name->text().trimmed(), val ? val->text() : QString());
    }
    emitEdit(QStringLiteral("arguments"),
             QString::fromUtf8(QJsonDocument::fromVariant(out).toJson(QJsonDocument::Compact)));
  };
  for (int i = 0; i < rows.size(); ++i) {
    const QVariantMap row = rows[i].toMap();
    table->setItem(i, 0, new QTableWidgetItem(row.value(QStringLiteral("name")).toString()));
    table->setItem(i, 1, new QTableWidgetItem(row.value(QStringLiteral("value")).toString()));
  }
  connect(table, &QTableWidget::itemChanged, this, [emitArgs](QTableWidgetItem*) { emitArgs(); });
  auto* box = new QWidget;
  auto* v = new QVBoxLayout(box);
  v->setContentsMargins(0, 0, 0, 0);
  v->setSpacing(4);
  v->addWidget(table);
  auto* btns = new QHBoxLayout;
  auto* add = new QPushButton(QStringLiteral("添加参数"));
  auto* del = new QPushButton(QStringLiteral("删除选中"));
  btns->addWidget(add);
  btns->addWidget(del);
  btns->addStretch();
  v->addLayout(btns);
  connect(add, &QPushButton::clicked, this, [table, emitArgs]() {
    const int r = table->rowCount();
    table->insertRow(r);
    table->setItem(r, 0, new QTableWidgetItem);
    table->setItem(r, 1, new QTableWidgetItem);
    emitArgs();
  });
  connect(del, &QPushButton::clicked, this, [table, emitArgs]() {
    const int r = table->currentRow();
    if (r >= 0) table->removeRow(r);
    emitArgs();
  });
  auto* lab = new QLabel(QStringLiteral("输入参数"));
  lab->setProperty("propKey", QStringLiteral("arguments"));
  lab->setProperty("propLabel", QStringLiteral("输入参数"));
  form_->addRow(lab, box);
}

void PropertyPanel::rebuildForm(const QString& title, const QString& nodeId,
                                const QString& op, const QVariantMap& params) {
  params_ = params;
  building_ = true;
  currentId_ = nodeId;
  title_->setText(title);
  while (form_->rowCount() > 0) form_->removeRow(0);

  if (op == QLatin1String("var_calc"))
    addExprTable(params.value(QStringLiteral("expressions")).toList());
  if (op == QLatin1String("condition"))
    addRulesTable(params.value(QStringLiteral("rules")).toList());
  if (op == QLatin1String("branch"))
    addPathsTable(params.value(QStringLiteral("paths")).toList());
  if (op == QLatin1String("condition") || op == QLatin1String("branch")) {
    auto* hint = new QLabel(
        op == QLatin1String("branch")
            ? QStringLiteral("画布出边 when 填路径名；无命中走默认路径。禁用路径不参与匹配。")
            : QStringLiteral("真分支 when=true，假分支 when=false。多规则按 AND/OR 合成。未选中的分支显示已跳过。"));
    hint->setWordWrap(true);
    hint->setObjectName(QStringLiteral("muted"));
    form_->addRow(hint);
  }
  if (op == QLatin1String("subflow") || op == QLatin1String("loop")) {
    addArgumentsTable(params.value(QStringLiteral("arguments")));
    auto* hint = new QLabel(
        op == QLatin1String("loop")
            ? QStringLiteral("循环 1–100 轮；until 模式要求输出节点的停止字段为布尔值，达上限仍未满足则失败。")
            : QStringLiteral("在「全流程 / 子流程管理」中定义可复用流程。参数名不可为 _iteration / _iterations。"));
    hint->setWordWrap(true);
    hint->setObjectName(QStringLiteral("muted"));
    form_->addRow(hint);
  }

  QStringList used;
  used << QStringLiteral("expressions") << QStringLiteral("rules")
       << QStringLiteral("paths") << QStringLiteral("arguments");
  for (const Spec& spec : specsFor(op)) {
    addSpecRow(spec, params);
    used << spec.key;
  }
  if (!op.startsWith(QLatin1String("source"))) {
    for (auto it = params.begin(); it != params.end(); ++it) {
      if (used.contains(it.key())) continue;
      Spec extra;
      extra.key = it.key();
      extra.label = it.key();
      extra.kind = 0;
      addSpecRow(extra, params);
    }
  }
  building_ = false;
  applyFilter();
}

void PropertyPanel::showSource(const QVariantMap& sourceConfig) {
  meta_->setText(QStringLiteral("图像源 · 本地图像 / 相机 / SDK，曝光增益热更新"));
  QVariantMap flat = sourceConfig;
  const QVariantMap cam = sourceConfig.value(QStringLiteral("cameraParams")).toMap();
  for (auto it = cam.begin(); it != cam.end(); ++it)
    flat.insert(QStringLiteral("cam.%1").arg(it.key()), it.value());
  QString kind = flat.value(QStringLiteral("cam.imageSource")).toString();
  if (kind.isEmpty()) {
    const QString mode = flat.value(QStringLiteral("mode")).toString();
    kind = (mode == QLatin1String("camera") || mode == QLatin1String("sdk")) ? mode
                                                                              : QStringLiteral("local");
    flat.insert(QStringLiteral("cam.imageSource"), kind);
  }
  if (!flat.contains(QStringLiteral("cam.pixelFormat")))
    flat.insert(QStringLiteral("cam.pixelFormat"), QStringLiteral("RGB24"));
  rebuildForm(QStringLiteral("属性 · 图像源"), QStringLiteral("source"),
              QStringLiteral("source:%1").arg(kind), flat);
}

void PropertyPanel::showStep(const FlowStep& step) {
  QString hint = QStringLiteral("算子 %1 · %2").arg(step.operation, step.runState);
  if (step.operation == QLatin1String("format_data"))
    hint += QStringLiteral(" · 支持 {name} / ${flow.x} / {{name}} · emptyDefault 空结果 · expr 见白名单");
  else if (step.operation == QLatin1String("send_data") ||
           step.operation == QLatin1String("receive_data"))
    hint += QStringLiteral(" · LocalLoop 回环 / TCP");
  else if (step.operation == QLatin1String("serial_exchange"))
    hint += QStringLiteral(" · 回环模拟 / 真实串口 / PTY 回环 · serialOk / serialRx");
  else if (step.operation == QLatin1String("modbus_read") ||
           step.operation == QLatin1String("modbus_write") ||
           step.operation == QLatin1String("modbus_wait"))
    hint += QStringLiteral(" · 模拟器 / TCP 软从站 / RTU PTY · 协议零地址 · values/value");
  else if (step.operation == QLatin1String("s7_read") ||
           step.operation == QLatin1String("s7_write"))
    hint += QStringLiteral(" · 模拟器 / ISO-on-TCP 软从站 · DB/M/I/Q 大端 · s7Read/s7Write");
  else if (step.operation == QLatin1String("opcua_read") ||
           step.operation == QLatin1String("opcua_write") ||
           step.operation == QLatin1String("opcua_browse") ||
           step.operation == QLatin1String("opcua_wait"))
    hint += QStringLiteral(" · 模拟器 / opc.tcp 软从站 Security=None · opcRead/opcWrite");
  else if (step.operation == QLatin1String("mqtt_publish") ||
           step.operation == QLatin1String("mqtt_receive"))
    hint += QStringLiteral(" · 模拟器 / MQTT 3.1.1 软代理 · mqttPub/mqttRecv");
  else if (step.operation == QLatin1String("result_gate"))
    hint += QStringLiteral(" · sourceVar → passVar");
  else if (step.operation == QLatin1String("var_calc"))
    hint += QStringLiteral(
        " · expr: in / startswith|endswith|contains / lower|upper / trim|strip|replace / slice|substr|mid|isdigit|isalpha|lpad|rpad|repeat|default|coalesce|nvl|ifempty|indexof|find|left|right|isempty|notempty|zfill|count|clamp|round|floor|ceil|sign|pow|sqrt|trunc|title|capitalize|hypot|log|exp|isalnum|swapcase|radians|degrees|ord|chr|bin|hex|islower|isupper|nvl|lstrip|rstrip|iff|bool|oct|fabs|fmod|cbrt|log10|frac|log2|isfinite|atan2|copysign|bitand|bitor|bitxor|gcd|lcm|clamp01|lerp|invlerp|smoothstep|step|saturate|fract|isnan|isinf|mix|exp2|fma|sin|cos|tan|asin|acos|atan|sinh|cosh|tanh|log1p|expm1|fdim|nearbyint|bitshl|bitshr|remainder|scalbn|nextafter|tgamma|lgamma|erf|erfc|asinh|acosh|atanh|rint|logb|ilogb|signbit|isnormal|fmax|fmin|bitnot|between|approxeq|inrange|nan|inf|reverse|join|cmp|eq|ne|gt|lt|ge|le|choose|nth|ifelse|nullif|iif|not_|and_|or_|xor_|truthy|falsy|ifnull|nonempty|strlen|tostring|toint|todouble|tonumber");
  else if (step.operation == QLatin1String("barcode") ||
           step.operation == QLatin1String("qr_decode"))
    hint += QStringLiteral(" · ZXing 多码 · 判定 judgeMinCount");
  else if (step.operation == QLatin1String("ocr"))
    hint += QStringLiteral(" · Tesseract · lang/psm · ocrText");
  else if (step.operation == QLatin1String("geometry"))
    hint += QStringLiteral(" · 直线/圆/矩形/轮廓/边缘 · geomCount/X/Y/Radius/Length");
  else if (step.operation == QLatin1String("measure"))
    hint += QStringLiteral(" · 直径/线长/两点距/夹角/轮廓 · 等比例标定 pxPerMm");
  else if (step.operation == QLatin1String("caliper"))
    hint += QStringLiteral(" · QImage 边缘卡尺 · caliperDist/measureMm");
  else if (step.operation == QLatin1String("defects"))
    hint += QStringLiteral(" · 灰度差影+连通域 · defectsCount/defectsRatio/defectsOk · 可跟随定位");
  else if (step.operation == QLatin1String("yolo"))
    hint += QStringLiteral(" · YOLO 检测 · yoloCount/yoloScore/yoloLabel · backend=software");
  else if (step.operation == QLatin1String("yolo_segment"))
    hint += QStringLiteral(" · YOLO 分割 · yoloSegCount/yoloSegArea/yoloSegScore · 轮廓/孔洞");
  else if (step.operation == QLatin1String("locate"))
    hint += QStringLiteral(" · 模板 SAD + 旋转搜索 · locateX/Y/Angle/Score");
  else if (step.operation == QLatin1String("pose_correct"))
    hint += QStringLiteral(" · 定位跟随 · fixtureX/Y/Angle 供下游 ROI/测量");
  else if (step.operation == QLatin1String("subflow"))
    hint += QStringLiteral(" · 调用子流程 · 结果 subflowPassed/subflowCount");
  else if (step.operation == QLatin1String("loop"))
    hint += QStringLiteral(" · 循环子流程 · loopCount/loopStoppedEarly · 最多 100 轮");
  meta_->setText(hint);
  rebuildForm(QStringLiteral("属性 · %1").arg(step.name), step.id, step.operation,
              step.params);
}


void PropertyPanel::applySnapshot(const QVariantMap& snap) {
  if (!form_) return;
  building_ = true;
  params_ = snap;
  for (int r = 0; r < form_->rowCount(); ++r) {
    QLayoutItem* labItem = form_->itemAt(r, QFormLayout::LabelRole);
    QLayoutItem* fieldItem = form_->itemAt(r, QFormLayout::FieldRole);
    if (!labItem || !fieldItem) continue;
    QWidget* labW = labItem->widget();
    QWidget* field = fieldItem->widget();
    if (!labW || !field) continue;
    const QString key = labW->property("propKey").toString();
    if (key.isEmpty() || !snap.contains(key)) continue;
    const QVariant v = snap.value(key);
    if (auto* le = qobject_cast<QLineEdit*>(field)) {
      le->setText(stringify(v));
    } else if (auto* sp = qobject_cast<QSpinBox*>(field)) {
      sp->setValue(v.toInt());
    } else if (auto* dsp = qobject_cast<QDoubleSpinBox*>(field)) {
      dsp->setValue(v.toDouble());
    } else if (auto* box = qobject_cast<QCheckBox*>(field)) {
      const QString s = stringify(v);
      box->setChecked(v.toBool() || s == QLatin1String("true") || s == QLatin1String("1"));
    } else if (auto* combo = qobject_cast<QComboBox*>(field)) {
      const int idx = combo->findData(v.toString());
      if (idx >= 0) combo->setCurrentIndex(idx);
    }
  }
  building_ = false;
  for (auto it = snap.begin(); it != snap.end(); ++it)
    emitEdit(it.key(), stringify(it.value()));
}

void PropertyPanel::focusFilter() {
  if (!filterEdit_) return;
  filterEdit_->setFocus(Qt::ShortcutFocusReason);
  filterEdit_->selectAll();
}

void PropertyPanel::applyFilter() {
  if (!form_ || !filterEdit_) return;
  const QString f = filterEdit_->text().trimmed();
  for (int r = 0; r < form_->rowCount(); ++r) {
    QString hay;
    if (auto* li = form_->itemAt(r, QFormLayout::LabelRole)) {
      if (auto* w = li->widget()) {
        hay += w->property("propKey").toString() + QLatin1Char(' ');
        hay += w->property("propLabel").toString() + QLatin1Char(' ');
        if (auto* lab = qobject_cast<QLabel*>(w)) hay += lab->text() + QLatin1Char(' ');
        else hay += w->objectName() + QLatin1Char(' ');
      }
    }
    if (auto* fi = form_->itemAt(r, QFormLayout::FieldRole)) {
      if (auto* w = fi->widget()) {
        hay += w->property("propKey").toString() + QLatin1Char(' ');
        if (qobject_cast<QTableWidget*>(w)) hay += QStringLiteral("expressions expr 表达式 ");
      }
    }
    // spanning full-row widgets (expr table)
    if (auto* si = form_->itemAt(r, QFormLayout::SpanningRole)) {
      if (auto* w = si->widget()) {
        hay += w->property("propKey").toString() + QStringLiteral(" expressions expr 表达式 ");
      }
    }
    const bool show = f.isEmpty() || hay.contains(f, Qt::CaseInsensitive);
    form_->setRowVisible(r, show);
  }
  if (meta_ && !f.isEmpty()) {
    int vis = 0;
    for (int r = 0; r < form_->rowCount(); ++r) {
      // setRowVisible doesn't expose getter easily — count via label visibility
      if (auto* li = form_->itemAt(r, QFormLayout::LabelRole)) {
        if (li->widget() && li->widget()->isVisibleTo(formHost_)) ++vis;
      } else if (auto* si = form_->itemAt(r, QFormLayout::SpanningRole)) {
        if (si->widget() && si->widget()->isVisibleTo(formHost_)) ++vis;
      }
    }
    Q_UNUSED(vis);
  }
  filterEdit_->setToolTip(
      QStringLiteral("属性过滤 · %1 · Ctrl+F 聚焦 · Esc 清空")
          .arg(f.isEmpty() ? QStringLiteral("全部") : QStringLiteral("「%1」").arg(f)));
}


void PropertyPanel::copyVisibleParams() {
  if (!form_) return;
  QStringList lines;
  for (int r = 0; r < form_->rowCount(); ++r) {
    QWidget* labW = nullptr;
    QWidget* fieldW = nullptr;
    if (auto* li = form_->itemAt(r, QFormLayout::LabelRole)) labW = li->widget();
    if (auto* fi = form_->itemAt(r, QFormLayout::FieldRole)) fieldW = fi->widget();
    if (labW && !labW->isVisibleTo(formHost_)) continue;
    QString key = labW ? labW->property("propKey").toString() : QString();
    if (key.isEmpty() && fieldW) key = fieldW->property("propKey").toString();
    if (key.isEmpty()) continue;
    QString val;
    if (auto* le = qobject_cast<QLineEdit*>(fieldW)) {
      val = le->text();
    } else if (auto* sp = qobject_cast<QSpinBox*>(fieldW)) {
      val = QString::number(sp->value());
    } else if (auto* dsp = qobject_cast<QDoubleSpinBox*>(fieldW)) {
      val = QString::number(dsp->value());
    } else if (auto* box = qobject_cast<QCheckBox*>(fieldW)) {
      val = box->isChecked() ? QStringLiteral("true") : QStringLiteral("false");
    } else if (auto* combo = qobject_cast<QComboBox*>(fieldW)) {
      val = combo->currentData().toString();
      if (val.isEmpty()) val = combo->currentText();
    } else if (fieldW) {
      val = fieldW->property("text").toString();
    }
    lines << QStringLiteral("%1=%2").arg(key, val);
  }
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(lines.join(QLatin1Char('\n')));
  if (filterEdit_)
    filterEdit_->setToolTip(QStringLiteral("已复制可见参数 %1 · Ctrl+Shift+C").arg(lines.size()));
}


void PropertyPanel::pasteKeyValueParams() {
  const QString clip = QGuiApplication::clipboard() ? QGuiApplication::clipboard()->text() : QString();
  if (clip.trimmed().isEmpty() || !form_) return;
  int n = 0;
  for (const QString& line : clip.split(QLatin1Char('\n'))) {
    const int eq = line.indexOf(QLatin1Char('='));
    if (eq <= 0) continue;
    const QString key = line.left(eq).trimmed();
    const QString val = line.mid(eq + 1).trimmed();
    if (key.isEmpty()) continue;
    for (int r = 0; r < form_->rowCount(); ++r) {
      QWidget* fieldW = nullptr;
      if (auto* fi = form_->itemAt(r, QFormLayout::FieldRole)) fieldW = fi->widget();
      if (!fieldW) continue;
      if (fieldW->property("propKey").toString() != key) continue;
      if (auto* le = qobject_cast<QLineEdit*>(fieldW)) {
        le->setText(val);
        ++n;
      } else if (auto* sp = qobject_cast<QSpinBox*>(fieldW)) {
        bool ok = false;
        const int iv = val.toInt(&ok);
        if (ok) { sp->setValue(iv); ++n; }
      } else if (auto* dsp = qobject_cast<QDoubleSpinBox*>(fieldW)) {
        bool ok = false;
        const double dv = val.toDouble(&ok);
        if (ok) { dsp->setValue(dv); ++n; }
      } else if (auto* box = qobject_cast<QCheckBox*>(fieldW)) {
        box->setChecked(val == QLatin1String("true") || val == QLatin1String("1"));
        ++n;
      } else if (auto* combo = qobject_cast<QComboBox*>(fieldW)) {
        int cidx = combo->findData(val);
        if (cidx < 0) cidx = combo->findText(val);
        if (cidx >= 0) { combo->setCurrentIndex(cidx); ++n; }
      }
      break;
    }
  }
  if (filterEdit_)
    filterEdit_->setToolTip(QStringLiteral("已粘贴参数 %1 · Ctrl+Shift+V").arg(n));
}


void PropertyPanel::exportParamsJson() {
  QJsonObject o = QJsonObject::fromVariantMap(params_);
  if (!currentId_.isEmpty()) o.insert(QStringLiteral("_nodeId"), currentId_);
  const QByteArray bytes = QJsonDocument(o).toJson(QJsonDocument::Compact);
  if (auto* clip = QGuiApplication::clipboard()) clip->setText(QString::fromUtf8(bytes));
  if (filterEdit_)
    filterEdit_->setToolTip(QStringLiteral("已导出参数JSON %1 · Ctrl+Shift+J").arg(params_.size()));
}

void PropertyPanel::importParamsJson() {
  const QString clip = QGuiApplication::clipboard() ? QGuiApplication::clipboard()->text() : QString();
  if (clip.trimmed().isEmpty() || !form_) return;
  QJsonParseError pe;
  const QJsonDocument doc = QJsonDocument::fromJson(clip.toUtf8(), &pe);
  if (pe.error != QJsonParseError::NoError || !doc.isObject()) {
    if (filterEdit_)
      filterEdit_->setToolTip(QStringLiteral("JSON 无效 · Ctrl+Shift+O"));
    return;
  }
  const QVariantMap m = doc.object().toVariantMap();
  int n = 0;
  for (auto it = m.begin(); it != m.end(); ++it) {
    if (it.key().startsWith(QLatin1Char('_'))) continue;
    const QString key = it.key();
    const QString val = it.value().toString();
    for (int r = 0; r < form_->rowCount(); ++r) {
      QWidget* fieldW = nullptr;
      if (auto* fi = form_->itemAt(r, QFormLayout::FieldRole)) fieldW = fi->widget();
      if (!fieldW) continue;
      if (fieldW->property("propKey").toString() != key) continue;
      if (auto* le = qobject_cast<QLineEdit*>(fieldW)) {
        le->setText(val); ++n;
      } else if (auto* sp = qobject_cast<QSpinBox*>(fieldW)) {
        bool ok = false; const int iv = val.toInt(&ok);
        if (ok) { sp->setValue(iv); ++n; }
      } else if (auto* dsp = qobject_cast<QDoubleSpinBox*>(fieldW)) {
        bool ok = false; const double dv = val.toDouble(&ok);
        if (ok) { dsp->setValue(dv); ++n; }
      } else if (auto* box = qobject_cast<QCheckBox*>(fieldW)) {
        box->setChecked(val == QLatin1String("true") || val == QLatin1String("1") ||
                        it.value().toBool());
        ++n;
      } else if (auto* combo = qobject_cast<QComboBox*>(fieldW)) {
        int cidx = combo->findData(val);
        if (cidx < 0) cidx = combo->findText(val);
        if (cidx >= 0) { combo->setCurrentIndex(cidx); ++n; }
      }
      break;
    }
  }
  if (filterEdit_)
    filterEdit_->setToolTip(QStringLiteral("已导入参数JSON %1 · Ctrl+Shift+O").arg(n));
}


void PropertyPanel::flushPendingEdits() {
  if (!form_) return;
  // Clear focus so editingFinished fires on the active QLineEdit first.
  if (QWidget* fw = QApplication::focusWidget()) {
    if (isAncestorOf(fw)) fw->clearFocus();
  }
  for (int r = 0; r < form_->rowCount(); ++r) {
    QWidget* labW = nullptr;
    QWidget* fieldW = nullptr;
    if (auto* li = form_->itemAt(r, QFormLayout::LabelRole)) labW = li->widget();
    if (auto* fi = form_->itemAt(r, QFormLayout::FieldRole)) fieldW = fi->widget();
    QString key = labW ? labW->property("propKey").toString() : QString();
    if (key.isEmpty() && fieldW) key = fieldW->property("propKey").toString();
    if (key.isEmpty()) continue;
    if (auto* le = qobject_cast<QLineEdit*>(fieldW)) {
      if (params_.value(key).toString() != le->text()) emitEdit(key, le->text());
    }
  }
}

}  // namespace sieans_qt
