#pragma once

#include <QString>
#include <QStringList>
#include <QVector>
#include <QColor>

namespace sieans_qt {

/** One geom/measure feature collected from a cached film-frame result. */
struct GeomPickable {
  QString kind;  // line | point
  QString field;
  QString label;
  qreal x = 0;
  qreal y = 0;
  qreal x1 = 0;
  qreal y1 = 0;
  qreal x2 = 0;
  qreal y2 = 0;
};

/** One colored overlay primitive for multi-frame compare (PySide set_geom_overlays). */
struct GeomOverlaySpec {
  QString type;  // line | point | label
  QString color;
  qreal width = 1.5;
  qreal x = 0;
  qreal y = 0;
  qreal x1 = 0;
  qreal y1 = 0;
  qreal x2 = 0;
  qreal y2 = 0;
  qreal r = 6;
  QString text;
  QString frame;
  QString framePath;
};

/** Color-cycled overlay specs; highlight_path uses the accent color and width. */
QVector<GeomOverlaySpec> overlaySpecsForMultiframe(
    const QVector<QPair<QString, QVector<GeomPickable>>>& frames,
    const QString& highlightPath = QString());

/** Isolated pickable/spec/highlight/ImageView checks. Empty list = pass. Needs QApplication. */
QStringList geomOverlaySelfTest();

}  // namespace sieans_qt
