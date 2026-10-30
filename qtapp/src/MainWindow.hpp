#pragma once

#include "ImageView.hpp"

#include <QMainWindow>
#include <QPlainTextEdit>
#include <QLabel>
#include <QTreeWidget>
#include <memory>

namespace sieans {
class GenTLCapture;
}

namespace sieans_qt {

class MainWindow : public QMainWindow {
  Q_OBJECT
 public:
  explicit MainWindow(QWidget* parent = nullptr);
  ~MainWindow() override;

 private slots:
  void onOpenImage();
  void onLoadSample();
  void onDecodeQr();
  void onEnumerateGenTL();
  void onGrabOneFrame();
  void onAbout();

 private:
  void buildUi();
  void buildMenus();
  void buildToolbar();
  void logResult(const QString& line);
  void showStatus(const QString& msg, int timeout_ms = 5000);
  bool loadImagePath(const QString& path);
  void runDecodeOnCurrent();

  ImageView* image_view_ = nullptr;
  QTreeWidget* flow_tree_ = nullptr;
  QPlainTextEdit* result_panel_ = nullptr;
  QLabel* status_backend_ = nullptr;

  QString current_path_;
  std::unique_ptr<sieans::GenTLCapture> gentl_;
  QString last_gentl_device_id_;
};

}  // namespace sieans_qt
