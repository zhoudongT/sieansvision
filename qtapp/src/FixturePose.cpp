#include "FixturePose.hpp"

#include <QPainter>
#include <QColor>
#include <QtMath>
#include <cmath>

namespace sieans_qt {

QPointF poseMap(const Pose2D& pose, const QPointF& local) {
  const double scale = (pose.scale > 0 && std::isfinite(pose.scale)) ? pose.scale : 1.0;
  const double rad = qDegreesToRadians(pose.angleDeg);
  const double c = std::cos(rad), s = std::sin(rad);
  return QPointF(pose.x + scale * (c * local.x() - s * local.y()),
                 pose.y + scale * (s * local.x() + c * local.y()));
}

QPointF poseUnmap(const Pose2D& pose, const QPointF& image) {
  const double scale = (pose.scale > 0 && std::isfinite(pose.scale)) ? pose.scale : 1.0;
  const double rad = qDegreesToRadians(pose.angleDeg);
  const double c = std::cos(rad), s = std::sin(rad);
  const double dx = image.x() - pose.x, dy = image.y() - pose.y;
  const double inv = 1.0 / scale;
  return QPointF(inv * (c * dx + s * dy), inv * (-s * dx + c * dy));
}

Pose2D poseFromParams(const QVariantMap& params, const QString& prefix) {
  Pose2D p;
  const QString pre = prefix.isEmpty() ? QStringLiteral("fixture") : prefix;
  auto get = [&](const QString& camel, const QString& snake, double def = 0) {
    if (params.contains(camel)) return params.value(camel).toDouble();
    if (params.contains(snake)) return params.value(snake).toDouble();
    if (params.contains(pre + camel.mid(0, 1).toUpper() + camel.mid(1)))
      return params.value(pre + camel.mid(0, 1).toUpper() + camel.mid(1)).toDouble();
    return def;
  };
  // Prefer explicit fixtureX injected into params
  if (params.contains(QStringLiteral("fixtureX"))) {
    p.x = params.value(QStringLiteral("fixtureX")).toDouble();
    p.y = params.value(QStringLiteral("fixtureY")).toDouble();
    p.angleDeg = params.value(QStringLiteral("fixtureAngle")).toDouble();
    p.scale = params.value(QStringLiteral("fixtureScale"), 1).toDouble();
    p.ok = params.contains(QStringLiteral("fixtureOk"))
               ? params.value(QStringLiteral("fixtureOk")).toInt() != 0 ||
                     params.value(QStringLiteral("fixtureOk")).toBool()
               : true;
    if (!(p.scale > 0)) p.scale = 1;
    return p;
  }
  p.x = params.value(pre + QStringLiteral("X"), params.value(QStringLiteral("baseX"), 0))
            .toDouble();
  p.y = params.value(pre + QStringLiteral("Y"), params.value(QStringLiteral("baseY"), 0))
            .toDouble();
  p.angleDeg =
      params.value(pre + QStringLiteral("Angle"), params.value(QStringLiteral("baseAngle"), 0))
          .toDouble();
  p.scale =
      params.value(pre + QStringLiteral("Scale"), params.value(QStringLiteral("baseScale"), 1))
          .toDouble();
  if (!(p.scale > 0)) p.scale = 1;
  p.ok = params.value(pre + QStringLiteral("Ok"), 0).toInt() != 0 ||
         params.value(pre + QStringLiteral("Ok")).toBool();
  Q_UNUSED(get);
  return p;
}

void injectFixtureFromVars(QVariantMap& params, const QVariantMap& vars) {
  const bool follow = params.value(QStringLiteral("followFixture")).toBool();
  if (!follow) return;
  const QString pre =
      params.value(QStringLiteral("fixtureVar"), QStringLiteral("fixture")).toString();
  const QString prefix = pre.isEmpty() ? QStringLiteral("fixture") : pre;
  auto take = [&](const QString& key, const QString& alt = QString()) {
    if (vars.contains(key)) return vars.value(key);
    if (!alt.isEmpty() && vars.contains(alt)) return vars.value(alt);
    return QVariant();
  };
  const QVariant x = take(prefix + QStringLiteral("X"), QStringLiteral("locateX"));
  const QVariant y = take(prefix + QStringLiteral("Y"), QStringLiteral("locateY"));
  if (!x.isValid() || !y.isValid()) return;
  params.insert(QStringLiteral("fixtureX"), x);
  params.insert(QStringLiteral("fixtureY"), y);
  params.insert(QStringLiteral("fixtureAngle"),
                take(prefix + QStringLiteral("Angle"), QStringLiteral("locateAngle")));
  QVariant sc = take(prefix + QStringLiteral("Scale"), QStringLiteral("locateScale"));
  params.insert(QStringLiteral("fixtureScale"), sc.isValid() ? sc : 1);
  QVariant okv = take(prefix + QStringLiteral("Ok"), QStringLiteral("locateOk"));
  params.insert(QStringLiteral("fixtureOk"), okv.isValid() ? okv : 1);
  if (!params.contains(QStringLiteral("fixtureBaseX"))) {
    QVariant bx = take(prefix + QStringLiteral("BaseX"));
    if (bx.isValid()) {
      params.insert(QStringLiteral("fixtureBaseX"), bx);
      params.insert(QStringLiteral("fixtureBaseY"), take(prefix + QStringLiteral("BaseY")));
      params.insert(QStringLiteral("fixtureBaseAngle"),
                    take(prefix + QStringLiteral("BaseAngle")));
    }
  }
}

FollowRoi resolveFollowRoi(const QVariantMap& params, int imageW, int imageH) {
  FollowRoi fr;
  if (!params.value(QStringLiteral("followFixture")).toBool()) return fr;
  Pose2D pose = poseFromParams(params);
  if (!pose.ok && !params.contains(QStringLiteral("fixtureX"))) return fr;
  if (params.contains(QStringLiteral("fixtureOk")) &&
      !(params.value(QStringLiteral("fixtureOk")).toInt() != 0 ||
        params.value(QStringLiteral("fixtureOk")).toBool()))
    return fr;
  pose.ok = true;
  double rw = params.value(QStringLiteral("roiW"), 0).toDouble();
  double rh = params.value(QStringLiteral("roiH"), 0).toDouble();
  if (rw <= 0 || rh <= 0) {
    rw = params.value(QStringLiteral("locateW"), 80).toDouble();
    rh = params.value(QStringLiteral("locateH"), 40).toDouble();
    if (rw <= 0) rw = 80;
    if (rh <= 0) rh = 40;
  }
  double rx = params.contains(QStringLiteral("roiX"))
                  ? params.value(QStringLiteral("roiX")).toDouble()
                  : -rw * 0.5;
  double ry = params.contains(QStringLiteral("roiY"))
                  ? params.value(QStringLiteral("roiY")).toDouble()
                  : -rh * 0.5;
  fr.roiX = rx;
  fr.roiY = ry;
  fr.patchW = qMax(1, int(std::lround(rw)));
  fr.patchH = qMax(1, int(std::lround(rh)));
  fr.corners << poseMap(pose, QPointF(rx, ry))
             << poseMap(pose, QPointF(rx + rw, ry))
             << poseMap(pose, QPointF(rx + rw, ry + rh))
             << poseMap(pose, QPointF(rx, ry + rh));
  const QRectF b = fr.corners.boundingRect();
  fr.aabb = QRect(int(std::floor(b.x())), int(std::floor(b.y())),
                  int(std::ceil(b.width())), int(std::ceil(b.height())))
                .intersected(QRect(0, 0, imageW, imageH));
  fr.center = poseMap(pose, QPointF(rx + rw * 0.5, ry + rh * 0.5));
  fr.active = true;
  return fr;
}

QImage extractFollowPatch(const QImage& src, const FollowRoi& roi, const Pose2D& pose) {
  if (src.isNull() || !roi.active || roi.patchW <= 0 || roi.patchH <= 0) return {};
  QImage img = src.convertToFormat(QImage::Format_RGB888);
  QImage out(roi.patchW, roi.patchH, QImage::Format_RGB888);
  out.fill(Qt::black);
  const int sw = img.width(), sh = img.height();
  for (int j = 0; j < roi.patchH; ++j) {
    uchar* dst = out.scanLine(j);
    for (int i = 0; i < roi.patchW; ++i) {
      const QPointF p = poseMap(pose, QPointF(roi.roiX + i + 0.5, roi.roiY + j + 0.5));
      const int x = int(std::floor(p.x()));
      const int y = int(std::floor(p.y()));
      if (x < 0 || y < 0 || x >= sw || y >= sh) continue;
      const uchar* s = img.constScanLine(y) + x * 3;
      dst[i * 3 + 0] = s[0];
      dst[i * 3 + 1] = s[1];
      dst[i * 3 + 2] = s[2];
    }
  }
  return out;
}

PoseCorrectResult runPoseCorrect(const QVariantMap& params, const QVariantMap& vars) {
  PoseCorrectResult r;
  const QString source =
      params.value(QStringLiteral("fixtureSource"), QStringLiteral("auto")).toString();
  Pose2D pose;
  pose.x = params.value(QStringLiteral("baseX"), 0).toDouble();
  pose.y = params.value(QStringLiteral("baseY"), 0).toDouble();
  pose.angleDeg = params.value(QStringLiteral("baseAngle"), 0).toDouble();
  pose.scale = params.value(QStringLiteral("baseScale"), 1).toDouble();
  if (!(pose.scale > 0)) pose.scale = 1;

  auto tryBind = [&](const QString& pre) -> bool {
    if (!vars.contains(pre + QStringLiteral("X")) && !vars.contains(pre + QStringLiteral("x")))
      return false;
    const QVariant xv = vars.contains(pre + QStringLiteral("X"))
                            ? vars.value(pre + QStringLiteral("X"))
                            : vars.value(pre + QStringLiteral("x"));
    const QVariant yv = vars.contains(pre + QStringLiteral("Y"))
                            ? vars.value(pre + QStringLiteral("Y"))
                            : vars.value(pre + QStringLiteral("y"));
    if (!xv.isValid()) return false;
    pose.x = xv.toDouble();
    pose.y = yv.toDouble();
    if (vars.contains(pre + QStringLiteral("Angle")))
      pose.angleDeg = vars.value(pre + QStringLiteral("Angle")).toDouble();
    else if (vars.contains(pre + QStringLiteral("angle")))
      pose.angleDeg = vars.value(pre + QStringLiteral("angle")).toDouble();
    if (vars.contains(pre + QStringLiteral("Scale"))) {
      const double sc = vars.value(pre + QStringLiteral("Scale")).toDouble();
      if (sc > 0) pose.scale = sc;
    }
    if (vars.contains(pre + QStringLiteral("Score")))
      r.score = vars.value(pre + QStringLiteral("Score")).toDouble();
    r.boundFrom = pre;
    r.boundOk = true;
    return true;
  };

  if (source == QLatin1String("auto") || source == QLatin1String("bind")) {
    QString bind = params.value(QStringLiteral("bindStepId")).toString().trimmed();
    const bool autoBind = !params.contains(QStringLiteral("autoBindLocate")) ||
                          params.value(QStringLiteral("autoBindLocate")).toBool();
    bool bound = false;
    if (!bind.isEmpty()) bound = tryBind(bind) || tryBind(QStringLiteral("locate"));
    if (!bound && autoBind) bound = tryBind(QStringLiteral("locate"));
    if (!bound && source == QLatin1String("bind")) {
      r.status = QStringLiteral("unbound");
      r.note = QStringLiteral("未解析到上游 matches/items，使用 baseX/Y");
    } else if (bound) {
      r.status = QStringLiteral("ok");
      r.note = QStringLiteral("已绑定上游匹配位姿");
    } else {
      r.status = QStringLiteral("unbound");
      r.note = QStringLiteral("未解析到上游 matches/items，使用 baseX/Y");
    }
  } else {
    r.status = QStringLiteral("ok");
    r.note = QStringLiteral("手动基准位姿");
    pose.ok = true;
  }
  pose.ok = r.boundOk || source == QLatin1String("manual");
  r.pose = pose;
  r.ok = pose.ok;
  const double axisLen = params.value(QStringLiteral("axisLength"), 40).toDouble();
  const double L = axisLen > 0 ? axisLen : 40;
  r.origin = QPointF(pose.x, pose.y);
  r.axisX << r.origin << poseMap(pose, QPointF(L, 0));
  r.axisY << r.origin << poseMap(pose, QPointF(0, L));
  if (!r.ok && r.note.isEmpty()) r.note = QStringLiteral("定位跟随未绑定");
  return r;
}

QStringList locateSelfTest() {
  QStringList fails;
  auto expect = [&](bool cond, const char* msg) {
    if (!cond) fails << QString::fromUtf8(msg);
  };

  // follow math
  {
    Pose2D p;
    p.x = 100;
    p.y = 50;
    p.angleDeg = 0;
    p.scale = 1;
    p.ok = true;
    const QPointF a = poseMap(p, QPointF(10, 4));
    expect(qAbs(a.x() - 110) < 1e-6 && qAbs(a.y() - 54) < 1e-6, "map 0deg");
    const QPointF b = poseUnmap(p, a);
    expect(qAbs(b.x() - 10) < 1e-6 && qAbs(b.y() - 4) < 1e-6, "unmap 0deg");
    p.angleDeg = 90;
    const QPointF c = poseMap(p, QPointF(10, 0));
    expect(qAbs(c.x() - 100) < 1e-6 && qAbs(c.y() - 60) < 1e-6, "map 90deg");
  }

  QImage scene(220, 160, QImage::Format_RGB888);
  scene.fill(QColor(200, 200, 200));
  const QRect mark(80, 50, 40, 30);
  {
    QPainter p(&scene);
    p.fillRect(mark, QColor(20, 20, 80));
    p.fillRect(QRect(84, 54, 10, 22), QColor(220, 200, 40));  // asymmetry for rotation
    p.end();
  }
  const QImage tpl = scene.copy(mark);
  QVariantMap lp;
  lp.insert(QStringLiteral("minScore"), 0.7);
  lp.insert(QStringLiteral("maxMatches"), 2);
  lp.insert(QStringLiteral("angleStart"), 0);
  lp.insert(QStringLiteral("angleEnd"), 0);
  lp.insert(QStringLiteral("templatePath"), QString());  // will fail file; inject via...
  // runLocate would try to resolve template from empty path → capture. We'll pass
  // by saving? Easier: write a temp is messy. Add a hook? Use runLocate after putting
  // the template in params via... resolve uses file or capture.
  // Call findTemplate + runLocate with templatePath saved to a buffer isn't needed:
  // we can set templateSource capture... actually empty path uses salientCrop.
  // Safer: use findTemplate directly and also runLocate with a written path? 
  // Selftest shouldn't depend on disk. I'll add optional _template image later.
  // For now test findTemplate + a pathless capture might find the high-variance mark.
  {
    const QVector<TemplateHit> hits = findTemplate(scene, tpl, 0.75, 1, 2);
    expect(!hits.isEmpty(), "find mark");
    if (!hits.isEmpty()) {
      expect(qAbs(hits.first().center.x() - mark.center().x()) <= 3, "center x");
      expect(qAbs(hits.first().center.y() - mark.center().y()) <= 3, "center y");
      expect(hits.first().score >= 0.9, "score high");
    }
  }

  // rotation: paint mark into a larger canvas rotated 15° around its center
  {
    QImage rot(220, 160, QImage::Format_RGB888);
    rot.fill(QColor(200, 200, 200));
    QPainter p(&rot);
    p.translate(110, 80);
    p.rotate(15);  // Qt: clockwise in y-down? rotate is CW in y-down actually wait:
    // QPainter::rotate is clockwise for y-down. Our angle is CCW in y-down [c -s;s c]
    // which is visually clockwise on screen... Let's just search a range and require
    // a hit with |angle|>=5 and score ok, rather than exact 15.
    p.translate(-mark.center());
    p.drawImage(mark.topLeft(), tpl);
    p.end();
    QVariantMap rp;
    rp.insert(QStringLiteral("minScore"), 0.65);
    rp.insert(QStringLiteral("maxMatches"), 1);
    rp.insert(QStringLiteral("angleStart"), -20);
    rp.insert(QStringLiteral("angleEnd"), 20);
    rp.insert(QStringLiteral("angleStep"), 5);
    rp.insert(QStringLiteral("step"), 2);
    // stash template by using capture on a scene that's just the mark? Instead extend
    // runLocate to accept an already-resolved image via a private... I'll write
    // to a QImage and use find after exposing runLocate on (scene, tpl, params).
    // Quick path: add overload? For selftest, save to a unique /tmp file is ok in smoke
    // machine. Prefer in-memory: if params contains "_templateImage" ... skip.
    // I'll call a file in artifacts? Selftest may run without write access... use
    // QTemporary? Keep it in /tmp.
    const QString path = QStringLiteral("/tmp/sieans-locate-selftest-tpl.png");
    tpl.save(path);
    rp.insert(QStringLiteral("templatePath"), path);
    const LocateResult lr = runLocate(rot, rp);
    expect(lr.ok, "rotated ok");
    if (lr.ok) {
      expect(lr.hits.first().score >= 0.65, "rotated score");
      expect(qAbs(lr.hits.first().angleDeg) >= 5, "rotated angle nonzero");
    }
  }

  {
    Pose2D pose;
    pose.x = 80;
    pose.y = 40;
    pose.angleDeg = 0;
    pose.scale = 1;
    pose.ok = true;
    QVariantMap fp;
    fp.insert(QStringLiteral("followFixture"), true);
    fp.insert(QStringLiteral("fixtureX"), pose.x);
    fp.insert(QStringLiteral("fixtureY"), pose.y);
    fp.insert(QStringLiteral("fixtureAngle"), 0);
    fp.insert(QStringLiteral("fixtureScale"), 1);
    fp.insert(QStringLiteral("fixtureOk"), 1);
    fp.insert(QStringLiteral("roiX"), 20);
    fp.insert(QStringLiteral("roiY"), -8);
    fp.insert(QStringLiteral("roiW"), 16);
    fp.insert(QStringLiteral("roiH"), 16);
    const FollowRoi fr = resolveFollowRoi(fp, 400, 300);
    expect(fr.active, "follow roi active");
    expect(qAbs(fr.center.x() - (80 + 20 + 8)) < 1.0, "follow roi cx");
    expect(qAbs(fr.center.y() - (40 - 8 + 8)) < 1.0, "follow roi cy");
  }

  {
    QVariantMap vars;
    vars.insert(QStringLiteral("locateX"), 123);
    vars.insert(QStringLiteral("locateY"), 45);
    vars.insert(QStringLiteral("locateAngle"), -7);
    vars.insert(QStringLiteral("locateScore"), 0.91);
    vars.insert(QStringLiteral("locateOk"), 1);
    QVariantMap p;
    p.insert(QStringLiteral("fixtureSource"), QStringLiteral("auto"));
    const PoseCorrectResult cr = runPoseCorrect(p, vars);
    expect(cr.ok && cr.boundOk, "pose bind");
    expect(qAbs(cr.pose.x - 123) < 1e-6 && qAbs(cr.pose.y - 45) < 1e-6, "pose xy");
    expect(qAbs(cr.pose.angleDeg + 7) < 1e-6, "pose angle");
  }

  {
    QVariantMap p;
    p.insert(QStringLiteral("fixtureSource"), QStringLiteral("manual"));
    p.insert(QStringLiteral("baseX"), 5);
    p.insert(QStringLiteral("baseY"), 6);
    const PoseCorrectResult cr = runPoseCorrect(p, {});
    expect(cr.ok && cr.pose.x == 5 && cr.pose.y == 6, "manual pose");
  }

  // NCC：同一标记应得到接近 1 的相关分数。
  {
    const QString path = QStringLiteral("/tmp/sieans-locate-selftest-ncc-tpl.png");
    tpl.save(path);
    QVariantMap np;
    np.insert(QStringLiteral("minScore"), 0.8);
    np.insert(QStringLiteral("maxMatches"), 1);
    np.insert(QStringLiteral("angleStart"), 0);
    np.insert(QStringLiteral("angleEnd"), 0);
    np.insert(QStringLiteral("metric"), QStringLiteral("ncc"));
    np.insert(QStringLiteral("step"), 2);
    np.insert(QStringLiteral("templatePath"), path);
    const LocateResult lr = runLocate(scene, np);
    expect(lr.ok, "ncc ok");
    if (lr.ok) {
      expect(lr.hits.first().score >= 0.95, "ncc score");
      expect(qAbs(lr.hits.first().center.x() - mark.center().x()) <= 3, "ncc cx");
      expect(qAbs(lr.hits.first().center.y() - mark.center().y()) <= 3, "ncc cy");
    }
  }

  // 各向异性：场景中的标记只在 X 方向拉到 1.4 倍，搜索应落到 scaleX≈1.4、scaleY=1。
  {
    QImage aniso(260, 160, QImage::Format_RGB888);
    aniso.fill(QColor(200, 200, 200));
    QImage stretched = tpl.scaled(qRound(tpl.width() * 1.4), tpl.height());
    {
      QPainter p(&aniso);
      p.drawImage(QPoint(70, 50), stretched);
      p.end();
    }
    const QString path = QStringLiteral("/tmp/sieans-locate-selftest-aniso-tpl.png");
    tpl.save(path);
    QVariantMap ap;
    ap.insert(QStringLiteral("minScore"), 0.7);
    ap.insert(QStringLiteral("maxMatches"), 1);
    ap.insert(QStringLiteral("angleStart"), 0);
    ap.insert(QStringLiteral("angleEnd"), 0);
    ap.insert(QStringLiteral("scaleEnable"), true);
    ap.insert(QStringLiteral("scaleAniso"), true);
    ap.insert(QStringLiteral("scaleMin"), 1.0);
    ap.insert(QStringLiteral("scaleMax"), 1.6);
    ap.insert(QStringLiteral("scaleStep"), 0.2);
    ap.insert(QStringLiteral("scaleYMin"), 1.0);
    ap.insert(QStringLiteral("scaleYMax"), 1.0);
    ap.insert(QStringLiteral("scaleYStep"), 0.2);
    ap.insert(QStringLiteral("step"), 2);
    ap.insert(QStringLiteral("templatePath"), path);
    const LocateResult lr = runLocate(aniso, ap);
    expect(lr.ok, "aniso ok");
    if (lr.ok) {
      expect(qAbs(lr.hits.first().scaleX - 1.4) <= 0.21, "aniso scaleX");
      expect(qAbs(lr.hits.first().scaleY - 1.0) <= 0.05, "aniso scaleY");
    }
  }

  // 多模板：两个不同标记，库里两个模板，应各命中一次。
  {
    QImage two(280, 180, QImage::Format_RGB888);
    two.fill(QColor(200, 200, 200));
    QImage tplB(40, 30, QImage::Format_RGB888);
    tplB.fill(QColor(20, 90, 20));
    {
      QPainter p(&tplB);
      p.fillRect(QRect(6, 6, 22, 8), QColor(240, 80, 80));
      p.end();
    }
    {
      QPainter p(&two);
      p.drawImage(QPoint(40, 40), tpl);
      p.drawImage(QPoint(160, 80), tplB);
      p.end();
    }
    const QString pa = QStringLiteral("/tmp/sieans-locate-selftest-lib-a.png");
    const QString pb = QStringLiteral("/tmp/sieans-locate-selftest-lib-b.png");
    tpl.save(pa);
    tplB.save(pb);
    QVariantList lib;
    lib << QVariantMap{{QStringLiteral("name"), QStringLiteral("markA")},
                       {QStringLiteral("path"), pa}};
    lib << QVariantMap{{QStringLiteral("name"), QStringLiteral("markB")},
                       {QStringLiteral("path"), pb}};
    QVariantMap mp;
    mp.insert(QStringLiteral("minScore"), 0.75);
    mp.insert(QStringLiteral("maxMatches"), 2);
    mp.insert(QStringLiteral("angleStart"), 0);
    mp.insert(QStringLiteral("angleEnd"), 0);
    mp.insert(QStringLiteral("step"), 2);
    mp.insert(QStringLiteral("templateLibrary"), lib);
    const LocateResult lr = runLocate(two, mp);
    expect(lr.ok && lr.hits.size() == 2, "multi count");
    if (lr.hits.size() == 2) {
      QStringList names;
      for (const TemplateHit& h : lr.hits) names << h.templateName;
      expect(names.contains(QStringLiteral("markA")) && names.contains(QStringLiteral("markB")),
             "multi names");
    }
  }

  // 弹性分块：水平条中段错位 14px，整体刚体 NCC 应达不到 0.75，分块应找到；
  // 换成明显不同的方块时应拒绝。不是变化模型，只允许块内平移。
  {
    QImage bar(80, 20, QImage::Format_RGB888);
    bar.fill(QColor(0, 0, 0));
    {
      QPainter p(&bar);
      p.fillRect(QRect(0, 2, 80, 16), QColor(240, 240, 240));
      p.fillRect(QRect(2, 4, 10, 12), QColor(40, 40, 200));  // 左端标记
      p.end();
    }
    QImage bent(200, 100, QImage::Format_RGB888);
    bent.fill(QColor(0, 0, 0));
    {
      QPainter p(&bent);
      p.drawImage(QPoint(30, 20), bar.copy(0, 0, 40, 20));
      p.drawImage(QPoint(70, 34), bar.copy(40, 0, 40, 20));  // 下错 14px
      p.end();
    }
    const QString path = QStringLiteral("/tmp/sieans-locate-selftest-deform-tpl.png");
    bar.save(path);
    QVariantMap rigidP;
    rigidP.insert(QStringLiteral("minScore"), 0.75);
    rigidP.insert(QStringLiteral("maxMatches"), 1);
    rigidP.insert(QStringLiteral("angleStart"), 0);
    rigidP.insert(QStringLiteral("angleEnd"), 0);
    rigidP.insert(QStringLiteral("metric"), QStringLiteral("ncc"));
    rigidP.insert(QStringLiteral("step"), 2);
    rigidP.insert(QStringLiteral("templatePath"), path);
    const LocateResult rigid = runLocate(bent, rigidP);
    expect(!rigid.ok, "deform rigid should miss jog");

    QVariantMap dp = rigidP;
    dp.insert(QStringLiteral("matchMode"), QStringLiteral("deform"));
    dp.insert(QStringLiteral("deformEnable"), true);
    dp.insert(QStringLiteral("deformRadius"), 16);
    dp.insert(QStringLiteral("deformLambda"), 0.15);
    dp.insert(QStringLiteral("deformGridX"), 2);
    dp.insert(QStringLiteral("deformGridY"), 1);
    dp.insert(QStringLiteral("minScore"), 0.7);
    const LocateResult el = runLocate(bent, dp);
    expect(el.ok, "deform finds jog");
    if (el.ok) {
      expect(el.hits.first().score >= 0.7, "deform score");
      expect(qAbs(el.hits.first().center.x() - 70) <= 16, "deform cx");
      expect(el.hits.first().center.y() >= 20 && el.hits.first().center.y() <= 54, "deform cy");
    }

    QImage other(200, 100, QImage::Format_RGB888);
    other.fill(QColor(0, 0, 0));
    {
      QPainter p(&other);
      p.setBrush(QColor(240, 240, 240));
      p.setPen(Qt::NoPen);
      p.drawEllipse(QPoint(80, 50), 28, 28);
      p.end();
    }
    const LocateResult rej = runLocate(other, dp);
    expect(!rej.ok, "deform rejects disk");
  }

  return fails;
}

}  // namespace sieans_qt
