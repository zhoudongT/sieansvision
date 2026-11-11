#pragma once

#include <QString>
#include <QStringList>

namespace sieans_qt {

/**
 * 定位本仓库根目录（同时具备 qtapp/scripts/build.sh 与 scripts/launch-sieans-qt.sh）。
 * 查找顺序：SIEANS_REPO、可执行文件向上、当前工作目录向上，最后才尝试本机历史路径。
 * 找不到时返回空串，不编造目录。
 */
QString workbenchRepoRoot();

/** 方案目录：仓库 projects/（必要时创建）。仓库未知时回退到 $HOME/sieansvision-projects。 */
QString workbenchProjectsDir();

/** 运行产物目录：仓库 artifacts/（必要时创建）。 */
QString workbenchArtifactsDir();

/** 用户数据目录：$HOME/.local/share/sieans（必要时创建）。不写方案文件。 */
QString workbenchUserDataDir();

/** 快速匹配模板落盘目录：artifacts/qt-templates（必要时创建）。 */
QString workbenchTemplatesDir();

/**
 * 若请求路径为空，或仍是历史写死的 /home/allen/文档/sieansvision/artifacts，
 * 则改到当前检出的产物目录，便于换机器后仍能保存。
 */
QString workbenchResolveArtifactsDir(const QString& requested);

/** 示例 QR 图的候选路径（已存在的排在前面，调用方可再检查可读）。 */
QStringList workbenchSampleQrCandidates();

/** 第一个存在的示例 QR 路径；都没有则空串。 */
QString workbenchFirstExistingSampleQr();

/**
 * 自动冒烟 / offscreen / 自检时为 true，禁止弹出「未保存」等模态框，以免卡住无界面进程。
 */
bool workbenchIsHeadless();

/** 路径解析与方案文件往返的自检。空列表表示通过。不要求 QApplication。 */
QStringList workbenchPathsSelfTest();

}  // namespace sieans_qt
