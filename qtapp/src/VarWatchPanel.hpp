#pragma once

#include <QWidget>
#include <QEvent>
#include <QTableWidget>
#include <QVariantMap>
#include <QStringList>

class QLineEdit;

namespace sieans_qt {

class VarWatchPanel : public QWidget {
  Q_OBJECT
 public:
  explicit VarWatchPanel(QWidget* parent = nullptr);

  void setWatchKeys(const QStringList& keys);
  void setKeyList(const QStringList& keys);
  void setVariables(const QVariantMap& vars);
  void exportFiltered();
  void copyKeyEqualsValue();
  void copyFlowToken();
  void exportJsonFiltered();
  void exportKeysJson();
  void addKeysFromClipboard();
  void replaceKeysFromClipboard();
  void removeSelectedKeys();
  void removeTailWatchKey();
  void moveSelectedKey(int delta);
  void cutSelectedKeys();
  void copyHostWatchKeys();
  void reverseWatchKeys();
  void moveSelectedToEdge(int edge);
  void toggleSelectedHostWatch();
  void clearAllWatchKeys();
  void sortWatchKeys();
  void dedupeWatchKeys();
  QStringList watchKeyList() const { return keys_; }
  QVariantMap variables() const { return vars_; }

 signals:
  void hostWatchToggleRequested(const QString& key);
  void watchListChanged(const QStringList& keys);

 protected:
  bool eventFilter(QObject* obj, QEvent* event) override;

private:
  void rebuild();

  QTableWidget* table_ = nullptr;
  QLineEdit* filterEdit_ = nullptr;
  QStringList keys_;
  QStringList hostWatch_;
  QVariantMap vars_;
  QString filter_;
};

}  // namespace sieans_qt
