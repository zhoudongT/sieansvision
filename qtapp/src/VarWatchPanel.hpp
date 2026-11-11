#pragma once

#include <QWidget>
#include <QEvent>
#include <QTableWidget>
#include <QVariantMap>
#include <QStringList>
#include <QHash>

class QLineEdit;
class QComboBox;
class QPushButton;
class QLabel;
class QHBoxLayout;

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
  /** Restore named pin groups onto the combo (no signal). */
  void setPinGroups(const QStringList& names, const QHash<QString, QStringList>& keys,
                    const QString& active);
  /** Switch the combo and emit pinGroupChanged. */
  bool selectPinGroup(const QString& name);
  QString activePinGroup() const { return activePinGroup_; }
  int pinGroupCount() const { return pinGroupNames_.size(); }
  QString pinGroupLabelText() const;
  QStringList watchKeyList() const { return keys_; }
  QVariantMap variables() const { return vars_; }

 signals:
  void hostWatchToggleRequested(const QString& key);
  void watchListChanged(const QStringList& keys);
  void pinGroupChanged(const QString& name);
  void pinGroupSaveRequested();
  void pinGroupNewRequested(const QString& name);

 protected:
  bool eventFilter(QObject* obj, QEvent* event) override;

private:
  void rebuild();
  void rebuildPinGroupCombo();
  void syncPinGroupLabel();
  void onNewPinGroup();

  QTableWidget* table_ = nullptr;
  QLineEdit* filterEdit_ = nullptr;
  QComboBox* pinGroupCombo_ = nullptr;
  QPushButton* pinGroupNewBtn_ = nullptr;
  QPushButton* pinGroupSaveBtn_ = nullptr;
  QLabel* pinGroupLab_ = nullptr;
  QStringList keys_;
  QStringList hostWatch_;
  QStringList pinGroupNames_;
  QHash<QString, QStringList> pinGroupKeys_;
  QString activePinGroup_;
  QVariantMap vars_;
  QString filter_;
};

}  // namespace sieans_qt
