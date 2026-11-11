#include "GeomOverlay.hpp"
#include "ImageView.hpp"

#include <QFileInfo>
#include <QImage>
#include <QSet>
#include <QApplication>
#include <cmath>

namespace sieans_qt {
namespace {

const char* kColors[] = {"#e87722", "#6eb6ff", "#3ecf8e",
                         "#c9a0ff", "#e35d6a", "#f0c674"};
constexpr int kColorN = 6;

bool isGeomMeasureFormat(const QString& f) {
  return f == QLatin1String("GEOM") || f == QLatin1String("MEASURE") ||
         f == QLatin1String("CALIPER");
}

bool samePoint(const QPointF& a, const QPointF& b) {
  return std::hypot(a.x() - b.x(), a.y() - b.y()) < 0.51;
}

}  // namespace

QVector<GeomPickable> pickablesFromOverlayHits(const QVector<OverlayHit>& hits) {
  QVector<GeomPickable> out;
  int idx = 0;
  for (const OverlayHit& h : hits) {
    if (!isGeomMeasureFormat(h.format)) continue;
    ++idx;
    GeomPickable p;
    p.field = h.format;
    p.label = h.text.isEmpty() ? h.format : h.text;
    QVector<QPointF> uniq;
    for (const QPointF& pt : h.polygon) {
      bool seen = false;
      for (const QPointF& u : uniq) {
        if (samePoint(u, pt)) {
          seen = true;
          break;
        }
      }
      if (!seen) uniq.push_back(pt);
    }
    if (uniq.size() == 2) {
      p.kind = QStringLiteral("line");
      p.x1 = uniq[0].x();
      p.y1 = uniq[0].y();
      p.x2 = uniq[1].x();
      p.y2 = uniq[1].y();
    } else if (!h.polygon.isEmpty()) {
      p.kind = QStringLiteral("point");
      QPointF c(0, 0);
      for (const QPointF& pt : h.polygon) c += pt;
      c /= qreal(h.polygon.size());
      p.x = c.x();
      p.y = c.y();
    } else {
      continue;
    }
    out.push_back(p);
  }
  return out;
}

QVector<GeomOverlaySpec> overlaySpecsForMultiframe(
    const QVector<QPair<QString, QVector<GeomPickable>>>& frames,
    const QString& highlightPath) {
  QVector<GeomOverlaySpec> out;
  const QString hi = highlightPath.trimmed();
  for (int i = 0; i < frames.size(); ++i) {
    const QString path = frames.at(i).first;
    const QString leaf = path.isEmpty() ? QStringLiteral("#%1").arg(i)
                                        : QFileInfo(path).fileName();
    const bool isHi = !hi.isEmpty() && path == hi;
    const bool accent = isHi || (hi.isEmpty() && i == 0);
    const QString color = QString::fromLatin1(kColors[accent ? 0 : ((i % (kColorN - 1)) + 1)]);
    const qreal width = (accent) ? 2.5 : 1.5;
    for (const GeomPickable& pk : frames.at(i).second) {
      auto tag = [&](const QString& lab) {
        if (leaf.isEmpty()) return lab;
        if (lab.contains(leaf)) return lab;
        return lab.isEmpty() ? leaf : (lab + QStringLiteral(" · ") + leaf);
      };
      if (pk.kind == QLatin1String("line")) {
        GeomOverlaySpec line;
        line.type = QStringLiteral("line");
        line.color = color;
        line.width = width;
        line.x1 = pk.x1;
        line.y1 = pk.y1;
        line.x2 = pk.x2;
        line.y2 = pk.y2;
        line.frame = leaf;
        line.framePath = path;
        out.push_back(line);
        GeomOverlaySpec lab;
        lab.type = QStringLiteral("label");
        lab.color = color;
        lab.width = width;
        lab.x = (pk.x1 + pk.x2) / 2.0 + 4.0;
        lab.y = (pk.y1 + pk.y2) / 2.0 - 4.0;
        lab.text = tag(pk.label.isEmpty() ? pk.field : pk.label);
        lab.frame = leaf;
        lab.framePath = path;
        out.push_back(lab);
      } else {
        GeomOverlaySpec pt;
        pt.type = QStringLiteral("point");
        pt.color = color;
        pt.width = width;
        pt.x = pk.x;
        pt.y = pk.y;
        pt.r = 6;
        pt.frame = leaf;
        pt.framePath = path;
        out.push_back(pt);
        GeomOverlaySpec lab;
        lab.type = QStringLiteral("label");
        lab.color = color;
        lab.width = width;
        lab.x = pk.x + 6.0;
        lab.y = pk.y - 8.0;
        lab.text = tag(pk.label.isEmpty() ? pk.field : pk.label);
        lab.frame = leaf;
        lab.framePath = path;
        out.push_back(lab);
      }
    }
  }
  return out;
}

QStringList geomOverlaySelfTest() {
  QStringList fails;
  auto check = [&](const char* name, bool ok, const QString& detail = QString()) {
    if (!ok)
      fails << (detail.isEmpty() ? QString::fromUtf8(name)
                                 : QStringLiteral("%1: %2").arg(QString::fromUtf8(name), detail));
  };

  const QString pa = QStringLiteral("/tmp/frame-a.png");
  const QString pb = QStringLiteral("/tmp/frame-b.png");
  GeomPickable la;
  la.kind = QStringLiteral("line");
  la.field = QStringLiteral("lines[0]");
  la.label = QStringLiteral("找线 · lines[0]");
  la.x1 = 10;
  la.y1 = 10;
  la.x2 = 80;
  la.y2 = 10;
  GeomPickable pbpt;
  pbpt.kind = QStringLiteral("point");
  pbpt.field = QStringLiteral("circles[0]");
  pbpt.label = QStringLiteral("圆");
  pbpt.x = 40;
  pbpt.y = 50;

  QVector<QPair<QString, QVector<GeomPickable>>> frames;
  frames.push_back({pa, {la}});
  frames.push_back({pb, {pbpt}});
  const QVector<GeomOverlaySpec> specs = overlaySpecsForMultiframe(frames, pb);
  check("spec-count", specs.size() == 4, QString::number(specs.size()));
  int hiLine = 0, hiPoint = 0, mutedLine = 0;
  for (const GeomOverlaySpec& s : specs) {
    if (s.framePath == pb && s.color == QLatin1String("#e87722") && s.width == 2.5)
      ++hiPoint;
    if (s.framePath == pa && s.color != QLatin1String("#e87722") && s.width == 1.5)
      ++mutedLine;
    if (s.type == QLatin1String("label") && s.framePath == pb)
      check("label-leaf", s.text.contains(QStringLiteral("frame-b.png")), s.text);
  }
  check("highlight-accent", hiPoint >= 2, QString::number(hiPoint));
  check("muted-other", mutedLine >= 2, QString::number(mutedLine));

  OverlayHit line;
  line.format = QStringLiteral("CALIPER");
  line.text = QStringLiteral("L=12");
  line.polygon << QPointF(1, 2) << QPointF(9, 2) << QPointF(9, 2) << QPointF(1, 2);
  OverlayHit box;
  box.format = QStringLiteral("GEOM");
  box.text = QStringLiteral("r=5");
  box.polygon << QPointF(0, 0) << QPointF(10, 0) << QPointF(10, 10) << QPointF(0, 10);
  OverlayHit skip;
  skip.format = QStringLiteral("OCR");
  skip.polygon << QPointF(0, 0) << QPointF(1, 0) << QPointF(1, 1) << QPointF(0, 1);
  const QVector<GeomPickable> pks = pickablesFromOverlayHits({line, box, skip});
  check("hits-count", pks.size() == 2, QString::number(pks.size()));
  check("hits-line", !pks.isEmpty() && pks.first().kind == QLatin1String("line") &&
                         pks.first().x1 == 1 && pks.first().x2 == 9);
  check("hits-point", pks.size() == 2 && pks.at(1).kind == QLatin1String("point"));

  if (!qApp) {
    fails << QStringLiteral("no-qapp");
    return fails;
  }
  ImageView view;
  QImage img(120, 80, QImage::Format_RGB888);
  img.fill(QColor(20, 24, 28));
  view.setImage(img, false);
  view.setGeomOverlays(specs);
  check("view-count", view.geomOverlayCount() == specs.size(),
        QString::number(view.geomOverlayCount()));
  view.setGeomOverlays({});
  check("view-cleared", view.geomOverlayCount() == 0,
        QString::number(view.geomOverlayCount()));
  return fails;
}

}  // namespace sieans_qt
